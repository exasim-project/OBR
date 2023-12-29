"""
Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -mobr` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``obr.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``obr.__main__`` in ``sys.modules``.

  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""

import click
import yaml  # type: ignore[import]
import os
import time
import sys
import json
import logging
import pandas as pd
import shutil

from signac.contrib.job import Job
from .signac_wrapper.operations import OpenFOAMProject, get_values
from .create_tree import create_tree
from .core.parse_yaml import read_yaml
from .core.queries import input_to_queries, query_impl, build_filter_query, Query
from .core.core import map_view_folder_to_job_id, merge_job_documents
from pathlib import Path
from subprocess import check_output
from git.repo import Repo
from git.util import Actor
from git import InvalidGitRepositoryError
from datetime import datetime
from typing import Union, Optional, Any
from copy import deepcopy


def check_cli_operations(
    project: OpenFOAMProject, operations: list[str], list_operations: Optional[Any]
) -> bool:
    """list available operations if none are specified or given the click option or an incorrect op is given"""
    if operations == ["generate"]:
        return True
    if list_operations:
        project.print_operations()
        return False
    elif not operations:
        logging.info("No operation(s) specified.")
        project.print_operations()
        logging.info("Syntax: obr run [-o|--operation] <operation>(,<operation>)+")
        return False
    elif any((false_op := op) not in project.operations for op in operations):
        logging.info(f"Specified operation {false_op} is not a valid operation.")
        project.print_operations()
        return False
    return True


def is_valid_workspace(filters: list[str] = []) -> bool:
    """This function checks if:
    - the `workspace` folder is not empty, and
    - applying filters would return an empty list
    """
    project: OpenFOAMProject = OpenFOAMProject.get_project()
    jobs: list[Job] = project.filter_jobs(filters=filters)
    if len(jobs) == 0:
        if filters == []:
            logging.warning("No jobs found in workspace folder!")
            return False
        logging.warning(
            f"Found no jobs that satisfy the given filter(s) {' and '.join(filters)}!"
        )
        return False
    return True


def copy_to_archive(
    repo: Union[Repo, None], use_git_repo: bool, src_file: Path, target_file: Path
) -> None:
    """Copies files to archive repo"""
    # ensure target directory exists()
    target_path = target_file.parents[0]
    if not target_path.exists():
        target_path.mkdir(parents=True)
    logging.info(f"cp \\\n\t{src_file}\n\t{target_file.resolve()}")
    if src_file.is_symlink():
        src_file = Path(os.path.realpath(src_file))
    check_output(["cp", src_file, target_file])
    if use_git_repo and repo:
        repo.git.add(target_file)  # NOTE do _not_ do repo.git.add(all=True)


def archive_view(
    repo: Union[Repo, None],
    use_git_repo: bool,
    campaign_target_path: Path,
    view_name: Path,
    target_folder: Path,
):
    """Creates a new view folder in the archival folder"""
    dst = campaign_target_path.absolute()
    print("create view folder", view_name.parent)
    view_name.parent.mkdir(parents=True, exist_ok=True)

    relpath = os.path.relpath(dst, view_name)
    # for some reason the relpath has one ../ too much
    relpath = relpath[3:]
    print("create_view_link", dst, view_name, relpath)

    if not Path(view_name).exists():
        view_name.symlink_to(relpath)

    if use_git_repo and repo:
        repo.git.add(view_name)  # NOTE do _not_ do repo.git.add(all=True)


def cli_cmd_setup(kwargs: dict) -> tuple[OpenFOAMProject, Job]:
    """This function performs the common pattern of checking project folders for existence and creating the project and extracting the jobs."""
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])
    project = OpenFOAMProject.get_project()
    filters: list[str] = kwargs.get("filter", [])
    if sel := kwargs.get("job"):
        jobs = [job for job in project if sel == job.id]
    else:
        jobs = project.filter_jobs(filters=filters)

    # check if given path points to valid project
    if not is_valid_workspace(filters):
        sys.exit(1)
    return project, jobs


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx: click.Context, debug: bool):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option(
    "-p", "--pretend", is_flag=True, help="Set flag to only print submission script"
)
@click.option(
    "-o",
    "--operations",
    default="",
    required=True,
    help=(
        "Specify the operation(s) to run. Pass multiple operations after -o, separated"
        " by commata (NO space), e.g. obr run -o shell,apply. Run with --help to list"
        " available operations."
    ),
)
@click.option(
    "-l",
    "--list_operations",
    is_flag=True,
    help="Prints all available operations and returns.",
)
@click.option(
    "--filter",
    type=str,
    multiple=True,
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --filter."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr submit --filter"
        ' "solver==pisoFoam"'
    ),
)
@click.option("--bundling_key", default=None, help="")
@click.option("-p", "--partition", default="cpuonly")
@click.option("--account", default="")
@click.option("--pretend", is_flag=True)
@click.option(
    "--scheduler_args",
    default="",
    help="Currently required to be in --key1 value --key2 value2 form",
)
@click.pass_context
def submit(ctx: click.Context, **kwargs):
    project, jobs = cli_cmd_setup(kwargs)

    project._entrypoint = {"executable": "", "path": "obr"}

    operations = kwargs.get("operations", "").split(",")
    list_operations = kwargs.get("list_operations")
    if not check_cli_operations(project, operations, list_operations):
        return

    partition = kwargs.get("partition")
    account = kwargs.get("account")

    # TODO find a signac way to do that
    cluster_args = {
        "partition": partition,
        "pretend": kwargs["pretend"],
        "account": account,
    }

    # TODO improve this using regex
    scheduler_args = kwargs.get("scheduler_args")
    if scheduler_args:
        split = scheduler_args.split(" ")
        for i in range(0, len(split), 2):
            cluster_args.update({split[i]: split[i + 1]})

    bundling_key = kwargs.get("bundling_key")
    if bundling_key:
        bundling_values = get_values(jobs, bundling_key)
        for bundle_value in bundling_values:
            selected_jobs: list[Job] = [
                j for j in project if bundle_value in list(j.sp().values())
            ]
            logging.info(f"submit bundle {bundle_value} of {len(selected_jobs)} jobs")
            ret_submit = (
                project.submit(
                    jobs=selected_jobs,
                    bundle_size=len(selected_jobs),
                    names=[kwargs.get("operation")],
                    **cluster_args,
                )
                or ""
            )
            logging.info("submission response" + str(ret_submit))
            time.sleep(15)
    else:
        logging.info(f"submitting {len(jobs)} individual jobs")
        import cProfile
        import pstats

        with cProfile.Profile() as pr:
            ret_submit = project.submit(
                jobs=jobs,
                names=operations,
                **cluster_args,
            )
            logging.info(ret_submit)

        stats = pstats.Stats(pr)
        stats.sort_stats(pstats.SortKey.TIME)
        # stats.print_stats()
        stats.dump_stats(filename="needs_profiling.prof")

    # print(project.scheduler_jobs(TestEnvironment.get_prefix(runSolver)))
    # print(list(project.scheduler_jobs(TestEnvironment.get_scheduler())))
    #


@cli.command()
@click.option(
    "--filter",
    type=str,
    multiple=True,
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --filter."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr run -o"
        ' runParallelSolver --filter "solver==pisoFoam"'
    ),
)
@click.option("-w", "--workspace", is_flag=True, help="remove all obr project files")
@click.option("-c", "--case", is_flag=True, help="reset the state of a case by deleting solver logs")
@click.option(
    "-v", "--view", default="remove case completely specified by a view folder"
)
@click.pass_context
def reset(ctx: click.Context, **kwargs):
    """deletes workspace or cases"""

    def safe_delete(fn):
        path = Path(fn)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    project, jobs = cli_cmd_setup(kwargs)

    if kwargs.get("workspace"):
        safe_delete("workspace")
        safe_delete("view")
        safe_delete("signac.rc")
        return
    if kwargs.get("case"):
        project.run(
            jobs = jobs,
            names=["resetCase"],
            progress=True,
            np=-1,
        )

    # TODO implement a procedure  that checks if it is inside
    # a obr project. To allow 'obr purge .' within a view


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option(
    "-o",
    "--operations",
    default="",
    required=True,
    help=(
        "Specify the operation(s) to run. Pass multiple operations after -o, separated"
        " by commata (NO space), e.g. obr run -o shell,apply. Run with --help to list"
        " available operations."
    ),
)
@click.option(
    "-l",
    "--list_operations",
    is_flag=True,
    help="Prints all available operations and returns.",
)
@click.option(
    "--filter",
    type=str,
    multiple=True,
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --filter."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr run -o"
        ' runParallelSolver --filter "solver==pisoFoam"'
    ),
)
@click.option("-j", "--job")
@click.option("--args", default="")
@click.option("-t", "--tasks", default=-1)
@click.option("-a", "--aggregate", is_flag=True)
@click.option("--args", default="")
@click.pass_context
def run(ctx: click.Context, **kwargs):
    """Run specified operations"""
    print("run", kwargs)
    project, jobs = cli_cmd_setup(kwargs)

    operations = kwargs.get("operations", "").split(",")
    list_operations = kwargs.get("list_operations")
    if not check_cli_operations(project, operations, list_operations):
        return

    if kwargs.get("args"):
        os.environ["OBR_CALL_ARGS"] = kwargs.get("args", "")

    if kwargs.get("job"):
        os.environ["OBR_JOB"] = kwargs.get("job", "")

    if kwargs.get("operations") == "apply":
        logging.warning("Run 'obr apply' directly")
        return

    if kwargs.get("operations") == "runParallelSolver":
        # NOTE if tasks is not set explicitly we set it to 1 for parallelSolverSolver
        # to avoid oversubsrciption
        ntasks: int = kwargs["tasks"] if kwargs.get("tasks", 0) >= 1 else 1
        if not kwargs.get("tasks", False):
            sys.argv.append("-t")
            sys.argv.append(str(ntasks))
        project.run(
            names=operations,
            progress=True,
            np=ntasks,
        )
        return

    if not kwargs.get("aggregate"):
        project.run(
            jobs=jobs,  # project.groupby("doc.is_base"),
            names=operations,
            progress=True,
            np=kwargs.get("tasks", -1),
        )
    else:
        # calling for aggregates does not work with jobs
        project.run(
            names=operations,
            np=kwargs.get("tasks", -1),
        )
    logging.info("completed all operations")


@cli.command()
@click.option(
    "-c",
    "--campaign",
    type=str,
    multiple=False,
    help="",
)
@click.option(
    "-f",
    "--file",
    type=str,
    multiple=False,
    help="",
)
@click.option(
    "--filter",
    type=str,
    multiple=True,
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --filter."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr run -o"
        ' runParallelSolver --filter "solver==pisoFoam"'
    ),
)
@click.pass_context
def apply(ctx: click.Context, **kwargs):
    project = OpenFOAMProject().init_project()

    filters: list[str] = kwargs.get("filter", [])
    # check if given path points to valid project
    if not is_valid_workspace(filters):
        return
    jobs = project.filter_jobs(filters=filters)
    os.environ["OBR_APPLY_FILE"] = kwargs.get("file", "")
    os.environ["OBR_APPLY_CAMPAIGN"] = kwargs.get("campaign", "")
    sys.argv.append("--aggregate")
    sys.argv.append("-t")
    sys.argv.append("1")
    project.run(
        names=["apply"],
        progress=True,
        np=1,
    )


@cli.command()
@click.option(
    "-f",
    "--folder",
    default=".",
    help="Where to create the worspace and view. Default: '.' ",
)
@click.option(
    "-g", "--generate", is_flag=True, help="Call generate directly after init."
)
@click.option(
    "-w", "--workflow", default="", help="Call a given workflow command after generate."
)
@click.option("-c", "--config", required=True, help="Path to configuration file.")
@click.option("-t", "--tasks", default=-1, help="Number of tasks to run concurrently.")
@click.option("-u", "--url", default=None, help="Url to a configuration yaml")
@click.option("--verbose", default=0, help="set verbosity")
@click.pass_context
def init(ctx: click.Context, **kwargs):
    config_str = read_yaml(kwargs)
    config_str = config_str.replace("\n\n", "\n")
    config = yaml.safe_load(config_str)

    if kwargs.get("verbose", 0) >= 1:
        logging.info(config)

    project = OpenFOAMProject.init_project(root=kwargs["folder"])
    create_tree(project, config, kwargs)

    logging.info("successfully initialised")

    if kwargs.get("generate"):
        project.run(
            names=["generate"],
            progress=True,
            np=kwargs.get("tasks", -1),
        )


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-d", "--detailed", is_flag=True)
@click.option("--detailed", is_flag=True)
@click.option(
    "--hide",
    default="",
    help="Hide default values like jobid from output.",
)
@click.option(
    "--extra",
    default="",
    help="Pass a comma separated list to set extra values",
)
@click.option(
    "--sort_by",
    default="",
    help="Pass a comma separated list to set the ordering of the output",
)
@click.option(
    "--filter",
    type=str,
    multiple=True,
    default=[],
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --filter."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr submit --filter"
        ' "solver==pisoFoam"'
    ),
)
@click.option(
    "--export_to",
    required=False,
    multiple=False,
    default="markdown",
    help="Output format. Valid choices: markdown, json",
)
@click.pass_context
def status(ctx: click.Context, **kwargs):
    project, jobs = cli_cmd_setup(kwargs)

    # project.print_status(detailed=kwargs["detailed"], pretty=True)
    id_view_map = map_view_folder_to_job_id("view")
    sort_by = kwargs.get("sort_by", False).split(",")
    extra = kwargs.get("extra", "").split(",")
    hide = kwargs.get("hide", "")
    hide = hide.split(",") if hide else []

    input_queries = sort_by + extra
    queries: list[Query] = build_filter_query(input_queries)
    # convert query results to records
    records = []
    query_results = project.query(jobs=jobs, query=queries)
    for jobid, entries in query_results.items():
        record = {"jobid": jobid}
        record.update(entries)
        records.append(record)

    query_results = project.query(jobs=jobs, query=queries)
    df = pd.DataFrame.from_records(records)
    df["view"] = df["jobid"].apply(lambda x: id_view_map.get(x, None))
    if hide:
        df.drop(columns=hide, inplace=True, axis=0)
    if sort_by:
        # df.dropna(inplace=True)
        df = df.set_index(sort_by).sort_index().reset_index()
        if not kwargs.get("detailed"):
            df.dropna(inplace=True)
    # with open(export_to, "w") as outfile:
    if kwargs.get("export_to") == "markdown":
        print(df.to_markdown(tablefmt="github"))
    if kwargs.get("export_to") == "json":
        print(df.to_json())


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option(
    "--filter",
    type=str,
    multiple=True,
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --filter."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr query --filter"
        "solver==pisoFoam"
    ),
)
@click.option("-d", "--detailed", is_flag=True)
@click.option("-a", "--all", is_flag=True)
@click.option(
    "-q",
    "--query",
    required=True,
    multiple=True,
    help=(
        "Pass a <key><predicate><value> value pair per occurrence of --query."
        " Predicates include ==, !=, <=, <, >=, >. For instance, obr query --query"
        " solver==pisoFoam"
    ),
)
@click.option(
    "--campaign",
    required=False,
    multiple=False,
    help="Run query only on job document of a specific campaign.",
)
@click.option(
    "--export_to",
    required=False,
    multiple=False,
    help="Write results to a file. Valid choices json, markdown",
)
@click.option(
    "--markdown_formater",
    required=False,
    multiple=False,
    help="Format ",
)
@click.option(
    "--validate_against",
    required=False,
    multiple=False,
    help="Validate the query output against the specified file.",
)
@click.option(
    "--quiet", required=False, is_flag=True, help="Don't print out query results."
)
@click.pass_context
def query(ctx: click.Context, **kwargs):
    # TODO refactor
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject.get_project()
    filters: list[str] = list(kwargs.get("filter", ()))
    if not is_valid_workspace(filters):
        return

    input_queries: tuple[str] = kwargs.get("query", ())
    quiet: bool = kwargs.get("quiet", False)

    if input_queries == "":
        logging.warning("--query argument cannot be empty!")
        return
    queries: list[Query] = build_filter_query(input_queries)
    jobs = project.filter_jobs(filters=list(filters))

    if kwargs.get("campaign"):
        for job in jobs:
            merge_job_documents(job, kwargs.get("campaign"))

    query_results = project.query(jobs=jobs, query=queries)
    if not quiet:
        for job_id, query_res in deepcopy(query_results).items():
            out_str = f"{job_id}:"
            for k, v in query_res.items():
                out_str += f" {k}: {v}"
            logging.info(out_str)

    export_to: str = kwargs.get("export_to", "")
    if export_to:
        if export_to.endswith(".json"):
            with open(export_to, "w") as outfile:
                # json_data refers to the above JSON
                json.dump(query_results, outfile)
        if export_to.endswith(".md"):
            # convert query results to records
            records = []
            for jobid, entries in query_results.items():
                record = {"jobid": jobid}
                record.update(entries)
                records.append(record)

            df = pd.DataFrame.from_records(records)
            df.dropna(inplace=True)
            df.set_index(["nCells"], inplace=True)
            df.sort_index(inplace=True)
            with open(export_to, "w") as outfile:
                df.to_markdown(outfile)

    validation_file: str = kwargs.get("validate_against", "")
    if validation_file:
        with open(validation_file, "r") as infile:
            # json_data refers to the above JSON
            validation_dict = json.load(infile)
            if validation_dict.get("$schema"):
                logging.info("using json schema for validation")
                from jsonschema import validate

                validate(query_results, validation_dict)
            else:
                from deepdiff import DeepDiff

                logging.info("using deepdiff for validation")
                difference_dict = DeepDiff(validation_dict, query_results)

                if difference_dict:
                    print(difference_dict)
                    logging.warn("validation failed")
                    sys.exit(1)


@cli.command()
@click.option(
    "--filter",
    type=str,
    multiple=True,
    help=(
        "Pass a <key>=<value> value pair per occurrence of --filter. For instance, obr"
        " archive --filter solver=pisoFoam --filter preconditioner=IC"
    ),
)
@click.option(
    "-f",
    "--folder",
    required=True,
    default=".",
    type=str,
    help="Path to OpenFOAMProject.",
)
@click.option(
    "-r",
    "--repo",
    required=True,
    type=str,
    help=(
        "Path to data repository. If this is a valid Github repository, files will be"
        " automatically added."
    ),
)
@click.option(
    "-s",
    "--skip-logs",
    required=False,
    is_flag=True,
    help=(
        "If set, .log files will not be archived. This does not affect .log files"
        " passed via the --file option."
    ),
)
@click.option(
    "-a",
    "--file",
    required=False,
    multiple=True,
    help="Path(s) to non-logfile(s) to be also added to the repository.",
)
@click.option(
    "--campaign",
    required=True,
    type=str,
    help="Specify the campaign",
)
@click.option(
    "--tag",
    required=False,
    type=str,
    help=(
        "Specify prefix of branch name. Will checkout new branch with timestamp"
        " <tag>-<timestamp>."
    ),
)
@click.option(
    "--amend",
    is_flag=True,
    required=False,
    help="Add to existing branch instead of creating new one.",
)
@click.option(
    "--push",
    required=False,
    is_flag=True,
    help="Push changes directly to origin and switch to previous branch.",
)
@click.option(
    "--dry-run",
    required=False,
    is_flag=True,
    help=(
        "If set, will log which files WOULD be copied and committed, without actually"
        " doing it."
    ),
)
@click.pass_context
def archive(ctx: click.Context, **kwargs):
    target_folder: Path = Path(kwargs.get("repo", "")).absolute()
    if current_path := kwargs.get("folder", "."):
        os.chdir(current_path)
        current_path = Path(current_path).absolute()

    # setup project and jobs
    project = OpenFOAMProject().init_project()
    filters: list[str] = kwargs.get("filter", [])
    # check if given path points to valid project
    if not is_valid_workspace(filters):
        return
    jobs = project.filter_jobs(filters)

    dry_run = kwargs.get("dry_run", False)
    branch_name = None
    previous_branch = None
    campaign = kwargs["campaign"]
    tag = kwargs.get("tag", "")
    # check if given path is actually a github repository
    use_git_repo = False
    try:
        repo = Repo(path=str(target_folder), search_parent_directories=True)
        previous_branch = repo.active_branch.name
        use_git_repo = True
    except InvalidGitRepositoryError:
        logging.warn(
            f"Given directory {target_folder=} is not a github repository. Will only"
            " copy files."
        )
    if use_git_repo:
        if kwargs.get("amend"):
            branches = [
                (branch.name[-16 : len(branch.name)], branch.name)
                for branch in repo.branches
                if branch.name.startswith(campaign)
            ]
            branches.sort()

            if not branches:
                # throw error, return
                logging.error(
                    f"Cannot amend to {campaign} branch. Existing"
                    f" branches include {repo.git.branch()}."
                )
                return
            branch_name = branches[-1][1]
            if dry_run:
                logging.info(f"Would amend to {branch_name}.")
            else:
                logging.info(f"Amending to {branch_name} branch")
                repo.git.checkout(branch_name)
        else:
            time_stamp = (
                str(datetime.now())
                .rsplit(":", 1)[0]
                .replace(" ", ":")
                .replace(":", "_")
            )
            branch_name = f"{campaign}/{time_stamp}"
            if dry_run:
                logging.info(f"Would checkout {branch_name}.")
            else:
                logging.info(f"checkout {branch_name}")
                repo.git.checkout("HEAD", b=branch_name)

    id_view_map = map_view_folder_to_job_id("view")

    # setup target folder
    if not target_folder.exists():
        if dry_run:
            logging.info(f"Would Create {str(target_folder)}")
        else:
            logging.info(f"creating {str(target_folder)}")
            target_folder.mkdir()

    skip = kwargs.get("skip_logs")
    if not skip:
        # iterate cases and copy log files into target repo
        for job in jobs:
            # copy signac state point
            signac_statepoint = Path(job.path) / "signac_statepoint.json"
            if not signac_statepoint.exists():
                continue
            target_file = target_folder / f"workspace/{job.id}/signac_statepoint.json"
            if dry_run:
                logging.info(f"Would copy {signac_statepoint} to {target_file}.")
            else:
                logging.debug(f"{target_folder}, {signac_statepoint}")
                copy_to_archive(repo, use_git_repo, signac_statepoint, target_file)

            # copy signac state point
            signac_job_document = Path(job.path) / "signac_job_document.json"
            if not signac_job_document.exists():
                continue

            md5sum = check_output(
                ["md5sum", str(signac_job_document)], text=True
            ).split()[0]
            target_file = (
                target_folder
                / f"workspace/{job.id}/signac_job_document_{md5sum}_{campaign}.json"
            )
            if dry_run:
                logging.info(f"Would copy {signac_job_document} to {target_file}.")
            else:
                logging.debug(f"{target_folder}, {signac_job_document}")
                copy_to_archive(repo, use_git_repo, signac_job_document, target_file)

            case_folder = Path(job.path) / "case"
            if not case_folder.exists():
                logging.info(f"Job with {job.id=} has no case folder.")
                continue

            # TODO: implement archival only of non-failed jobs
            # skip if either the most recent obr action failed or the label is set to "not success"
            # case = OpenFOAMCase(str(case_folder), job)
            # if not case.was_successful():
            #     logging.info(
            #         f"Skipping Job with {job.id=} due to recent failure states."
            #     )
            #     continue

            root, _, files = next(os.walk(case_folder))
            tags = "/".join(tag.split(","))
            campaign_target_path = (
                target_folder / f"workspace/{job.id}/{campaign}/{tags}"
            )
            for file in files:
                src_file = Path(root) / file
                if src_file.is_relative_to(current_path):
                    src_file = src_file.relative_to(current_path)
                if file.endswith("log"):
                    target_file = campaign_target_path / file
                    if target_file.is_relative_to(current_path):
                        target_file = target_file.relative_to(current_path)
                    if dry_run:
                        logging.info(f"Would copy {src_file} to {target_file}.")
                    else:
                        copy_to_archive(repo, use_git_repo, src_file, target_file)

            view_path = id_view_map.get(job.id)
            if view_path:
                view_path = target_folder / "view" / view_path / f"{campaign}/{tags}"
                archive_view(
                    repo, use_git_repo, campaign_target_path, view_path, target_folder
                )

            # copy CLI-passed files into data repo and add if possible
            extra_files: tuple[str] = kwargs.get("file", ())
            for file in extra_files:
                f = case_folder / file
                target_file = campaign_target_path / file
                if not f.exists():
                    logging.info(f"invalid path {f}. Skipping.")
                    continue
                if dry_run:
                    logging.info(f"Would copy {f} to {f.absolute}.")
                else:
                    copy_to_archive(repo, use_git_repo, f, target_file)

    # commit and push
    if use_git_repo and repo and branch_name:
        message = f"Add new logs -> {str(target_folder)}"
        author = Actor(repo.git.config("user.name"), repo.git.config("user.email"))
        logging.info(f"Actor with {author.conf_name=} and {author.conf_email=}")
        logging.info(
            f'config: {repo.git.config("user.name"), repo.git.config("user.email")}'
        )
        if dry_run:
            logging.info(
                f"Would commit changes to repo {repo.working_dir.rsplit('/',1)[1]} with"
                f" {message=} and remote name {repo.remote().name}"
            )

        else:
            logging.info(
                f"Committing changes to repo {repo.working_dir.rsplit('/',1)[1]} with"
                f" {message=} and remote name {repo.remote().name}"
            )
            try:
                repo.index.commit(message, author=author, committer=author)
                if kwargs.get("push"):
                    repo.git.push("origin", "-u", branch_name)
                    logging.info(f"Switching back to branch '{previous_branch}'")
                    repo.git.checkout(previous_branch)
            except Exception as e:
                logging.error(e)


def main():
    logging.basicConfig(
        format="[%(filename)s:%(lineno)d]\t%(levelname)7s: %(message)s",
        level=logging.INFO,
    )
    cli(obj={})


if __name__ == "__main__":
    cli(obj={})

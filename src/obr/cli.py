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
import re
import time

from .signac_wrapper.labels import *
from .signac_wrapper.operations import *
from .create_tree import create_tree


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option(
    "-p", "--pretend", is_flag=True, help="Set flag to only print submission script"
)
@click.option("-o", "--operation")
@click.option("--bundling", default=None)
@click.option("--bundling_match", is_flag=True)
@click.pass_context
def submit(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject().init_project()
    project._entrypoint = {"executable": "", "path": "obr"}
    # OpenFOAMProject().main()
    # print(dir(project.operations["runParallelSolver"]))
    # TODO find a signac way to do that
    bundling_key = kwargs["bundling"]
    if bundling_key:
        non_matching_jobs = [
            j for j in project if not bundling_key in list(j.sp.keys())
        ]
        bundling_set_vals = set(
            [j.sp[bundling_key] for j in project if bundling_key in list(j.sp.keys())]
        )

        if not kwargs["bundling_match"]:
            print("submit non matching jobs", non_matching_jobs)
            print(
                project.submit(
                    jobs=non_matching_jobs,
                    bundle_size=len(non_matching_jobs),
                    names=[kwargs.get("operation")],
                    **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
                )
            )

        if kwargs["bundling_match"]:
            print("submit matching jobs", non_matching_jobs)
            for bundle in bundling_set_vals:
                jobs = [j for j in project if bundle in list(j.sp.values())]
                print(f"submit bundle {bundle} of {len(jobs)} jobs")

                print(
                    "submission response",
                    project.submit(
                        jobs=jobs,
                        bundle_size=len(jobs),
                        names=[kwargs.get("operation")],
                        **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
                    ),
                )
                time.sleep(15)
    else:
        print("submit all jobs")
        print(
            project.submit(
                names=[kwargs.get("operation")],
                **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
            )
        )

    # print(project.scheduler_jobs(TestEnvironment.get_prefix(runSolver)))
    # print(list(project.scheduler_jobs(TestEnvironment.get_scheduler())))
    #


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-o", "--operations", default="")
@click.option("-j", "--job")
@click.option("--args", default="")
@click.option("-t", "--tasks", default=-1)
@click.option("-a", "--aggregate", is_flag=True)
@click.option("--query", default="")
@click.option("--args", default="")
@click.pass_context
def run(ctx, **kwargs):
    """Run specified operations"""
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject().init_project()
    queries_str = kwargs.get("query")
    queries = input_to_queries(queries_str)
    if queries:
        sel_jobs = query_impl(project, queries, output=False)
        jobs = [j for j in project if j.id in sel_jobs]
    else:
        jobs = [j for j in project]

    if kwargs.get("args"):
        os.environ["OBR_CALL_ARGS"] = kwargs.get("args")

    # project._reregister_aggregates()
    # print(project.groups)
    # val = list(project._groups.values())[0]
    # agg = project._group_to_aggregate_store[val]
    # print(type(project._group_to_aggregate_store[val]))
    # print(agg._aggregates_by_id)
    # jobs = project.groups["generate"]
    # print(list(project.groupby("doc.is_base")))
    if not kwargs.get("aggregate"):
        project.run(
            jobs=jobs,  # project.groupby("doc.is_base"),
            names=kwargs.get("operations").split(","),
            np=kwargs.get("tasks", -1),
        )
    else:
        # calling for aggregates does not work with jobs
        project.run(
            names=kwargs.get("operations").split(","),
            np=kwargs.get("tasks", -1),
        )
    print("[OBR] completed all operations")


def parse_variables(in_str: str, args: dict, domain: str):
    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        if not args.get(inst, ""):
            print(f"warning {inst} not defined")
        in_str = in_str.replace(
            "${{" + domain + "." + inst + "}}", args.get(inst, f"'{inst}'")
        )
    expr = re.findall(r"\${{([\'\"\= 0.-9()*+A-Za-z_>!]*)}}", in_str)
    for inst in expr:
        in_str = in_str.replace("${{" + inst + "}}", str(eval(inst)))
    return in_str


@cli.command()
@click.option(
    "-f", "--folder", default=".", help="Where to create the worspace and view"
)
@click.option("-e", "--execute", default=False)
@click.option("-c", "--config", help="Path to configuration file.")
@click.option("-t", "--tasks", default=-1, help="Number of tasks to run concurrently.")
@click.option("-u", "--url", default=None, help="Url to a configuration yaml")
@click.option("--verbose", default=0, help="set verbosity")
@click.pass_context
def init(ctx, **kwargs):
    import urllib.request

    if kwargs.get("url"):
        with urllib.request.urlopen(kwargs["url"]) as f:
            config_str = f.read().decode("utf-8")
    else:
        config_file = kwargs["config"]
        yaml_location = (Path(os.getcwd()) / config_file).parents[0]

        # load base yaml file
        with open(config_file, "r") as config_handle:
            config_str = config_handle.read()

        # search for includes
        includes = re.findall("[  ]*\${{include.[\w.]*}}", config_str)
        for include in includes:
            ws = " ".join(include.split(" ")[:-1])
            fn = ".".join(include.split(".")[1:]).replace("}", "")
            with open(yaml_location / fn, "r") as include_handle:
                include_str = ws + ws.join(include_handle.readlines())
            config_str = config_str.replace(include, include_str)

    config = yaml.safe_load(
        parse_variables(
            parse_variables(config_str, os.environ, "env"),
            {"location": str(yaml_location)},
            "yaml",
        )
    )

    if kwargs.get("verbose", 0) >= 1:
        print(config)

    project = OpenFOAMProject.init_project(root=kwargs["folder"])
    create_tree(project, config, kwargs)

    print("[OBR] successfully initialised")


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-d", "--detailed", is_flag=True)
@click.pass_context
def status(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject.get_project()
    project.print_status(detailed=kwargs["detailed"], pretty=True)


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-d", "--detailed", is_flag=True)
@click.option("-a", "--all", is_flag=True)
@click.option("-q", "--query")
@click.pass_context
def query(ctx, **kwargs):
    # TODO refactor
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject.get_project()
    queries_str = kwargs.get("query")
    queries = input_to_queries(queries_str)
    query_impl(project, queries, output=True, latest_only=not kwargs.get("all"))


def main():
    cli(obj={})


if __name__ == "__main__":
    cli(obj={})

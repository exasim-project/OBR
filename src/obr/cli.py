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
import yaml
import os
import re
import time

from signac_labels import *
from signac_operations import *


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
@click.option("-p", "--pretend", default=False)
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
                print(len(jobs))

                print(
                    project.submit(
                        jobs=jobs,
                        bundle_size=len(jobs),
                        names=[kwargs.get("operation")],
                        **{"partition": "cpuonly", "pretend": kwargs["pretend"]},
                    )
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


def filter_jobs(job, jid: str = None, filter: str = None) -> bool:
    import yaml

    if jid:
        return job.id == jid
    if filter:
        negate = filter.startswith("!")
        if negate:
            filter = filter.replace("!", "")

        d = yaml.safe_load(filter.replace(", ", "\n"))
        if negate:
            return not all([f"{k}: {v}" in str(job.sp) for k, v in d.items()])
        return all([f"'{k}': {v}" in str(job.sp) for k, v in d.items()])

    return True


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-o", "--operations", default="")
@click.option("-j", "--job")
@click.option("--args", default="")
@click.option("-t", "--tasks", default=-1)
@click.option("-a", "--aggregate", is_flag=True)
@click.option("--filter", default=None)
@click.option("--args", default="")
@click.pass_context
def run(ctx, **kwargs):
    """Run specified operations"""
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject().init_project()
    jobs = [
        j for j in project if filter_jobs(j, kwargs.get("job"), kwargs.get("filter"))
    ]

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


def parse_variables(in_str, args, domain):
    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        in_str = in_str.replace("${{" + domain + "." + inst + "}}", args.get(inst, ""))
    expr = re.findall(r"\${{([ 0-9()*+]*)}}", in_str)
    for inst in expr:
        in_str = in_str.replace("${{" + inst + "}}", str(eval(inst)))
    return in_str


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-e", "--execute", default=False)
@click.option("-c", "--config")
@click.option("-t", "--tasks", default=-1)
@click.option("-u", "--url", default=None)
@click.pass_context
def init(ctx, **kwargs):
    import obr_create_tree
    import urllib.request

    if kwargs.get("url"):
        with urllib.request.urlopen(kwargs["url"]) as f:
            config_str = f.read().decode("utf-8")
    else:
        config_file = kwargs["config"]
        with open(config_file, "r") as config_handle:
            config_str = config_handle.read()

    config = yaml.safe_load(
        parse_variables(
            parse_variables(config_str, os.environ, "env"),
            {"location": str((Path(os.getcwd()) / config_file).parents[0])},
            "yaml",
        )
    )

    project = OpenFOAMProject.init_project(root=kwargs["folder"])
    obr_create_tree.obr_create_tree(project, config, kwargs, config_file)


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option("-d", "--detailed", is_flag=True)
@click.pass_context
def status(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject.get_project()
    project.print_status(detailed=kwargs["detailed"], pretty=True)


def query_impl(project, queries, output=False):
    """ """
    docs = {}
    for job in project:
        if not job.doc.get("obr"):
            continue
        for key, value in job.doc.obr.items():
            docs.update({key: value})
        docs.update(job.sp)

    for key, value in docs.items():
        for q in queries:
            if "==" in q:
                q_key, q_value = q.split("==")
                q_value = q_value.replace(" ", "")
                q_key = q_key.replace(" ", "")
            else:
                q_key = q
                q_value = ""

            # is an operation just consider latest
            # execution for now
            if isinstance(value, list):
                value = value[-1]

            # is an operation just consider latest
            # execution for now
            if isinstance(value, dict):
                for operation_key, operation_value in value.items():
                    if operation_key == q_key and q_value in str(operation_value):
                        res.append(
                            {
                                job.id: (
                                    job.path,
                                    key,
                                    operation_key,
                                    operation_value,
                                )
                            }
                        )
            else:
                if key == q_key and q_value in str(value):
                    res.append({job.id: (job.path, key, value)})
    if output:
        for r in res:
            print(r)

    query_ids = []
    for id_ in res:
        query_ids.append(id_.values[0][0])

    return query_ids


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
    queries = kwargs.get("query").split(" and ")
    query_impl(project, queries, output=True)


def main():
    cli(obj={})


if __name__ == "__main__":
    cli(obj={})

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

from .signac_wrapper.labels import *
from .signac_wrapper.operations import *
from .create_tree import create_tree
from .core.parse_yaml import read_yaml
from .core.queries import input_to_queries, query_impl


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
@click.option("-o", "--operations", default="", required=True, help="Specify the operation(s) to run. Pass multiple operations after -o, separated by commata (NO space), e.g. obr run -o shell,apply. Run with --help to list available operations.")
@click.option("-l", "--list-operations", is_flag=True, help="Prints all available operations and returns.")
@click.option("--query", default=None, help="")
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
def submit(ctx, **kwargs):
    if kwargs.get("folder"):
        os.chdir(kwargs["folder"])

    project = OpenFOAMProject().init_project()
    project._entrypoint = {"executable": "", "path": "obr"}

    operations = kwargs.get('operations', "").split(',')
    # list available operations if none are specified or given the click option or an incorrect op is given
    if not operations:
        print('No operation(s) specified.')
        project.print_operations()
        print('Syntax: obr run [-o|--operation] <operation>(,<operation>)+')
        return
    elif any((false_op := op) not in project.operations for op in operations):
        print(f'Specified operation {false_op} is not a valid operation.')
        project.print_operations()
        return
    elif kwargs.get('list_operations'):
        project.print_operations()
        return

    queries_str = kwargs.get("query")
    bundling_key = kwargs.get("bundling_key")
    partition = kwargs.get("partition")
    account = kwargs.get("account")

    if queries_str:
        queries = input_to_queries(queries_str)
        sel_jobs = query_impl(project, queries, output=False)
        jobs = [j for j in project if j.id in sel_jobs]
    else:
        jobs = [j for j in project]

    # OpenFOAMProject().main()
    # print(dir(project.operations["runParallelSolver"]))
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

    if bundling_key:
        bundling_values = get_values(jobs, bundling_key)
        for bundle_value in bundling_values:
            jobs = [j for j in project if bundle_value in list(j.sp().values())]
            print(f"[OBR] submit bundle {bundle_value} of {len(jobs)} jobs")
            print(
                "[OBR] submission response",
                project.submit(
                    jobs=jobs,
                    bundle_size=len(jobs),
                    names=[kwargs.get("operation")],
                    **cluster_args,
                ),
            )
            time.sleep(15)
    else:
        print(f"[OBR] submitting {len(jobs)} individual jobs")
        print(
            project.submit(
                names=[kwargs.get("operation")],
                **cluster_args,
            )
        )

    # print(project.scheduler_jobs(TestEnvironment.get_prefix(runSolver)))
    # print(list(project.scheduler_jobs(TestEnvironment.get_scheduler())))
    #


@cli.command()
@click.option("-f", "--folder", default=".")
@click.option(
    "-o",
    "--operations",
    default="",
    required=True,
    help="Specify the operation(s) to run. Pass multiple operations after -o, separated by commata (NO space), e.g. obr run -o shell,apply. Run with --help to list available operations.",
)
@click.option(
    "-l",
    "--list-operations",
    is_flag=True,
    help="Prints all available operations and returns.",
)
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

    operations = kwargs.get('operations', "").split(',')
    # list available operations if none are specified or given the click option or an incorrect op is given
    if not operations:
        print('No operation(s) specified.')
        project.print_operations()
        print('Syntax: obr run [-o|--operation] <operation>(,<operation>)+')
        return
    elif any((false_op := op) not in project.operations for op in operations):
        print(f'Specified operation {false_op} is not a valid operation.')
        project.print_operations()
        return
    elif kwargs.get('list_operations'):
        project.print_operations()
        return

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
    print("[OBR] completed all operations")


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
    config_str = read_yaml(kwargs)
    config_str = config_str.replace("\n\n", "\n")
    config = yaml.safe_load(config_str)

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

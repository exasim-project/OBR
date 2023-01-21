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

import flow
import signac
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
@click.option("--folder")
@click.option("--filter", default=None)
@click.option("--select", default=None)
@click.option("--force", default=False)
@click.pass_context
def decompose(ctx, **kwargs):
    import obr_decompose_tree

    obr_decompose_tree.decompose_tree(kwargs)


@cli.command()
@click.option("--folder", default="cases")
@click.option("--results_folder", default="results", help="folder to store results")
@click.option("--report", default="report.csv")
@click.option("--filter", default=None)
@click.option("--select", default=None)
@click.option("--continue_on_failure", default=True)
@click.option("--time_runs", default=3600)
@click.option("--min_runs", default=1)
@click.option("--single_run", default=True)
@click.option("--fail_on_error", default=False)
@click.option("--log_name", default="logs")
@click.option("--mpi_flags", default="logs")
@click.option("--runner", default="LocalCaseRunner")
@click.option("--partition")
@click.option("--mem")
@click.option("--time")
@click.option("--ntasks_per_node")
@click.pass_context
def benchmark(ctx, **kwargs):
    import obr_benchmark_cases

    obr_benchmark_cases.benchmark_cases(kwargs)


@cli.command()
@click.option("--folder", default="cases")
@click.option("--operations")
@click.pass_context
def execute(ctx, **kwargs):
    project = OpenFOAMProject.init_project(root=kwargs["folder"])
    project.run(names=kwargs.get("operations", "").split(","))


@cli.command()
@click.option("--folder", default="cases")
@click.option("--execute", default=True)
@click.option("--parameters", default="base")
@click.pass_context
def create(ctx, **kwargs):
    import obr_create_tree

    config_file = kwargs["parameters"]

    with open(config_file, "r") as config_handle:
        config = yaml.safe_load(config_handle)

    project = OpenFOAMProject.init_project(root=kwargs["folder"])
    obr_create_tree.obr_create_tree(project, config, kwargs)


@cli.command()
@click.option("--folder", default="cases")
@click.option("--detailed", default=False)
@click.pass_context
def status(ctx, **kwargs):
    import obr_create_tree

    project = OpenFOAMProject.get_project(root=kwargs["folder"])
    project.print_status(detailed=kwargs["detailed"], pretty=True)


@cli.command()
@click.option("--folder", default="cases")
@click.pass_context
def find(ctx, **kwargs):
    import obr_create_tree

    project = OpenFOAMProject.get_project(root=kwargs["folder"])
    for job in project:

        for operation, data in job.doc.obr.items():
            if data["state"] == "failure":
                print(
                    f"job {job.path} operation {operation} failed with:{os.linesep} {data['log']}"
                )
                # using the job.id we can find jobs which have this job as child
                print(list(job.doc.obr.keys()), job.sp)


def main():
    cli(obj={})


if __name__ == "__main__":
    cli(obj={})

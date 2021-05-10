#!/usr/bin/python
"""
    run ogl benchmarks

    Usage:
        runBenchmark.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --folder=<folder>   Target folder  [default: Test].
        --report=<filename> Target file to store stats [default: report.csv].
        --omp_max_threads=<n>  Set the number of omp threads [default: 1].
        --clean             Remove existing cases [default: False].
        --backend=BACKENDS  Select desired backends (e.g. OF,GKO)
        --solver=SOLVER     Select desired solvers (e.g. CG,BiCGStab,IR,smooth)
        --executor=EXECUTOR Select desired executor (e.g. CUDA,Ref,OMP)
        --preconditioner=PRECONDS  Select desired preconditioner (e.g. BJ,DIC)
        --mpi_max_procs=<n>  Set the number of mpi processes [default: 1].
        --field=FIELD       Set the field name to apply setup
        --test-run          Run every case only once [default: False]
        --small-cases       Include small cases [default: False].
        --large-cases       Include large cases [default: False].
        --very-large-cases  Include large cases [default: False].
        --min_runs=<n>      Number of applications runs [default: 5]
        --time_runs=<s>     Time to applications runs [default: 60]
        --fail_on_error     exit benchmark when a run fails [default: False]
        --project_path=<folder> Path to library which is benchmarked
"""

from docopt import docopt
from subprocess import check_output
from pathlib import Path
import os
import shutil
import datetime
from itertools import product, starmap
from functools import partial

from pathlib import Path
from OBR import Case as cs
from OBR import ParameterStudy as ps
from OBR import CaseRunner as cr
from OBR import ResultsAggregator as ra


def get_commit_id(path):
    return (
        check_output(["git", "rev-parse", "--short", "HEAD"], cwd=path)
        .decode("utf-8")
        .replace("\n", "")
    )


def resolution_study(test_path, solver, arguments, runner, fields):

    number_of_cells = []

    if arguments["--small-cases"]:
        number_of_cells += [8, 16]

    if arguments["--large-cases"]:
        number_of_cells += [32, 64]

    if arguments["--very-large-cases"]:
        number_of_cells += [128, 256]

    case_name = "boxTurb16"
    root = ps.OpenFOAMTutorialCase("DNS", "dnsFoam", case_name)

    cell_setters = [
        ps.CellSetter(test_path, num_cells, case_name, root, fields)
        for num_cells in number_of_cells
    ]

    parameter_study = ps.ParameterStudy(
        test_path, results, [cell_setters, solver], runner
    )

    parameter_study.build_parameter_study()


if __name__ == "__main__":

    arguments = docopt(__doc__, version="runBench 0.1")
    print(arguments)

    solver = arguments["--solver"].split(",")
    domains = arguments["--backend"].split(",")
    preconditioner = arguments["--preconditioner"].split(",")
    executor = arguments["--executor"].split(",")
    fields = arguments["--field"].split(",")

    extra_args = {"OMP": {"max_processes": int(arguments["--omp_max_threads"])}}

    # for do a partial apply field="p"
    test_path = Path(arguments.get("--folder", "Test"))
    construct = partial(ps.construct, test_path, "boxTurb16", fields, extra_args)

    # construct returns a tuple where  the first element is bool
    # indicating a valid combination of Domain and Solver and Executor
    valid_solvers_tuples = filter(
        lambda x: x[0],
        starmap(
            construct,
            product(solver, domains, executor, preconditioner),
        ),
    )
    # just unpack the solver setters to a list
    solvers = map(lambda x: x[1], valid_solvers_tuples)

    results = ra.Results(
        arguments.get("--report", "report.csv"),
        fields,
        commit=get_commit_id(Path(arguments["--project_path"])),
    )
    runner = cr.CaseRunner(
        solver="dnsFoam", results_aggregator=results, arguments=arguments
    )

    resolution_study(test_path, solvers, arguments, runner, fields)

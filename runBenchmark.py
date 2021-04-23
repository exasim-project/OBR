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
        --of                Generate OF cases [default: False].
        --gko               Generate GKO cases [default: False].
        --ref               Generate ref cases [default: False].
        --cuda              Generate cuda cases [default: False].
        --omp               Generate omp cases [default: False].
        --omp_max_threads=<n>  Set the number of omp threads [default: 1].
        --clean             Remove existing cases [default: False].
        --cg                Use CG matrix solver [default: False].
        --ir                Use Ginkgos IR matrix solver [default: False].
        --bicgstab          Use BiCGStab matrix solver [default: False].
        --smooth            Use OpenFOAMs smooth solver [default: False].
        --mpi_max_procs=<n>  Set the number of mpi processes [default: 1].
        --small-cases       Include small cases [default: False].
        --large-cases       Include large cases [default: False].
        --very-large-cases  Include large cases [default: False].
        --min_runs=<n>      Number of applications runs [default: 5]
        --time_runs=<s>      Time to applications runs [default: 60]
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


def resolution_study(test_path, solver, arguments, runner):

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
        ps.CellSetter(test_path, num_cells, case_name, root)
        for num_cells in number_of_cells
    ]

    parameter_study = ps.ParameterStudy(
        test_path, results, [cell_setters, solver], runner
    )

    parameter_study.build_parameter_study()


if __name__ == "__main__":

    arguments = docopt(__doc__, version="runBench 0.1")
    print(arguments)

    solver = []

    if arguments["--ir"]:
        solver.append("IR")

    if arguments["--cg"]:
        solver.append("CG")

    if arguments["--bicgstab"]:
        solver.append("BiCGStab")

    if arguments["--smooth"]:
        solver.append("smooth")

    executor = []

    if arguments["--cuda"]:
        executor.append("CUDA")

    if arguments["--ref"]:
        executor.append("Ref")

    if arguments["--omp"]:
        executor.append("OMP")

    domains = []
    if arguments["--of"]:
        domains.append("OF")

    if arguments["--gko"]:
        domains.append("GKO")

    # for do a partial apply field="p"
    test_path = Path(arguments.get("--folder", "Test"))
    construct = partial(ps.construct, test_path, "boxTurb16", "p")
    # construct returns a tuple where  the first element is bool
    # indicating a valid combination of Domain and Solver and Executor
    valid_solvers_tuples = filter(
        lambda x: x[0], starmap(construct, product(solver, domains, executor))
    )
    # just unpack the solver setters to a list
    solvers = map(lambda x: x[1], valid_solvers_tuples)

    results = ra.Results(arguments.get("--report", "report.csv"))
    runner = cr.CaseRunner(
        solver="dnsFoam", results_aggregator=results, arguments=arguments
    )

    resolution_study(test_path, solvers, arguments, runner)

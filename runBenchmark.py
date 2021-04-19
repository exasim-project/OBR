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
        --of                Generate default of cases [default: False].
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
from itertools import product

from pathlib import Path
from OBR import Case as cs
from OBR import ParameterStudy as ps
from OBR import ResultsAggregator as ra

def resolution_study(test_path, solver, arguments, runner):

    number_of_cells = []

    if arguments["--small-cases"]:
        number_of_cells += [8, 16]

    if arguments["--large-cases"]:
        number_of_cells += [32, 64]

    if arguments["--very-large-cases"]:
        number_of_cells += [128, 256]

    root = ps.OpenFOAMTutorialCase("DNS", "dnsFoam", "boxTurb16")

    cell_setters = [ps.CellSetter(num_cells) for num_cells in number_of_cells]

    for cell_setter in cell_setters:
        cell_setter.set_root_case(root)

    parameter_study = ps.ParameterStudy(test_path, results, [cell_setters, solver], runner)
    parameter_study.build_parameter_study()


class IR:
    def __init__(self):
        self.OF = False
        self.GKO = True
        self.base = True
        self.name = "IR"


class CG:
    def __init__(self):
        self.OF = True
        self.GKO = True
        self.base = True
        self.name = "CG"


class BiCGStab:
    def __init__(self):
        self.OF = True
        self.base = True
        self.GKO = True
        self.name = "BiCGStab"


class smoothSolver:
    def __init__(self):
        self.base = True
        self.OF = True
        self.GKO = False
        self.name = "smoothSolver"


if __name__ == "__main__":

    arguments = docopt(__doc__, version="runBench 0.1")
    print(arguments)

    solvers = []

    if arguments["--ir"]:
        solvers.append(IR())

    if arguments["--cg"]:
        solvers.append(CG())

    if arguments["--bicgstab"]:
        solvers.append(BiCGStab())

    if arguments["--smooth"]:
        solvers.append(smoothSolver())

    preconditioner = []

    if arguments["--cuda"]:
        pass

    if arguments["--of"]:
        pass

    if arguments["--ref"]:
        pass

    if arguments["--omp"]:
        pass


    test_path = Path(arguments.get("--folder", "Test")) / "name"

    results = ra.Results(arguments.get("--report", "report.csv"))
    runner = ps.CaseRunner("dnsFoam", test_path, results, arguments)

    ofcg = ps.OFCG("p")
    gkocg = ps.GKOCG(gko_executor=ps.OMP(), field="p")
    resolution_study(test_path, [ofcg, gkocg], arguments, runner)

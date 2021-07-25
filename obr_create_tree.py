#!/usr/bin/python
"""
    run ogl benchmarks

    Usage:
        runBenchmark.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --clean             Remove existing cases [default: False].
        --parameters=<json> pass the parameters for given parameter study
        --folder=<folder>   Target folder  [default: Test].
"""

from docopt import docopt
import json

from pathlib import Path
from OBR import ParameterStudyTree as ps
from OBR import CaseOrigins as co
from OBR import setFunctions as sf


def process_benchmark_description(fn, metadata, supported_file_version="0.1.0"):
    import sys
    from packaging import version

    # read benchmark description file
    with open(fn, "r") as parameters_handle:
        parameters_str = parameters_handle.read()

    # parse file
    parameter_study_arguments = json.loads(parameters_str)

    if parameter_study_arguments["obr"]["OBR_MIN_VERSION"] > metadata["OBR_VERSION"]:
        print("The benchmark file needs a more recent version of OBR")
        sys.exit(-1)
    if (
        parameter_study_arguments["obr"]["BENCHMARK_FILE_VERSION"]
        < supported_file_version
    ):
        print("The benchmark file version is no longer supported")
        sys.exit(-1)
    return parameter_study_arguments


if __name__ == "__main__":
    metadata = {
        "OBR_REPORT_VERSION": "0.1.0",
        "OBR_VERSION": "0.2.0",
        "node_data": {
            "host": sf.get_process(["hostname"]),
            "top": sf.get_process(["top", "-bn1"]).split("\n")[:15],
            "uptime": sf.get_process(["uptime"]),
        },
    }

    arguments = docopt(__doc__, version=metadata["OBR_VERSION"])

    parameter_study_arguments = process_benchmark_description(
        arguments.get("--parameters", "benchmark.json"), metadata
    )

    pst = ps.ParameterStudyTree(
        Path(arguments["--folder"]),
        parameter_study_arguments["variation"],
        base=getattr(co, parameter_study_arguments["case"]["type"])(
            parameter_study_arguments["case"]
        ),
    )

    pst.set_up()

    # extra_args = {"OMP": {"max_processes": int(arguments.get("--omp_max_threads", 1))}}

    # # for do a partial apply field="p"
    # test_path = Path(arguments.get("--folder", "Test"))

    # renumber = arguments.get("--renumber", False)
    # metadata["case"] = {"renumbered": renumber}

    # # if "MPI" in arguments.get("--executor"):
    # #     parameter_study_arguments["variation"]["decomposeMesh"] = True

    # parameter_study_arguments["variation"]["renumberMesh"] = renumber

    # results = ra.Results(
    #     arguments.get("--report", "report.csv"),
    #     fields,
    # )

    # results.write_comment([str(metadata)])

    # runner = cr.CaseRunner(
    #     solver=parameter_study_arguments["openfoam"]["solver"],
    #     results_aggregator=results,
    #     arguments=arguments,
    # )

    # case_name = parameter_study_arguments["openfoam"]["case"]
    # solver_stubs = parameter_study_arguments["openfoam"]["solver_stubs"]
    # construct = partial(
    #     ps.construct, test_path, case_name, fields, solver_stubs, extra_args
    # )

    # # construct returns a tuple where the first element is bool
    # # indicating a valid combination of Domain and Solver and Executor
    # valid_solvers_tuples = filter(
    #     lambda x: x[0],
    #     starmap(
    #         construct,
    #         product(solver, backend, executor, preconditioner),
    #     ),
    # )

    # # just unpack the solver setters to a list
    # matrix_solver = map(lambda x: x[1], valid_solvers_tuples)

    # parameter_study(test_path, matrix_solver, runner, fields, parameter_study_arguments)

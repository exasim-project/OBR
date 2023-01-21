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
        --init=<ts>         Run the base case for ts timesteps [default: 100].
"""

from docopt import docopt
import json
import os
import shutil
import re
import sys

from pathlib import Path
import ParameterStudyTree as ps
import CaseOrigins as co
import setFunctions as sf
from OpenFOAMCase import OpenFOAMCase
from metadata import versions


def parse_variables(in_str, args, domain):
    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        in_str = in_str.replace("${{" + domain + "." + inst + "}}", args.get(inst, ""))
    return in_str


def process_benchmark_description(fn, metadata, supported_file_version="0.3.0"):
    import sys
    from packaging import version

    # read benchmark description file
    fn = Path(fn).expanduser()
    with open(fn, "r") as parameters_handle:
        parameters_str = parameters_handle.read()

    lines = parameters_str.split("\n")
    cleaned = []

    for line in lines:
        if not line:
            continue
        cleaned.append(parse_variables(line, os.environ, "env"))

    parameters_str = "\n".join(cleaned)

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


def obr_create_tree(project, config, arguments):

    if not os.environ.get("FOAM_ETC"):
        print("[OBR] Error OpenFOAM not sourced")
        sys.exit(-1)

    # TODO figure out how operations should be handled for statepoints
    base_case_dict = {"case": config["case"]["type"]}
    of_case = project.open_job(base_case_dict)
    of_case.doc["is_base"] = True
    of_case.doc["parameters"] = config["case"]
    of_case.doc["pre_build"] = config["case"].get("pre_build", [])
    of_case.doc["post_build"] = config["case"].get("post_build", [])
    of_case.init()
    base_id = of_case.id

    operations = []
    id_path_mapping = {of_case.id: "base/"}

    def add_variations(variations, base, base_dict):
        for operation in variations:
            key = list(operation["values"].keys())[0]
            for value in operation["values"][key]:
                sub_variation = operation.get("variation")
                base_dict.update(
                    {
                        "case": config["case"]["type"],
                        "operation": operation["operation"],
                        key: value,
                        "value": value,
                        "args": key,
                        "has_child": True if sub_variation else False,
                    }
                )
                job = project.open_job(base_dict)
                job.doc["base_id"] = base
                job.doc["parameters"] = operation.get("parameters", [])
                job.doc["pre_build"] = operation.get("pre_build", [])
                job.doc["post_build"] = operation.get("post_build", [])
                job.init()
                print(key, value)
                print(job.id)
                id_path_mapping[job.id] = id_path_mapping.get(
                    base, ""
                ) + "{}/{}/".format(key, value)
                if sub_variation:
                    add_variations(sub_variation, job.id, base_dict)
            operations.append(operation.get("operation"))

    add_variations(config["variation"], base_id, base_case_dict)

    operations = list(set(operations))
    if arguments.get("execute"):
        project.run(names=["fetch_case"])
        project.run(names=operations)

    if not (Path(arguments["folder"]) / "view").exists():
        # FIXME this copies to views instead of linking
        project.find_jobs(filter={"has_child": False}).export_to(
            arguments["folder"],
            path=lambda job: "view/" + id_path_mapping[job.id],
            copytree=lambda src, dst: shutil.copytree(src, dst, symlinks=True),
        )

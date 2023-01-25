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
from collections.abc import MutableMapping
from copy import deepcopy

from pathlib import Path
import ParameterStudyTree as ps
import CaseOrigins as co
import setFunctions as sf
from OpenFOAMCase import OpenFOAMCase
from metadata import versions
from subprocess import check_output


def obr_create_tree(project, config, arguments):

    if not os.environ.get("FOAM_ETC"):
        print("[OBR] Error OpenFOAM not sourced")
        sys.exit(-1)

    # TODO figure out how operations should be handled for statepoints
    base_case_dict = {"case": config["case"]["type"], "has_child": True}
    of_case = project.open_job(base_case_dict)
    of_case.doc["is_base"] = True
    of_case.doc["parameters"] = config["case"]
    of_case.doc["pre_build"] = config["case"].get("pre_build", [])
    of_case.doc["post_build"] = config["case"].get("post_build", [])
    of_case.init()

    operations = []
    id_path_mapping = {of_case.id: "base/"}

    def flatten(d, parent_key="", sep="/"):
        items = []
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(flatten(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def add_variations(variation, parent_job, base_dict):
        base = parent_job.id
        for operation in variation:
            sub_variation = operation.get("variation")
            key = operation.get("key", None)
            parent = operation.get("parent", {})
            if parent:
                if not dict(parent.items() & parent_job.sp.items()):
                    continue

            for value in operation["values"]:
                if not key:
                    path = operation["schema"].format(**flatten(value)) + "/"
                    args = value
                    keys = list(value.keys())
                else:
                    args = {key: value}
                    path = "{}/{}/".format(key, value)
                    keys = [key]

                base_dict.update(
                    {
                        "case": config["case"]["type"],
                        "operation": operation["operation"],
                        "has_child": True if sub_variation else False,
                        **args,
                    }
                )
                job = project.open_job(base_dict)
                job.doc["base_id"] = base
                job.doc["keys"] = keys
                job.doc["parameters"] = operation.get("parameters", [])
                job.doc["pre_build"] = operation.get("pre_build", [])
                job.doc["post_build"] = operation.get("post_build", [])
                job.init()
                path = path.replace(" ", "_").replace("(", "").replace(")", "")
                path = path.split(">")[-1]
                id_path_mapping[job.id] = id_path_mapping.get(base, "") + path
                if sub_variation:
                    add_variations(sub_variation, job, base_dict)
            operations.append(operation.get("operation"))

    add_variations(config["variation"], of_case, base_case_dict)

    operations = list(set(operations))

    if arguments.get("execute"):
        project.run(names=["fetch_case"])
        project.run(names=operations, np=arguments.get("tasks", -1))

    def ln(src, dst):
        src = Path(src)
        dst = Path(dst)
        check_output(["ln", "-s", src, dst])

    if not (Path(arguments["folder"]) / "view").exists():
        # FIXME this copies to views instead of linking
        project.find_jobs(filter={"has_child": False}).export_to(
            arguments["folder"],
            path=lambda job: "view/" + id_path_mapping[job.id],
            copytree=lambda src, dst: ln(src, dst),
        )

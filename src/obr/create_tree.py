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

import os
import sys
import hashlib

from collections.abc import MutableMapping
from pathlib import Path
from subprocess import check_output

from obr.signac_wrapper.operations import OpenFOAMProject


def flatten(d, parent_key="", sep="/"):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def get_path_from(operation: dict, value) -> str:
    if not operation.get("schema"):
        print(
            """Error Schema missing for

Set schema to allow creating views
        """
        )
        raise KeyError

    return operation["schema"].format(**flatten(value)) + "/"


def extract_from_operation(operation, value):
    """takes an operation"""
    key = operation.get("key", "").replace(".", "_dot_")
    if not key:
        path = get_path_from(operation, value)
        args = value
        keys = list(value.keys())
    else:
        args = {key: value}
        # if operation is shell take only script name instead of full path
        if operation.get("operation") == "shell":
            key_ = str(Path(key.replace("_dot_", ".")).parts[-1])
        else:
            key_ = key
        path = "{}/{}/".format(key_, value)
        keys = [key]

    return keys, path, args


def generate_view(
    project: OpenFOAMProject, workspace: Path, view_path: Path, id_path_mapping: dict
):
    """
    Parameters:
        - workspace: folder that contains the workspace folder
        - view_path: path where the view should be created
        - id_path_mapping: dictionary from job.id to relative path name
    """

    def ln(src, dst):
        src = Path(src)
        dst = Path(dst)
        check_output(["ln", "-s", src, dst])

    if (view_path).exists():
        check_output(["rm", "-rf", str(view_path)])

    if not id_path_mapping:
        return

    project.find_jobs(filter={"has_child": False}).export_to(
        str(workspace),
        path=lambda job: "view/" + id_path_mapping[job.id],
        copytree=lambda src, dst: ln(src, dst),
    )


def is_on_requested_parent(operation, parent_job) -> bool:
    """Check if operation requests to be on specific parent


    Returns true if either on correct parent job or no parent was requested
    """
    requests_parent = operation.get("parent", {})

    # no parent job specified
    if not requests_parent:
        return True

    intersect_keys = requests_parent.keys() & parent_job.sp.keys()
    intersect_dict = {
        k: requests_parent[k]
        for k in intersect_keys
        if requests_parent[k] == parent_job.sp[k]
    }
    # Filter out variations that have not the specified parent statepoint
    # does not work on python 3.8
    # if not dict(parent.items() & parent_job.sp.items()):
    #    continue

    if intersect_dict:
        return True
    return False


def clean_path(path_name: str) -> str:
    """Clean path name"""

    path = path_name.replace(" ", "_").replace("(", "").replace(")", "")
    path = path.split(">")[-1]

    return path


def to_dict(synced_dict) -> dict:
    return {k: v for k, v in synced_dict.items()}


def add_variations(
    operations: list,
    project: OpenFOAMProject,
    variation: dict,
    parent_job,
    id_path_mapping: dict,
) -> list:
    """Recursively adds variations to the project"""
    for operation in variation:
        sub_variation = operation.get("variation")

        if not is_on_requested_parent(operation, parent_job):
            continue

        for value in operation["values"]:
            # support if statetment when values are a subdictionary
            if isinstance(value, dict) and not value.get("if", True):
                continue

            # derive path name from schema or key value
            keys, path, args = extract_from_operation(operation, value)
            path = clean_path(path)
            base_dict = to_dict(parent_job.sp)

            base_dict.update(
                {
                    "operation": operation["operation"],
                    "has_child": True if sub_variation else False,
                    **args,
                }
            )

            job = project.open_job(base_dict)
            setup_job_doc(job, parent_job.id, operation, keys, value)
            job.init()

            id_path_mapping[job.id] = id_path_mapping.get(parent_job.id, "") + path

            if sub_variation:
                operations = add_variations(
                    operations, project, sub_variation, job, id_path_mapping
                )

        operations.append(operation.get("operation"))
    return operations


def setup_job_doc(job, base_id, operation, keys: list, value, reset=False):
    """Sets basic information in the job document"""

    # we compute an opertation hash since not all
    # paramters go into the job statepoint
    h = hashlib.new("md5")
    h.update((str(operation) + str(value)).encode())
    operation_hash = h.hexdigest()
    doc_operation_hash = job.doc.get("operation_hash")

    if doc_operation_hash == operation_hash and not reset:
        return

    # dont overwrite old job state on init so that we can update a tree without
    # triggering rerunning operations
    if job.doc.get("state") == "ready":
        return

    # set up the hash of the operation
    job.doc["operation_hash"] = operation_hash

    # the job.id of the case from which the current
    # job has been derived
    job.doc["base_id"] = base_id

    # store the keys here since the job.sp constantly expands
    # that way we can check the specific keys from this operation
    job.doc["keys"] = keys

    # list of pre and post build operations
    job.doc["pre_build"] = operation.get("pre_build", [])
    job.doc["post_build"] = operation.get("post_build", [])

    job.doc["state"] = ""


def create_tree(
    project: OpenFOAMProject,
    config: dict,
    arguments: dict,
    skip_foam_src_check: bool = False,
):
    if not skip_foam_src_check and not os.environ.get("FOAM_ETC"):
        print("[OBR] Error OpenFOAM not sourced")
        sys.exit(-1)

    # Add base case
    base_case_state = {"has_child": True}
    base_case_state.update({k: v for k, v in config["case"].items()})
    of_case = project.open_job(base_case_state)

    setup_job_doc(
        of_case, None, config["case"], keys=list(config["case"].keys()), value=[]
    )

    of_case.doc["state"] = "ready"
    of_case.init()

    operations: list = []
    id_path_mapping = {of_case.id: "base/"}
    operations = add_variations(
        operations,
        project,
        config.get("variation", {}),
        of_case,
        id_path_mapping,
    )

    operations = list(set(operations))

    if arguments.get("execute"):
        project.run(names=["fetch_case"])
        project.run(names=operations, np=arguments.get("tasks", -1))

    generate_view(
        project,
        arguments["folder"],
        Path(arguments["folder"]) / "view",
        id_path_mapping,
    )

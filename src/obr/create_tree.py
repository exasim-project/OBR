import os
import sys

from collections.abc import MutableMapping
from pathlib import Path
from subprocess import check_output
from signac.job import Job
from obr.signac_wrapper.operations import OpenFOAMProject
from obr.core.queries import statepoint_query
from obr.core.parse_yaml import eval_generator_expressions
from obr.core.logger_setup import logger
from copy import deepcopy


def flatten(d, parent_key="", sep="/"):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def get_path_from(operation: dict, value: dict) -> str:
    """Derive a view path from schema and the value dict

    Returns: a view path as string
    """
    if not operation.get("schema"):
        logger.error("Error Schema missing for Set schema to allow creating views")
        raise KeyError

    return operation["schema"].format(**flatten(value)) + "/"


def extract_from_operation(operation: dict, value) -> dict:
    """takes an operation dictionary and do some processing
    It extracts keys path and args from the operation dictionary
    based on given value. The passed value is used as a selector
    to create keys path and args.

    - args are later used to pass it to the selected operation,
    either the operation contains:
    1. {key: key, values: [v1, v2, ...]} or
    2. {values: [{k:v1},{k:v2}] }
    2. {common: {c1:v1, c2:v2}, values: [{k:v1},{k:v2}] }

    -  the path is derived from the schema key value pair
    a entry {schema: path/{foo}, values: [{foo: 1}]} will be formatted
    to path/1

    Returns: a dictionary with keys, path and args
    """
    key = operation.get("key", "").replace(".", "_dot_")
    common = operation.get("common", {})
    if isinstance(value, dict) and common:
        value.update(common)
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

    return {"keys": keys, "path": path, "args": args}


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
        dst = Path(dst).absolute()
        relpath = os.path.relpath(src, dst)
        # for some reason the relpath has one ../ too much
        relpath = relpath[3:]
        dst.symlink_to(relpath)

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


def expand_generator_block(operation):
    """given an operation this function"""
    # check if we have a generator
    if generator := operation.get("generator"):
        if not (templates := generator.get("template")):
            raise AssertionError("No template section given.")
        if not (values := generator.get("values")):
            raise AssertionError("No value section given.")
        if not (key := generator.get("key")):
            raise AssertionError("No key given.")

        template_generated = []
        for val in values:
            # templates are a list of records
            # every record needs to be scanned and updated
            for template in templates:
                # template records need to be replaced
                # i.e. { numberOfSubdomains : foo, key: value}
                # by whatever key and value specify
                gen_dict = {}
                # next k, v are the key values from the template record
                # not to confused with the key value pair from the generator block
                for k, v in template.items():
                    if isinstance(v, str):
                        gen_dict[k] = v.replace(key, str(val))
                    # additionally the original key and current
                    # val are added so that we can use it in schemas
                    gen_dict[key] = val
                template_generated.append(gen_dict)
        return template_generated
    return operation["values"]


def add_variations(
    operations: list,
    project: OpenFOAMProject,
    variation: list,
    parent_job: Job,
    id_path_mapping: dict,
) -> list[str]:
    """Recursively adds variations to the project and initialises the jobs. This
    creates the workspace/uid folder and signac files as sideeffect.

    Returns: A list of all operation names
    """
    for operation in variation:
        sub_variation = operation.get("variation", {})

        if not is_on_requested_parent(operation, parent_job):
            continue

        values = expand_generator_block(operation)

        for value in values:
            # support if statetment when values are a subdictionary
            if isinstance(value, dict) and not value.get("if", True):
                continue

            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, str):
                        value[k] = eval_generator_expressions(v)

            # derive path name from schema or key value
            parse_res = extract_from_operation(operation, value)

            # filter any if statements from operation dict
            parse_res["keys"] = [k for k in parse_res["keys"] if k != "if"]
            parse_res["args"] = {
                k: v for k, v in parse_res["args"].items() if k != "if"
            }

            clean_path(parse_res["path"])
            base_dict = deepcopy(to_dict(parent_job.sp))

            statepoint = {
                "keys": parse_res["keys"],
                "parent_id": parent_job.id,
                "operation": operation["operation"],
                "has_child": True if sub_variation else False,
                "pre_build": operation.get("pre_build", []),
                "post_build": operation.get("post_build", []),
                **parse_res["args"],
            }
            statepoint["parent"] = base_dict

            # check for statepoint filters
            skip = False
            if (
                isinstance(value, dict)
                and value.get("if", False)
                and isinstance(value["if"], list)
            ):
                for filter_record in value["if"]:
                    predicate = filter_record.pop("predicate", "==")
                    if len(filter_record) != 1:
                        raise AssertionError(
                            "Exact one key-value pair is required for an if record"
                        )
                    key, value = list(filter_record.items())[0]
                    skip = not statepoint_query(statepoint, key, value, predicate)
                    if skip:
                        logger.debug(
                            f"skipping generating statepoint {statepoint} because of"
                            f" {key}=={value} filter"
                        )
                        break
                if skip:
                    continue

            job = project.open_job(statepoint)
            setup_job_doc(job)
            job.init()
            job.doc["state"]["global"] = ""

            id_path_mapping[job.id] = (
                id_path_mapping.get(parent_job.id, "") + parse_res["path"]
            )

            if sub_variation:
                operations = add_variations(
                    operations, project, sub_variation, job, id_path_mapping
                )

        operations.append(operation.get("operation"))
    return operations


def setup_job_doc(job: Job, reset: bool = False) -> None:
    """Sets basic information in the job document"""

    # dont overwrite old job state on init so that we can update a tree without
    # triggering rerunning operations
    if job.doc.get("state"):
        return
    job.doc["state"] = {}
    job.doc["data"] = []  # store results data here
    job.doc["history"] = []  # history of executed operations
    job.doc["cache"] = {}


def create_tree(
    project: OpenFOAMProject,
    config: dict,
    arguments: dict,
    skip_foam_src_check: bool = False,
):
    if not skip_foam_src_check and not os.environ.get("FOAM_ETC"):
        logger.error("Error OpenFOAM not sourced")
        sys.exit(-1)

    # Add base case
    base_case_state = {
        "has_child": True,
        "parent_id": None,
        "parent": {},
        "pre_build": config["case"].get("pre_build", []),
        "post_build": config["case"].get("post_build", []),
        "keys": list(config["case"].keys()),
    }
    base_case_state.update({k: v for k, v in config["case"].items()})
    of_case = project.open_job(base_case_state)

    setup_job_doc(of_case)
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

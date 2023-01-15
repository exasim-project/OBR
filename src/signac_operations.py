#!/usr/bin/env python3
import flow
import signac
from signac_labels import *

import signac_wrapper
from core import execute
from OpenFOAMCase import OpenFOAMCase, modifies_file

import os
import sys
from pathlib import Path
from subprocess import check_output


class OpenFOAMProject(flow.FlowProject):
    pass


def obr_create_operation(job, operation):
    """Operations that are used to create the case matrix this filters
    out operations that are not requested for the given job and performs
    the needed setup of the case
    """
    # don't execute operation on cases that dont request them
    if (
        operation != job.sp.get("operation")
        or not needs_init_dependent(job)
        or not is_case(job)
    ):
        return False
    return True


def base_case_is_ready(job):
    """Checks whether the parent of the given job is ready"""
    if job.doc.get("base_id"):
        project = OpenFOAMProject.get_project(root=job.path + "/../..")
        parent_job = project.open_job(id=job.doc.get("base_id"))
        base_path = Path(project.open_job(id=job.doc.get("base_id")).path)
        dst_path = Path(job.path) / "case"
        if "is_case" in list(project.labels(parent_job)):
            # print("base_case_ready", list(project.labels(parent_job)))
            # print(job.doc)
            if parent_job.sp.get("operation"):
                # print("parent operation", parent_job.sp.get("operation"))
                pass
            return True
        else:
            return False


def needs_init_dependent(job):
    """check if this job has been already linked to

    The default strategy is to link all files. If a file is modified
    the modifying operations are responsible for unlinking and copying
    """
    if job.doc.get("base_id"):
        project = OpenFOAMProject.get_project(root=job.path + "/../..")
        base_path = Path(project.open_job(id=job.doc.get("base_id")).path) / "case"
        dst_path = Path(job.path) / "case"
        # base path might not be ready atm
        for root, folder, files in os.walk(Path(base_path)):
            check_output(["mkdir", "-p", "case"], cwd=job.path)
            relative_path = Path(root).relative_to(base_path)
            for fold in folder:
                src = Path(root) / fold
                dst = Path(dst_path) / relative_path / fold
                if not dst.exists():
                    check_output(
                        [
                            "mkdir",
                            fold,
                        ],
                        cwd=dst_path / relative_path,
                    )
            for fn in files:
                src = Path(root) / fn
                dst = Path(dst_path) / relative_path / fn
                if not dst.exists():
                    check_output(
                        [
                            "ln",
                            "-s",
                            str(os.path.relpath(src, dst_path / relative_path)),
                        ],
                        cwd=dst_path / relative_path,
                    )
        return True
    else:
        return False


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "controlDict"))
@OpenFOAMProject.post.true("set_controlDict")
@OpenFOAMProject.operation
def controlDict(job, args={}):
    """sets up the controlDict"""
    if args:
        args = {key: value for key, value in args.items()}
    else:
        args = {job.sp["args"]: job.sp["value"]}
    OpenFOAMCase(str(job.path) + "/case", job).setControlDict(args)
    job.doc.controlDict = True


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "blockMesh"))
@OpenFOAMProject.post.true("set_blockMesh")
@OpenFOAMProject.operation
def blockMesh(job, args={}):
    case_name = job.sp["case"]
    OpenFOAMCase(str(job.path) + "/case", job).blockMesh(args)


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "fvSolution"))
@OpenFOAMProject.operation
def fvSolution(job, args={}):
    case_name = job.sp["case"]
    OpenFOAMCase(str(job.path) + "/case", job).setLinearSolver(args)


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(is_case)
@OpenFOAMProject.operation
def setKeyValuePair(job, args={}):
    modifies_file([Path(job.path) / fn for fn in args["file"]])
    case_name = job.sp["case"]
    OpenFOAMCase(str(job.path) + "/case", job).setKeyValuePair(args)


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "decomposePar"))
@OpenFOAMProject.operation
def decomposePar(job, args={}):
    case_name = job.sp["case"]
    OpenFOAMCase(str(job.path) + "/case", job).decomposePar(args)


def execute_operation(job, operation_name, operations):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    for operation in operations:
        if isinstance(operation, str):
            getattr(sys.modules[__name__], operation)(job)
        else:
            if operation.get("shell", None):
                execute(operation.get("shell"), job)
            else:
                func = list(operation.keys())[0]
                getattr(sys.modules[__name__], func)(job, operation.get(func))
    return True


def execute_post_build(operation_name, job):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    operations = job.doc.get("post_build", [])
    execute_operation(job, operation_name, operations)


def execute_pre_build(operation_name, job):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    operations = job.doc.get("pre_build", [])
    execute_operation(job, operation_name, operations)


@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(lambda job: job.doc.get("is_base", False))
@OpenFOAMProject.post(is_case)
@OpenFOAMProject.operation
def fetch_case(job):
    import CaseOrigins

    case_type = job.sp["case"]
    fetch_case_handler = getattr(CaseOrigins, case_type)(job.doc["parameters"])
    fetch_case_handler.init(job=job)


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "RefineMesh"))
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.pre(has_generated_mesh)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.operation
def RefineMesh(job):
    value = job.sp["value"]
    parameters = job.doc["parameters"]
    for _ in range(value):
        OpenFOAMCase(str(job.path) + "/case", job).refineMesh(parameters)

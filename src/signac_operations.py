#!/usr/bin/env python3
import flow
from signac_labels import *

from core import execute
from OpenFOAMCase import OpenFOAMCase

import os
import sys
from pathlib import Path
from subprocess import check_output

# TODO operations should get an id/hash so that we can log success


class OpenFOAMProject(flow.FlowProject):
    pass


generate = OpenFOAMProject.make_group(name="generate")

simulate = OpenFOAMProject.make_group("execute")


def is_case(job):
    has_ctrlDict = job.isfile("case/system/controlDict")
    return has_ctrlDict


def operation_complete(job, operation):
    """An operation is considered to be complete if an entry in the job document with same arguments exists and state is success
    """
    # TODO check hash
    if job.doc.get("obr"):
        state = job.doc.get("obr").get(operation)
        if not state:
            return False
        args_in = get_args(job, False)
        prev_args = {key: job.sp[key] for key in job.doc.get("keys", [])}
        return (state[-1]["state"] == "success") and (args_in == prev_args)
    else:
        return False


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
        Path(job.path) / "case"
        if "unitialised" in list(project.labels(parent_job)):
            # print("base_case_ready", list(project.labels(parent_job)))
            # print(job.doc)
            if parent_job.sp.get("operation"):
                # print("parent operation", parent_job.sp.get("operation"))
                pass
            return False
        else:
            return True


def needs_init_dependent(job):
    """check if this job has been already linked to

    The default strategy is to link all files. If a file is modified
    the modifying operations are responsible for unlinking and copying
    """
    if job.doc.get("base_id"):
        if job.doc.get("init_depentent"):
            return True
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
        job.doc["init_dependent"] = True
        return True
    else:
        return False


def get_args(job, args):
    """operation can get args either via function call or it statepoint
    if no args are passed via function the args from the statepoint are taken
    """
    return (
        {key: value for key, value in args.items()}
        if args
        else {key: job.sp[key] for key in job.doc["keys"]}
    )


def execute_operation(job, operation_name, operations):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    if not operations:
        return True
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


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "controlDict"))
@OpenFOAMProject.post.true("set_controlDict")
@OpenFOAMProject.operation
def controlDict(job, args={}):
    """sets up the controlDict"""
    # TODO gets args either from function arguments if function
    # was called directly from a pre/post build or from sp
    # if this was a variation. In any case this could be a decorator
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).controlDict.set(args)
    job.doc.controlDict = True


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "blockMesh"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "blockMesh"))
@OpenFOAMProject.operation
def blockMesh(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).blockMesh(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "fvSolution"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "fvSolution"))
@OpenFOAMProject.operation
def fvSolution(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).fvSolution.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(is_case)
@OpenFOAMProject.operation
def setKeyValuePair(job, args={}):
    # FIXME
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).setKeyValuePair(args)


def has_mesh(job):
    """Check whether all mesh files are files (owning) or symlinks (non-owning)

    TODO check also for .obr files for state of operation"""
    fn = Path(job.path) / "case/constant/polyMesh"
    if not fn.exists():
        return False
    for f in ["boundary", "faces", "neighbour", "owner", "points"]:
        if not (fn / f).exists():
            return False
    return True


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "decomposePar"))
@OpenFOAMProject.pre(has_mesh)
@OpenFOAMProject.post(lambda job: operation_complete(job, "decomposePar"))
@OpenFOAMProject.operation
def decomposePar(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).decomposePar(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(lambda job: job.doc.get("is_base", False))
@OpenFOAMProject.post(is_case)
@OpenFOAMProject.operation
def fetchCase(job):
    import CaseOrigins

    case_type = job.sp["case"]
    fetch_case_handler = getattr(CaseOrigins, case_type)(job.doc["parameters"])
    fetch_case_handler.init(job=job)


@generate
@OpenFOAMProject.operation_hooks.on_start(execute_pre_build)
@OpenFOAMProject.operation_hooks.on_success(execute_post_build)
@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(lambda job: obr_create_operation(job, "RefineMesh"))
@OpenFOAMProject.pre(has_mesh)
@OpenFOAMProject.post(lambda job: operation_complete(job, "RefineMesh"))
@OpenFOAMProject.operation
def refineMesh(job):
    value = job.sp["value"]
    parameters = job.doc["parameters"]
    for _ in range(value):
        OpenFOAMCase(str(job.path) + "/case", job).refineMesh(parameters)


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(owns_mesh)
@OpenFOAMProject.operation
def checkMesh(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).checkMesh(args)


def get_number_of_procs(job):
    np = job.sp.get("numberSubDomains")
    if np:
        return np
    return int(
        OpenFOAMCase(str(job.path) + "/case", job).decomposeParDict.get(
            "numberSubDomains"
        )
    )


@simulate
@OpenFOAMProject.pre(final)
@OpenFOAMProject.operation(
    cmd=True, directives={"np": lambda job: get_number_of_procs(job)}
)
def runParallelSolver(job, args={}):
    from datetime import datetime

    args = get_args(job, args)
    case = OpenFOAMCase(str(job.path) + "/case", job)
    solver = case.controlDict.get("application")
    mpiargs = "--map-by core --bind-to core"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    res = job.doc["obr"].get("solver", [])
    res.append(
        {
            "type": "shell",
            "log": f"{solver}_{timestamp}.log",
            "state": "started",
            "timestamp": timestamp,
        }
    )
    job.doc["obr"][solver] = res

    cli_args = {
        "solver": solver,
        "path": job.path,
        "timestamp": timestamp,
        "np": get_number_of_procs(job),
    }
    return os.environ.get("OBR_RUN_CMD").format(**cli_args)

    # return (
    #     f"mpirun {mpiargs} {solver} -parallel -case {job.path}/case >"
    #     f" {job.path}/case/{solver}_{timestamp}.log 2>&1"
    # )


def func(x):
    # print(f"called {__name__}", type(x), len(x), x)
    return [True, True]

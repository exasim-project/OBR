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
# TODO add:
# - reconstructPar
# - unlockTmpLock
# - renumberMesh


class OpenFOAMProject(flow.FlowProject):
    pass


generate = OpenFOAMProject.make_group(name="generate")

simulate = OpenFOAMProject.make_group("execute")


class JobCache:
    def __init__(self, jobs):
        self.d = {j.id: j for j in jobs}

    def search_parent(self, job, key):
        base_id = job.doc.get("base_id")
        if not base_id:
            return
        base_value = self.d[base_id].doc["obr"].get(key)
        if base_value:
            return base_value
        else:
            return self.search_parent(self.d[base_id], key)


def is_case(job):
    has_ctrlDict = job.isfile("case/system/controlDict")
    return has_ctrlDict


def operation_complete(job, operation):
    """An operation is considered to be complete if an entry in the job document with same arguments exists and state is success
    """
    if job.doc.get("obr"):
        state = job.doc.get("obr").get(operation)
        if not state:
            return False
        args_in = get_args(job, False)
        prev_args = {key: job.sp[key] for key in job.doc.get("keys", [])}
        return (state[-1]["state"] == "success") and (args_in == prev_args)
    else:
        return False


def basic_eligible(job, operation):
    """Dispatches to standard checks if operations are eligible for given job

    this includes:
      - check for lock, to avoid running operations when calling 'obr run'
        before operation is finished
      - check if parent case is ready
      - operation has been requested for job
      - copy and link files and folder
    """
    # don't execute operation on cases that dont request them
    if (
        is_locked(job)
        or not base_case_is_ready(job)
        or not operation == job.sp.get("operation")
        or not needs_init_dependent(job)
        or not is_case(job)
    ):
        return False
    return True


def base_case_is_ready(job):
    """Checks whether the parent of the given job is ready

    TODO rename to parent_job_is_ready
    """
    if job.doc.get("base_id"):
        project = OpenFOAMProject.get_project(root=job.path + "/../..")
        parent_job = project.open_job(id=job.doc.get("base_id"))
        return parent_job.doc.get("state", "") == "ready"


def needs_init_dependent(job):
    """check if this job has been already linked to

    The default strategy is to link all files. If a file is modified
    the modifying operations are responsible for unlinking and copying
    """
    if job.doc.get("base_id"):
        if job.doc.get("init_dependent"):
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

    also args can be just a str in case of shell scripts
    """
    if isinstance(args, dict):
        return (
            {key: value for key, value in args.items()}
            if args
            else {key: job.sp[key] for key in job.doc["keys"]}
        )
    else:
        return args


def execute_operation(job, operation_name, operations):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    if not operations:
        return True
    for operation in operations:
        try:
            if isinstance(operation, str):
                getattr(sys.modules[__name__], operation)(job)
            else:
                func = list(operation.keys())[0]
                getattr(sys.modules[__name__], func)(job, operation.get(func))
        except Exception as e:
            job.doc["state"] == "failure"
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


def start_job_state(_, job):
    current_state = job.doc.get("state")
    if not current_state:
        job.doc["state"] = "started"
        return
    if current_state == "started":
        # job has been started but not finished yet
        job.doc["state"] = "tmp_lock"
    return True


def end_job_state(_, job):
    job.doc["state"] = "ready"
    return True


def dispatch_pre_hooks(operation_name, job):
    """just forwards to start_job_state and execute_pre_build"""
    start_job_state(operation_name, job)
    execute_pre_build(operation_name, job)


def dispatch_post_hooks(operation_name, job):
    """just forwards to start_job_state and execute_pre_build"""
    execute_post_build(operation_name, job)
    end_job_state(operation_name, job)


def set_failure(operation_name, error, job):
    """just forwards to start_job_state and execute_pre_build"""
    job.doc["state"] = "failure"


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "controlDict"))
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
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "blockMesh"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "blockMesh"))
@OpenFOAMProject.operation
def blockMesh(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).blockMesh(args)

    # get number of cells
    log = job.doc["obr"]["blockMesh"][-1]["log"]
    cells = (
        check_output(["grep", "nCells:", Path(job.path) / "case" / log])
        .decode("utf-8")
        .split()[-1]
    )
    job.doc["obr"]["nCells"] = int(cells)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "shell"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "shell"))
@OpenFOAMProject.operation
def shell(job, args={}):
    args = get_args(job, args)
    # if called from post build args are just a string
    if isinstance(args, dict):
        steps = [f"{k} {v}".replace("_dot_", ".") for k, v in args.items()]
    else:
        steps = [args]
    execute(steps, job)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "fvSolution"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "fvSolution"))
@OpenFOAMProject.operation
def fvSolution(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).fvSolution.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "setKeyValuePair"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "setKeyValuePair"))
@OpenFOAMProject.operation
def setKeyValuePair(job, args={}):
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
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "decomposePar"))
@OpenFOAMProject.pre(has_mesh)
@OpenFOAMProject.post(lambda job: operation_complete(job, "decomposePar"))
@OpenFOAMProject.operation
def decomposePar(job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).decomposePar(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: job.doc.get("is_base", False))
@OpenFOAMProject.post(is_case)
@OpenFOAMProject.operation
def fetchCase(job):
    import CaseOrigins

    case_type = job.sp["case"]
    fetch_case_handler = getattr(CaseOrigins, case_type)(job.doc["parameters"])
    fetch_case_handler.init(job=job)


def is_locked(job):
    """Cases that are already started are set to tmp_lock
    dont try to execute them
    """
    return job.doc.get("state") == "tmp_lock"


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "refineMesh"))
@OpenFOAMProject.pre(has_mesh)
@OpenFOAMProject.post(lambda job: operation_complete(job, "refineMesh"))
@OpenFOAMProject.operation
def refineMesh(job, args={}):
    args = get_args(job, args)
    for _ in range(args.get("value")):
        OpenFOAMCase(str(job.path) + "/case", job).refineMesh(args)


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
    job.doc["obr"]["solver"] = solver

    cli_args = {
        "solver": solver,
        "path": job.path,
        "timestamp": timestamp,
        "np": get_number_of_procs(job),
    }
    return os.environ.get("OBR_RUN_CMD").format(**cli_args)


@OpenFOAMProject.operation(aggregator=flow.aggregator())
def apply(*jobs, args={}):
    import importlib.util
    import sys

    fp = Path(os.environ.get("OBR_CALL_ARGS"))
    spec = importlib.util.spec_from_file_location("apply_func", fp)
    apply_functor = importlib.util.module_from_spec(spec)
    # sys.modules["apply_func"] = apply_functor
    spec.loader.exec_module(apply_functor)
    apply_functor.call(jobs)

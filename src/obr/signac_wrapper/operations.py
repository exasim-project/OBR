#!/usr/bin/env python3
import flow
import os
import sys
from pathlib import Path
from subprocess import check_output
from ..core.core import execute
from .labels import owns_mesh, final, finished
from obr.OpenFOAM.case import OpenFOAMCase
import CaseOrigins
from signac.contrib.job import Job
from typing import Union, Literal

# TODO operations should get an id/hash so that we can log success
# TODO add:
# - reconstructPar
# - unlockTmpLock
# - renumberMesh


class OpenFOAMProject(flow.FlowProject):
    def print_operations(self):
        ops = sorted(self.operations.keys())
        print("Available operations are:\n\t", "\n\t ".join(ops))
        return


generate = OpenFOAMProject.make_group(name="generate")
simulate = OpenFOAMProject.make_group("execute")


class JobCache:
    def __init__(self, jobs: list[Job]):
        self.d = {j.id: j for j in jobs}

    def search_parent(self, job: Job, key):
        base_id = job.doc.get("base_id")
        if not base_id:
            return
        base_value = self.d[base_id].doc["obr"].get(key)
        if base_value:
            return base_value
        else:
            return self.search_parent(self.d[base_id], key)


def is_case(job: Job) -> bool:
    has_ctrlDict = job.isfile("case/system/controlDict")
    return has_ctrlDict


def operation_complete(job: Job, operation: str) -> bool:
    """An operation is considered to be complete if an entry in the job document with same arguments exists and state is success"""
    if job.doc.get("state") == "ready":
        return True
    else:
        return False
    # TODO check if anything else is actually needed
    # if job.doc.get("obr"):
    #     # if job has completed before its state
    #     # is set to success

    #     state = job.doc.get("obr").get(operation)
    #     if not state:
    #         return False
    #     args_in = get_args(job, False)
    #     prev_args = {key: job.sp[key] for key in job.doc.get("keys", [])}
    #     return (state[-1]["state"] == "success") and (args_in == prev_args)
    # else:
    #     return False


def basic_eligible(job: Job, operation: str) -> bool:
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
        or not operation == job.sp().get("operation")
        or not needs_init_dependent(job)
        or not is_case(job)
    ):
        # For Debug purposes
        if False:
            print(f"check if job {job.id} is eligible is False")
            print("is_locked should be False", is_locked(job))
            print("base case is ready should be True", base_case_is_ready(job))
            print("needs_init_dependent should be True", needs_init_dependent(job))
            print("is_case should be True", is_case(job))
        return False
    return True


def base_case_is_ready(job: Job) -> Union[bool, None]:
    """Checks whether the parent of the given job is ready

    TODO rename to parent_job_is_ready
    """
    if job.doc.get("base_id"):
        project = OpenFOAMProject.get_project(root=job.path + "/../..")
        parent_job = project.open_job(id=job.doc.get("base_id"))
        return parent_job.doc.get("state", "") == "ready"


def _link_path(base: Path, dst: Path, copy_instead_link: bool):
    """creates file tree under dst with same folder structure as base but all files are relative symlinks"""
    # ensure dst path exists
    check_output(["mkdir", "-p", str(dst)])

    # base path might not be ready atm
    for root, folder, files in os.walk(Path(base)):
        relative_path = Path(root).relative_to(base)

        for fold in folder:
            src = Path(root) / fold
            dst_ = Path(dst) / relative_path / fold
            if not dst_.exists():
                check_output(
                    [
                        "mkdir",
                        fold,
                    ],
                    cwd=dst / relative_path,
                )

        for fn in files:
            src = Path(root) / fn
            dst_ = Path(dst) / relative_path / fn
            if not dst_.exists():
                if copy_instead_link:
                    check_output(
                        [
                            "cp",
                            str(os.path.relpath(src, dst / relative_path)),
                            ".",
                        ],
                        cwd=dst / relative_path,
                    )

                else:
                    check_output(
                        [
                            "ln",
                            "-s",
                            str(os.path.relpath(src, dst / relative_path)),
                        ],
                        cwd=dst / relative_path,
                    )


def needs_init_dependent(job: Job) -> bool:
    """check if this job has been already linked to

    The default strategy is to link all files. If a file is modified
    the modifying operations are responsible for unlinking and copying
    """
    # shell scripts might change files as side effect
    # hence we copy all files instead of linking to avoid
    # side effects
    # in future it might make sense to specify the files which are modified
    # in the yaml file
    copy_instead_link = job.sp().get("operation") == "shell"
    if job.doc.get("base_id"):
        if job.doc.get("init_dependent"):
            #    print("already init", job.id)
            return True
        base_id = job.doc.get("base_id")

        base_path = Path(job.path) / ".." / base_id / "case"
        dst_path = Path(job.path) / "case"
        _link_path(base_path, dst_path, copy_instead_link)
        job.doc["init_dependent"] = True
        return True
    else:
        return False


def get_args(job: Job, args: Union[dict, str]) -> Union[dict, str]:
    """operation can get args either via function call or it statepoint
    if no args are passed via function the args from the statepoint are taken

    also args can be just a str in case of shell scripts
    """
    if isinstance(args, dict):
        return (
            {key: value for key, value in args.items()}
            if args
            else {key: job.sp()[key] for key in job.doc["keys"]}
        )
    else:
        return args


def execute_operation(job: Job, operation_name: str, operations) -> Literal[True]:
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
            print(e)
            job.doc["state"] == "failure"
    return True


def execute_post_build(operation_name: str, job: Job):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    operations = job.doc.get("post_build", [])
    execute_operation(job, operation_name, operations)


def execute_pre_build(operation_name: str, job: Job):
    """check wether an operation is requested

    operation can be simple operations defined by a keyword like blockMesh
    or operations with parameters defined by a dictionary
    """
    operations = job.doc.get("pre_build", [])
    execute_operation(job, operation_name, operations)


def start_job_state(_, job: Job) -> Union[Literal[True], None]:
    current_state = job.doc.get("state")
    if not current_state:
        job.doc["state"] = "started"
        return
    if current_state == "started":
        # job has been started but not finished yet
        job.doc["state"] = "tmp_lock"
    return True


def end_job_state(_, job: Job) -> Literal[True]:
    job.doc["state"] = "ready"
    return True


def dispatch_pre_hooks(operation_name: str, job: Job):
    """just forwards to start_job_state and execute_pre_build"""
    print(type(operation_name))
    start_job_state(operation_name, job)
    execute_pre_build(operation_name, job)


def dispatch_post_hooks(operation_name: str, job: Job):
    """Forwards to `execute_post_build`, performs md5sum calculation of case files and finishes with `end_job_state`"""
    execute_post_build(operation_name, job)
    case = OpenFOAMCase(str(job.path) + "/case", job)
    case.perform_post_md5sum_calculations()
    end_job_state(operation_name, job)


def set_failure(operation_name: str, error, job: Job):
    """just forwards to start_job_state and execute_pre_build"""
    job.doc["state"] = "failure"


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "controlDict"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "controlDict"))
@OpenFOAMProject.operation
def controlDict(job: Job, args={}):
    """sets up the controlDict"""
    # TODO gets args either from function arguments if function
    # was called directly from a pre/post build or from sp
    # if this was a variation. In any case this could be a decorator
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).controlDict.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "blockMesh"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "blockMesh"))
@OpenFOAMProject.operation
def blockMesh(job: Job, args={}):
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
    job.doc.blockMesh = True


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "shell"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "shell"))
@OpenFOAMProject.operation
def shell(job: Job, args={}):
    args = get_args(job, args)
    # if called from post build args are just a string
    if isinstance(args, dict):
        steps = [f"{k} {v}".replace("_dot_", ".") for k, v in args.items()]
    else:
        steps = [args]
    execute(steps, job)
    # TODO do deduplication once done


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "fvSolution"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "fvSolution"))
@OpenFOAMProject.operation
def fvSolution(job: Job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).fvSolution.set(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: basic_eligible(job, "setKeyValuePair"))
@OpenFOAMProject.post(lambda job: operation_complete(job, "setKeyValuePair"))
@OpenFOAMProject.operation
def setKeyValuePair(job: Job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).setKeyValuePair(args)


def has_mesh(job: Job) -> bool:
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
def decomposePar(job: Job, args={}):
    args = get_args(job, args)

    # TODO
    # before decomposing check if case with same state
    # ie time folder blockMeshDict decomposeParDict
    # exists and decomposition is already done
    # if so just copy/link folders
    workspace_folder = Path(job.path) / "../"
    root, job_paths, _ = next(os.walk(workspace_folder))

    target_case = OpenFOAMCase(str(job.path) + "/case", job)

    # TODO consider also latest/all time folder contents
    target_md5sums = [
        target_case.decomposeParDict.md5sum(),
        target_case.blockMeshDictmd5sum(),
    ]

    found = False
    for job_path in job_paths:
        dst_path = Path(root) / job_path / "case"
        if not dst_path.exists():
            continue
        dst_case = OpenFOAMCase(dst_path, {})
        dst_md5sums = [
            dst_case.decomposeParDict.md5sum(),
            dst_case.blockMeshDictmd5sum(),
        ]
        if target_md5sums == dst_md5sums:
            found = True
            break

    if found:
        for processor_path in dst_case.processor_folder:
            _link_path(processor_path, target_case.path / processor_path.parts[-1])
    else:
        target_case.decomposePar(args)


@generate
@OpenFOAMProject.operation_hooks.on_start(dispatch_pre_hooks)
@OpenFOAMProject.operation_hooks.on_success(dispatch_post_hooks)
@OpenFOAMProject.operation_hooks.on_exception(set_failure)
@OpenFOAMProject.pre(lambda job: not bool(job.doc.get("base_id")))
@OpenFOAMProject.post(is_case)
@OpenFOAMProject.operation
def fetchCase(job: Job, args={}):
    args = get_args(job, args)

    case_type = job.sp()["type"]
    fetch_case_handler = getattr(CaseOrigins, case_type)(args)
    fetch_case_handler.init(job=job)


def is_locked(job: Job) -> bool:
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
def refineMesh(job: Job, args={}):
    args = get_args(job, args)
    for _ in range(args.get("value")):
        OpenFOAMCase(str(job.path) + "/case", job).refineMesh(args)


@OpenFOAMProject.pre(base_case_is_ready)
@OpenFOAMProject.pre(owns_mesh)
@OpenFOAMProject.operation
def checkMesh(job: Job, args={}):
    args = get_args(job, args)
    OpenFOAMCase(str(job.path) + "/case", job).checkMesh(args)

    log = job.doc["obr"]["checkMesh"][-1]["log"]
    cells = (
        check_output(["grep", "cells:", Path(job.path) / "case" / log])
        .decode("utf-8")
        .split()[-1]
    )
    job.doc["obr"]["nCells"] = int(cells)


def get_number_of_procs(job: Job) -> int:
    np = int(job.sp().get("numberSubDomains", 0))
    if np:
        return np
    return int(
        OpenFOAMCase(str(job.path) + "/case", job).decomposeParDict.get(
            "numberOfSubdomains"
        )
    )


def get_values(jobs: list, key: str) -> set:
    """find all different statepoint values"""
    values = [job.sp().get(key) for job in jobs if job.sp().get(key)]
    return set(values)


@simulate
@OpenFOAMProject.pre(final)
@OpenFOAMProject.operation(
    cmd=True, directives={"np": lambda job: get_number_of_procs(job)}
)
def runParallelSolver(job: Job, args={}) -> str:
    from datetime import datetime

    skip_complete = os.environ.get("OBR_SKIP_COMPLETE")
    if skip_complete and finished(job):
        return "true"

    args = get_args(job, args)
    case = OpenFOAMCase(str(job.path) + "/case", job)
    solver = case.controlDict.get("application")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    res = job.doc["obr"].get(solver, [])
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
    return os.environ.get("OBR_RUN_CMD").format(**cli_args) + "|| true"


@OpenFOAMProject.operation
def archive(job: Job, args={}) -> Literal[True]:
    root, _, files = next(os.walk(Path(job.path) / "case"))
    fp = os.environ.get("OBR_CALL_ARGS")
    for fn in files:
        if fp not in fn:
            continue
        if (Path(root) / fn).is_symlink():
            continue
        check_output(["cp", "-r", f"{job.path}/case/{fn}", f"obr_store/{job.id}_{fn}"])
    return True


@OpenFOAMProject.operation(aggregator=flow.aggregator())
def apply(*jobs, args={}):
    import importlib.util

    fp = Path(os.environ.get("OBR_CALL_ARGS"))
    spec = importlib.util.spec_from_file_location("apply_func", fp)
    apply_functor = importlib.util.module_from_spec(spec)
    # sys.modules["apply_func"] = apply_functor
    spec.loader.exec_module(apply_functor)
    apply_functor.call(jobs)

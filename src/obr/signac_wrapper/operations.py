#!/usr/bin/env python3
import flow
import os
import sys
import re
from copy import deepcopy
from typing import Callable, Any
from pathlib import Path
from subprocess import check_output
from collections import defaultdict
from dataclasses import dataclass, field

from ..core import execute
from .labels import *
from obr.OpenFOAM.case import OpenFOAMCase
import CaseOrigins


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
        project = OpenFOAMProject.get_project(root=job.path + "/../..")
        # print("project", job.path, project)
        base_id = job.doc.get("base_id")
        base_path = Path(job.path) / ".." / base_id / "case"
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
                    if copy_instead_link:
                        check_output(
                            [
                                "cp",
                                str(os.path.relpath(src, dst_path / relative_path)),
                                ".",
                            ],
                            cwd=dst_path / relative_path,
                        )

                    else:
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
            else {key: job.sp()[key] for key in job.doc["keys"]}
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
            print(e)
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
@OpenFOAMProject.post(lambda job: operation_complete(job, "controlDict"))
@OpenFOAMProject.operation
def controlDict(job, args={}):
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
    job.doc.blockMesh = True


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
    # TODO do deduplication once done


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
@OpenFOAMProject.pre(lambda job: not bool(job.doc.get("base_id")))
@OpenFOAMProject.post(is_case)
@OpenFOAMProject.operation
def fetchCase(job, args={}):
    args = get_args(job, args)

    case_type = job.sp()["type"]
    fetch_case_handler = getattr(CaseOrigins, case_type)(args)
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

    log = job.doc["obr"]["checkMesh"][-1]["log"]
    cells = (
        check_output(["grep", "cells:", Path(job.path) / "case" / log])
        .decode("utf-8")
        .split()[-1]
    )
    job.doc["obr"]["nCells"] = int(cells)


def get_number_of_procs(job) -> int:
    np = int(job.sp().get("numberSubDomains", 0))
    if np:
        return np
    return int(
        OpenFOAMCase(str(job.path) + "/case", job).decomposeParDict.get(
            "numberOfSubdomains"
        )
    )


def equal(a, b):
    return a == b


def not_equal(a, b):
    return a != b


@dataclass
class query_result:
    id: str = field()
    result: list[dict] = field(default_factory=list[dict])


# TODO implement to clean up query_to_dict
@dataclass
class Query:
    key: str
    value: Any = ""
    state: dict = field(default_factory=dict)
    predicate: Callable = equal

    def execute(self, key, value):
        if self.value:
            if self.predicate({self.key: self.value}, {key: value}) and not self.state:
                self.state = {key: value}
        else:
            # print(key, value)
            if self.predicate(self.key, key) and not self.state:
                self.state = {key: value}

    def match(self):
        return self.state


def input_to_query(inp: str) -> Query:
    """converts cli input  str to a Query object"""
    inp = inp.replace("key", '"key"').replace("value", '"value"')
    return Query(**eval(inp))


def input_to_queries(inp: str) -> list[Query]:
    """Convert a json string to list of queries"""

    inp_lst = re.findall("{[\w:\"'0-9,. ]*}", inp)
    return [input_to_query(x) for x in inp_lst]


def query_to_dict(
    jobs: list, queries: list[Query], output=False, latest_only=True, strict=False
) -> list[query_result]:
    """Given a list jobs find all jobs for which a query matches"""
    docs: dict = {}

    # merge job docs and statepoints
    for job in jobs:
        if not job.doc.get("obr"):
            continue
        docs[job.id] = {}
        for key, value in job.doc.obr.items():
            docs[job.id].update({key: value})
        docs[job.id].update(job.sp())

    ret = []

    def execute_query(query, key, value) -> Query:
        if isinstance(value, list) and latest_only and value:
            value = value[-1]
        # descent one level down
        # statepoints and job documents might contain subdicts which we want to descent
        # into
        signac_attr_dict_str = "JSONAttrDict"
        if isinstance(value, dict) or type(value).__name__ == signac_attr_dict_str:
            sub_results = list(
                filter(
                    lambda x: x.state,
                    [
                        execute_query(deepcopy(query), sub_key, sub_value)
                        for sub_key, sub_value in value.items()
                    ],
                )
            )
            if len(sub_results) > 0:
                return sub_results[0]
        query.execute(key, value)
        return query

    for job_id, doc in docs.items():
        # scan through merged operations and statepoint values of a job
        # look for keys and values
        # and append if all queries have been matched
        tmp_qs: list[Query] = []
        all_required = True
        for q in queries:
            res_cache = {}
            for key, value in doc.items():
                q_tmp = deepcopy(q)
                res = execute_query(q_tmp, key, value)
                if res.state:
                    res_cache = res.state
                    tmp_qs.append(res)

            # res.state could be from any key before
            if q.value and not res_cache:
                all_required = False

        # append if all required results are present
        res_tmp = query_result(job_id)
        for q in tmp_qs:
            # requests a value but not a state
            # is currently considered to be failed
            res_tmp.result.append(q.state)

        # in strict mode all queries need to have some result
        if strict:
            all_required = len(res_tmp.result) == len(queries)

        # merge all results to a single dictionary
        res_tmp_dict = {}
        for d in res_tmp.result:
            res_tmp_dict.update(d)
        res_tmp.result = [res_tmp_dict]

        if all_required:
            ret.append(deepcopy(res_tmp))
    return ret


def get_values(job_statepoints: list, key: str) -> set:
    """find all different statepoint values"""
    values = [sp.get(key) for sp in job_statepoints if sp.get(key)]
    return set(values)


def query_impl(
    jobs: list, queries: list[Query], output=False, latest_only=True
) -> list[str]:
    """Performs a query and returns corresponding job.ids"""
    res = query_to_dict(jobs, queries, output, latest_only)
    if output:
        for r in res:
            print(r)

    query_ids = []
    for id_ in res:
        query_ids.append(id_.id)

    return query_ids


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
def archive(job, args={}):
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
    import sys

    fp = Path(os.environ.get("OBR_CALL_ARGS"))
    spec = importlib.util.spec_from_file_location("apply_func", fp)
    apply_functor = importlib.util.module_from_spec(spec)
    # sys.modules["apply_func"] = apply_functor
    spec.loader.exec_module(apply_functor)
    apply_functor.call(jobs)

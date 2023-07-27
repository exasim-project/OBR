#!/usr/bin/env python3

from pathlib import Path
from flow import FlowProject
from subprocess import check_output
from ..core.core import check_log_for_success


@FlowProject.label
def owns_procs(job):
    fn = Path(job.path) / "case/processor0"
    return fn.exists() and not fn.is_symlink()


@FlowProject.label
def owns_mesh(job):
    """Check whether all mesh files are files (owning) or symlinks (non-owning)"""
    fn = Path(job.path) / "case/constant/polyMesh/points"
    return fn.exists() and not fn.is_symlink()


@FlowProject.label
def check_mesh(job):
    """Check whether checkMesh was performed correctly."""
    checkMeshList = job.doc.get("obr", {}).get("checkMesh", [])
    if checkMeshList == []:
        return False
    return checkMeshList[0].get("state") == "success"


@FlowProject.label
def unitialised(job):
    has_ctrlDict = job.isfile("case/system/controlDict")
    return not has_ctrlDict


@FlowProject.label
def finished(job):
    solver = job.doc.get("obr", {}).get("solver")
    if not solver:
        return False
    solver_log = job.doc["obr"][solver][-1]["log"]
    return check_log_for_success(Path(job.path) / "case" / solver_log)


@FlowProject.label
def started(job):
    solver = job.doc.get("obr", {}).get("solver")
    if not solver:
        return False
    if not job.doc["obr"][solver][-1]["state"] == "started":
        return False
    solver_log = job.doc["obr"][solver][-1]["log"]
    res = check_output(["tail", "-n", "1", solver_log], cwd=Path(job.path) / "case")
    if "Finalising" in res.decode("utf-8"):
        return False
    return True


@FlowProject.label
def processing(job):
    return (
        job.doc["state"].get("global") == "started"
        or job.doc["state"].get("global") == "tmp_lock"
    )


@FlowProject.label
def failure(job):
    return job.doc["state"].get("global") == "failure"


@FlowProject.label
def ready(job):
    return job.doc["state"].get("global") == "ready"


@FlowProject.label
def final(job):
    """jobs that dont have children/variations are considered to be final and
    are thus eligible for execution"""
    if not unitialised(job):
        return not job.sp.get("has_child")
    else:
        return False


@FlowProject.label
def failed_op(job):
    if not job.doc.get("obr"):
        return False

    for operation, data in job.doc.obr.items():
        if not isinstance(data, list):
            continue
        if data[-1]["state"] == "failure":
            return True

    return False

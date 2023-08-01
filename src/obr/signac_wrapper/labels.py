#!/usr/bin/env python3

from pathlib import Path
from flow import FlowProject
from subprocess import check_output
from ..core.core import check_log_for_success, get_latest_log

import re

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
def unitialised(job):
    has_ctrlDict = job.isfile("case/system/controlDict")
    return not has_ctrlDict


@FlowProject.label
def finished(job):
    solver_log = get_latest_log(job)
    if solver_log:
        return check_log_for_success(Path(job.path) / "case" / solver_log)
    return False


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
    are thus eligible for execution

    NOTE as a side effect we check the number of cells
    """
    if not unitialised(job):
        final =  not job.sp.get("has_child")
        if final:
            if not job.doc["cache".get("nCells"):
                owner = check_output(["head", "-n", "13", f"{job.path}/case/constant/polyMesh/owner" ], text=True)
                nCells = re.findall("[0-9]+",owner.split("\n")[-2])[1]
                job.doc["cache"]["nCells"] = nCells
        return final
    else:
        return False


@FlowProject.label
def failed_op(job):
    if job.doc["state"].get("global") == "failure":
        return True
    return False

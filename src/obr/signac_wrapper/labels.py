#!/usr/bin/env python3
import re

from pathlib import Path
from flow import FlowProject
from subprocess import check_output
from Owls.parser import LogFile

from ..core.core import get_latest_log, get_mesh_stats


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
def processing(job):
    return (
        job.doc["state"].get("global") == "started"
        or job.doc["state"].get("global") == "tmp_lock"
    )


@FlowProject.label
def finished(job):
    if job.doc["state"]["global"] == "completed":
        return True
    log = get_latest_log(job)
    if not log:
        return False
    lp = LogFile(log, matcher=[])
    if lp.footer.completed:
        job.doc["state"]["global"] = "completed"
    job.doc["state"]["latestTime"] = lp.latestTime.time
    job.doc["state"]["continuityErrors"] = lp.latestTime.continuity_errors
    if lp.footer.completed:
        return True
    return False


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
        final = not job.sp.get("has_child")
        if final:
            owner_path = f"{job.path}/case/constant/polyMesh/owner"
            if not job.doc["cache"].get("nCells"):
                mesh_stats = get_mesh_stats(owner_path)
                job.doc["cache"]["nCells"] = mesh_stats["nCells"]
                job.doc["cache"]["nFaces"] = mesh_stats["nFaces"]
            return True
    else:
        return False


@FlowProject.label
def failed_op(job):
    if job.doc["state"].get("global") == "failure":
        return True
    return False

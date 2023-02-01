#!/usr/bin/env python3

from pathlib import Path
from flow import FlowProject


@FlowProject.label
def owns_procs(job):
    fn = Path(job.path) / "case/processor0"
    return fn.exists() and not fn.is_symlink()


@FlowProject.label
def owns_mesh(job):
    """Check whether all mesh files are files (owning) or symlinks (non-owning)

    TODO check also for .obr files for state of operation"""
    fn = Path(job.path) / "case/constant/polyMesh/points"
    return fn.exists() and not fn.is_symlink()


@FlowProject.label
def check_mesh(job):
    """Check whether all mesh files are files (owning) or symlinks (non-owning)

    TODO check also for .obr files for state of operation"""
    return "success" == job.doc.get("obr", {}).get("checkMesh", {}).get("state")


@FlowProject.label
def not_case(job):
    has_ctrlDict = job.isfile("case/system/controlDict")
    return not has_ctrlDict


@FlowProject.label
def final(job):
    """jobs that dont have children/variations are considered to be final and
    are thus eligable for execution"""
    if not not_case(job):
        return not job.sp.get("has_child")
    else:
        return False


@FlowProject.label
def failed_op(job):
    if not job.doc.get("obr"):
        return False

    for operation, data in job.doc.obr.items():
        if data["state"] == "failure":
            return True

    return False

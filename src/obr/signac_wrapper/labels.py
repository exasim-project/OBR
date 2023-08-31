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
        final = not job.sp.get("has_child")
        if final:
            owner_path = Path(f"{job.path}/case/constant/polyMesh/owner")
            if not job.doc["cache"].get("nCells") and owner_path.exists():
                with open(owner_path, "r", errors="replace") as fh:
                    read = True
                    FoamFile = False
                    found_note = ""
                    while read:
                        line = fh.readline()
                        if "FoamFile" in line:
                            FoamFile = True
                        if FoamFile and line.strip().startswith("}"):
                            read = False
                        if FoamFile and "note" in line:
                            found_note = line
                note_line = found_note
                nCells = int(re.findall("nCells:([0-9]+)", note_line)[0])
                nFaces = int(re.findall("Faces:([0-9]+)", note_line)[0])
                job.doc["cache"]["nCells"] = nCells
                job.doc["cache"]["nFaces"] = nFaces
        return final
    else:
        return False


@FlowProject.label
def failed_op(job):
    if job.doc["state"].get("global") == "failure":
        return True
    return False

#!/usr/bin/env python3
import os
import subprocess
import re
import hashlib
import logging


from pathlib import Path
from subprocess import check_output
from typing import Union
from datetime import datetime
from signac.contrib.job import Job

# these are to be replaced with each other
SIGNAC_PATH_TOKEN = "_dot_"
PATH_TOKEN = "."


def parse_variables_impl(in_str, args, domain):
    ocurrances = re.findall(r"\${{" + domain + r"\.(\w+)}}", in_str)
    for inst in ocurrances:
        in_str = in_str.replace("${{" + domain + "." + inst + "}}", args.get(inst, ""))
    return in_str


def parse_variables(in_str):
    in_str = parse_variables_impl(in_str, os.environ, "env")
    return in_str


def path_to_key(path: Union[str, Path]) -> str:
    """Signac throws errors if '.' are used in keys within JSONAttrDicts, which are often needed, for example in file names.
    Thus, this function replaces . with _dot_"""
    return str(path).replace(PATH_TOKEN, SIGNAC_PATH_TOKEN)


def key_to_path(sign_path: Union[str, Path]) -> str:
    """Counter function to `path_to_key`, allowing equal transformations."""
    return str(sign_path).replace(SIGNAC_PATH_TOKEN, PATH_TOKEN)


def logged_execute(cmd, path, doc):
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected

    Returns:
        path to log file
    """

    check_output(["mkdir", "-p", ".obr_store"], cwd=path)
    d = doc["history"]
    cmd_str = " ".join(cmd)
    cmd_str = path_to_key(cmd_str).split()  # replace dots in cmd_str with _dot_'s
    if len(cmd_str) > 1:
        flags = cmd_str[1:]
    else:
        flags = []
    cmd_str = cmd_str[0]
    log_path = None
    try:
        ret = check_output(cmd, cwd=path, stderr=subprocess.STDOUT).decode("utf-8")
        log = ret
        state = "success"
    except subprocess.SubprocessError as e:
        logging.error(
            "SubprocessError:"
            + __file__
            + __name__
            + str(e)
            + " check: 'obr find --state failure' for more info",
        )
        log = e.output.decode("utf-8")
        state = "failure"
    except FileNotFoundError as e:
        logging.error(__file__ + __name__ + str(e))
        log = cmd + " not found"
        state = "failure"
    except Exception as e:
        logging.error(__file__ + __name__ + str(e))
        logging.error("General Exception" + __file__ + __name__ + str(e) + e.output)
        log = ret
        state = "failure"

    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    if log and len(log) > 1000:
        h = hashlib.new("md5")
        h.update(log.encode())
        h.hexdigest()
        fn = f"{cmd_str}_{timestamp}.log"
        with open(path / fn, "w") as fh:
            fh.write(log)
        log = fn
        log_path = path / fn

    d.append(
        {
            "cmd": cmd_str,
            "type": "shell",
            "log": log,
            "state": state,
            "flags": flags,
            "timestamp": timestamp,
            "user": os.environ.get("USER"),
            "hostname": os.environ.get("HOST"),
        }
    )

    doc["history"] = d

    return log_path


def logged_func(func, doc, **kwargs):
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected
    """
    from datetime import datetime

    cmd_str = func.__name__
    try:
        func(**kwargs)
        state = "success"
    except Exception as e:
        logging.error("Failure" + __file__ + __name__ + func.__name__ + kwargs + str(e))
        state = "failure"

    res = {
        "cmd": cmd_str,
        "args": str(kwargs),
        "state": state,
        "type": "obr",
        "timestamp": str(datetime.now()),
        "type": "logged_func",
        "user": os.environ.get("USER"),
        "hostname": os.environ.get("HOST"),
    }
    doc["history"].append(res)


def get_mesh_stats(owner_path: str) -> dict:
    """Check constant/polyMesh/owner file for mesh properties
    and return it via a dictionary"""
    nCells = None
    nFaces = None
    if Path(owner_path).exists():
        with open(owner_path, "r", errors="replace") as fh:
            read = True
            FoamFile = False
            found_note = ""
            while read:
                # A little parser for the header part of a foam file
                # TODO this should be moved to OWLS
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
    return {"nCells": nCells, "nFaces": nFaces}


def get_latest_log(job: Job):
    """find latest"""
    from ..OpenFOAM.case import OpenFOAMCase

    case_path = Path(job.path + "case")
    # in case obr status is called directly after initialization
    # this would also fail if there was no case directory
    if not case_path.exists():
        return ""

    case = OpenFOAMCase(case_path, job)
    solver = case.controlDict.get("application")

    history = job.doc["history"]
    for entry in history[:-1]:
        if entry.get("cmd", "").startswith(solver):
            return entry["log"]
    return ""


def execute(steps: list[str], job) -> bool:
    path = Path(job.path) / "case"
    if not steps:
        return False

    steps_filt = []
    if not isinstance(steps, list):
        steps = [steps]
    # scan through steps and stitch steps with line cont together
    for i, step in enumerate(steps):
        if step.endswith("\\"):
            cleaned = step.replace("\\", " ")
            steps[i + 1] = cleaned + steps[i + 1]
            continue
        steps_filt.append(step)

    # steps_filt = map(lambda x: " ".join(x.split()), steps_filt)

    for step in steps_filt:
        if not step:
            continue
        step = parse_variables(step)
        logged_execute(step.split(), path, job.doc)
    return True


def modifies_file(fns):
    """check if this job modifies a file, thus it needs to unlink
    and copy the file if it is a symlink
    """

    def unlink(fn):
        if Path(fn).is_symlink():
            src = fn.resolve()
            check_output(["rm", fn])
            check_output(["cp", "-r", src, fn])

    if isinstance(fns, list):
        for fn in fns:
            unlink(fn)
    else:
        unlink(fns)


def check_log_for_success(log: Path) -> bool:
    res = check_output(["tail", "-n", "2", log], text=True)
    return ("Finalising" in res) or ("End" in res)


def writes_files(fns):
    """check if this job modifies a file, thus it needs to unlink
    and copy the file if it is a symlink
    """

    def unlink(fn):
        if Path(fn).is_symlink():
            fn.resolve()
            check_output(["rm", fn])

    if isinstance(fns, list):
        for fn in fns:
            unlink(fn)
    else:
        unlink(fns)


def map_view_folder_to_job_id(view_folder: str) -> dict[str, str]:
    """Creates a mapping from the view schema to the original jobid

    Returns:
    ========
        A dictionary with jobid: view_folder
    """
    ret = {}
    base = Path(view_folder)
    if not base.exists():
        return {}
    for root, folder, file in os.walk(view_folder):
        for i, fold in enumerate(folder):
            path = Path(root) / fold
            job_id = None
            if path.is_symlink():
                job_id = path.resolve().name
                # only keep path parts relative to the start of of the view
                # folder
                if path.absolute().is_relative_to(base.absolute()):
                    ret[job_id] = str(path.absolute().relative_to(base.absolute()))
                folder.pop(i)
    return ret

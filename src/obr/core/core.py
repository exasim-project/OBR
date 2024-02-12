#!/usr/bin/env python3
import os
import subprocess
import re
import logging
import json
import shutil

from pathlib import Path
from subprocess import check_output
from typing import Union, Generator
from datetime import datetime
from signac.job import Job
from copy import deepcopy

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


def logged_execute(cmd, path, doc) -> Path:
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected

    Returns:
        path to log file
    """

    d = doc["history"]
    cmd_str = " ".join(cmd)
    cmd_str = path_to_key(cmd_str).split()  # replace dots in cmd_str with _dot_'s
    if len(cmd_str) > 1:
        flags = cmd_str[1:]
    else:
        flags = []
    cmd_str = cmd_str[0]
    try:
        ret = check_output(cmd, cwd=path, stderr=subprocess.STDOUT).decode("utf-8")
        log = ret
        state = "success"
    except subprocess.SubprocessError as e:
        log = e.output.decode("utf-8")
        logging.error("SubprocessError:" + __file__ + __name__ + str(e) + log)
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
    log_path = None

    # Only write log files above a certain size
    # otherwise the log is stored directly in the job doc
    if log and len(log) > 1000:
        # the cmd_str might contain / for example if
        # shell scripts are called. Hence we sanitize
        # the script name
        cmd_str_san = key_to_path(cmd_str.split("/")[-1])
        fn = f"{cmd_str_san}_{timestamp}.log"
        with open(path / fn, "w") as fh:
            fh.write(log)
        log = fn
        log_path = path / fn

    d.append({
        "cmd": cmd_str,
        "type": "shell",
        "log": log,
        "state": state,
        "flags": flags,
        "timestamp": timestamp,
        "user": os.environ.get("USER"),
        "hostname": os.environ.get("HOST"),
    })

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
        with open(owner_path, errors="replace") as fh:
            read = True
            is_foamFile = False
            found_note = ""
            while read:
                # A little parser for the header part of a foam file
                # TODO this should be moved to OWLS
                line = fh.readline()
                if "FoamFile" in line:
                    is_foamFile = True
                if is_foamFile and line.strip().startswith("}"):
                    read = False
                if is_foamFile and "note" in line:
                    found_note = line
        note_line = found_note
        nCells = int(re.findall("nCells:[ ]*([0-9]+)", note_line)[0])
        nFaces = int(re.findall("Faces:[ ]*([0-9]+)", note_line)[0])
    return {"nCells": nCells, "nFaces": nFaces}


def merge_job_documents(job: Job):
    """Merge multiple job_document_hash.json files into job_document.json"""
    root, _, files = next(os.walk(job.path))

    def is_job_sub_document(fn):
        if fn == "signac_job_document.json":
            return False
        return fn.startswith("signac_job_document")

    files = [f for f in files if is_job_sub_document(f)]
    merged_data = []
    merged_history = []
    cache = None
    for f in files:
        with open(Path(root) / f) as fh:
            job_doc = json.load(fh)
            for record in job_doc["data"]:
                merged_data.append(record)
            for record in job_doc["history"]:
                merged_history.append(record)
            # TODO handle inconsistent cache
            if not cache:
                cache = job_doc["cache"]
    job.doc = {"data": merged_data, "history": merged_history, "cache": cache}


def get_latest_log(job: Job) -> str:
    """Find latest log in job.id/case/folder

    Returns: path to latest solver log
    """
    from ..OpenFOAM.case import OpenFOAMCase

    case_path = Path(job.path + "/case")
    # in case obr status is called directly after initialization
    # this would also fail if there was no case directory
    if not case_path.exists():
        return ""

    case = OpenFOAMCase(case_path, job)
    solver = case.controlDict.get("application")

    history = job.doc["history"]
    for entry in history[::-1]:
        if solver in entry().get("cmd", ""):
            log_path = case_path / entry["log"]
            if not log_path.exists():
                continue
            return entry["log"]
    return ""


def get_timestamp_from_log(log) -> str:
    """gets the timestamp part from an log file"""
    log_name = Path(log).stem
    before = log_name.split("_")[0]
    return log_name.replace(before + "_", "")


def find_solver_logs(job: Job) -> Generator[tuple, None, None]:
    """Find and return all solver log files, campaign info and tags from job instances"""
    case_path = Path(job.path)
    if not case_path.exists():
        return

    root, campaigns, _ = next(os.walk(case_path))

    def find_tags(path: Path, tags: list, tag_mapping):
        """Recurses into subfolders of path until a system folder is found

        Returns:
          Dictionary mapping paths to tags -> tag
        """
        _, folder, _ = next(os.walk(path))
        is_case = len(folder) == 0
        if is_case:
            tag_mapping[str(path)] = tags
        else:
            for f in folder:
                tags_copy = deepcopy(tags)
                tags_copy.append(f)
                find_tags(path / f, tags_copy, tag_mapping)
        return tag_mapping

    for campaign in campaigns:
        # check if case folder
        tag_mapping = find_tags(case_path / campaign, [], {})

        for path, tags in tag_mapping.items():
            root, _, files = next(os.walk(path))
            for file in files:
                if "Foam" in file and file.endswith("log"):
                    yield f"{root}/{file}", campaign, tags


def execute_shell(steps: list[str], job) -> bool:
    """execute a list of shell commands on a job"""
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
    return ret


def link_folder_to_copy(source: Path) -> Path:
    """Given a path this functions converts all symlinked files into copies
    This file does not delete the created .bck folder, neither does it recurse
    into subfolders.

    Returns: path of the backup folder
    -------
    """
    import os

    source_bck = Path(str(source) + ".bck")
    check_output(["mv", source, source_bck])
    check_output(["mkdir", source])
    src_root, folder, files = next(os.walk(source_bck))
    targ_root, _, _ = next(os.walk(source))
    src_root = Path(src_root)
    targ_root = Path(targ_root)
    for fn in files:
        src_file_path = src_root / fn
        if src_file_path.is_symlink():
            logging.warning(
                f"{os.readlink(src_file_path)} is a symlink\n"
                "Some openfoam versions refuse to decompose files if content of"
                " zero folder are symlinks. Thus we temporarily copy this file."
            )
            src_file_path = src_file_path.resolve()
            target_file_path = targ_root / fn
            check_output(["cp", src_file_path, target_file_path])
    for fold in folder:
        src_fold_path = src_root / fold
        target_path = targ_root / fn
        check_output(["cp", "-r", src_fold_path, target_path])
    return source_bck


class TemporaryFolder:
    """A class to handle temporary folder, taking care of copying and
    deleting the resulting folder"""

    def __init__(self, source: Path, target: Path, delink=False):
        self.source = source
        self.target = target
        self.delink = delink
        check_output(["cp", "-r", source, target])

        if self.delink:
            self.delink_folder = DelinkFolder(self.target)

    def __del__(self):
        shutil.rmtree(str(self.target))


class DelinkFolder:
    """A class to handle delinking and copying the contents of a folder. Taking care of copying and
    deleting the resulting folder"""

    def __init__(self, source: Path):
        self.source = source
        self.source_bck = link_folder_to_copy(source)

    def __del__(self):
        shutil.rmtree(str(self.source))
        check_output(["mv", self.source_bck, self.source])


def find_time_folder(path: Path) -> list[Path]:
    """Given a path this function returns all time folder"""

    def is_time(s: str) -> bool:
        try:
            float(s)
            return True
        except:
            return False

    _, fs, _ = next(os.walk(self.path))
    ret = [self.path / f for f in fs if is_time(f)]
    ret.sort()
    return ret

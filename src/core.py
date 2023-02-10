#!/usr/bin/env python3
import os
import subprocess
import re
import hashlib
from pathlib import Path
from subprocess import check_output
from functools import wraps


def parse_variables_impl(in_str, args, domain):
    ocurrances = re.findall(r"\${{" + domain + "\.(\w+)}}", in_str)
    for inst in ocurrances:
        in_str = in_str.replace("${{" + domain + "." + inst + "}}", args.get(inst, ""))
    return in_str


def parse_variables(in_str):
    in_str = parse_variables_impl(in_str, os.environ, "env")
    return in_str


def logged_execute(cmd, path, doc):
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected
    """
    from datetime import datetime

    check_output(["mkdir", "-p", ".obr_store"], cwd=path)
    d = doc.get("obr", {})
    cmd_str = " ".join(cmd)
    cmd_str = cmd_str.replace(".", "_dot_").split()
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
        print(
            "SubprocessError:",
            __file__,
            __name__,
            e,
            " check: 'obr find --state failure' for more info",
        )
        log = e.output.decode("utf-8")
        state = "failure"
    except FileNotFoundError as e:
        print(__file__, __name__, e)
        log = cmd + " not found"
        state = "failure"
    except Exception as e:
        print(__file__, __name__, e)
        print("General Execption", __file__, __name__, e, e.output)
        log = ret
        state = "failure"

    timestamp = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    if log and len(log) > 1000:
        h = hashlib.new("md5")
        h.update(log.encode())
        hash_ = h.hexdigest()
        fn = f"{cmd_str}_{timestamp}.log"
        with open(path / fn, "w") as fh:
            fh.write(log)
        log = fn

    res = d.get(cmd_str, [])

    res.append(
        {
            "type": "shell",
            "log": log,
            "state": state,
            "flags": flags,
            "timestamp": timestamp,
        }
    )
    d[cmd_str] = res
    doc["obr"] = d


def logged_func(func, doc, **kwargs):
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected
    """
    from datetime import datetime

    d = doc.get("obr", {})
    cmd_str = func.__name__
    try:
        func(**kwargs)
        state = "success"
    except Exception as e:
        print("Failure", __file__, __name__, func.__name__, kwargs, e)
        state = "failure"

    res = d.get(cmd_str, [])
    res.append(
        {
            "args": str(kwargs),
            "state": state,
            "type": "obr",
            "timestamp": str(datetime.now()),
        }
    )
    d[cmd_str] = res
    doc["obr"] = d


def execute(steps: list[str], job) -> bool:
    path = Path(job.path) / "case"
    if not steps:
        return

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

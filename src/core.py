#!/usr/bin/env python3
import os
import subprocess
import re
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
    res = doc.get("obr", {})
    cmd_str = " ".join(cmd)
    # print("execute shell command: ", cmd)
    try:
        ret = check_output(cmd, cwd=path, stderr=subprocess.STDOUT).decode("utf-8")
        cmd_str = cmd_str.replace(".", "_dot_")
        res[cmd_str] = {"log": ret, "state": "success"}
    except subprocess.SubprocessError as e:
        print("SubprocessError:", __file__, __name__, e, e.output, e.stderr)
        log = e.output.decode("utf-8")
        res[cmd_str] = {"log": log, "state": "failure"}
    except FileNotFoundError as e:
        print(__file__, __name__, e)
        log = cmd + " not found"
        res[cmd_str] = {"log": log, "state": "failure"}
    except Exception as e:
        print(__file__, __name__, e)
        print("General Execption", __file__, __name__, e, e.output)
        log = ret
        res[cmd_str] = {"log": log, "state": "failure"}
    doc["obr"] = res


def logged_func(func, doc, **kwargs):
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected
    """
    res = doc.get("obr", {})
    # print("execute obr function: ", func.__name__, kwargs)
    try:
        func(**kwargs)
        res[func.__name__] = {"args": str(kwargs), "state": "success"}
    except Exception as e:
        print("Failure", __file__, __name__, func.__name__, kwargs, e)
        res[func.__name__] = {"args": str(kwargs), "state": "failed"}
    doc["obr"] = res


def execute(steps, job):
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
            src = fn.resolve()
            check_output(["rm", fn])

    if isinstance(fns, list):
        for fn in fns:
            unlink(fn)
    else:
        unlink(fns)


def decorator_modifies_file(fns=["path"]):
    def wrapper(f, *jobsp):
        @wraps(f)
        def wrapped(self, *args):
            print("called wrapped", *args, fn)
            for fn in fns:
                print(fn)
                modifies_file(getattr(self, fn))
            f(self, *args)

        return wrapped

    return wrapper


def decorator_writes_files(fns=["path"]):
    def wrapper(f):
        @wraps(f)
        def wrapped(self, *args):
            for fn in fns:
                writes_file(getattr(self, fn))
            f(self, *args)

        return wrapped

    return wrapper

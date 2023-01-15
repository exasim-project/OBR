#!/usr/bin/env python3
import os
import sys
import subprocess
import re
import json
from pathlib import Path
from subprocess import check_output


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
    print("execute shell command: ", cmd)
    try:
        ret = check_output(cmd, cwd=path).decode("utf-8")
        res[cmd_str] = {"log": ret, "state": "success"}
    except subprocess.SubprocessError as e:
        log = e.output.decode("utf-8")
        res[cmd_str] = {"log": log, "state": "failure"}
    except FileNotFoundError as e:
        log = cmd + " not found"
        res[cmd_str] = {"log": log, "state": "failure"}
    doc["obr"] = res


def logged_func(func, doc, **kwargs):
    """execute cmd and logs success

    If cmd is a string, it will be interpreted as shell cmd
    otherwise a callable function is expected
    """
    res = doc.get("obr", {})
    print("execute obr function: ", func.__name__, kwargs)
    try:
        func(**kwargs)
        res[func.__name__] = {"args": str(kwargs), "state": "success"}
    except Exception as e:
        print(e)
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

    steps_filt = map(lambda x: " ".join(x.split()), steps_filt)

    for step in steps_filt:
        if not step:
            continue
        step = parse_variables(step)
        cmd = step.split(" ")
        logged_execute(step, path, job.doc)
    return True

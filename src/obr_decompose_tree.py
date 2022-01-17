#!/usr/bin/env python3
"""
    run ogl benchmarks

    Usage:
        obr_run_cases.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --np=<nd>           Number of sub domains.
        --folder=<folder>   Target folder  [default: Test].
        --filter=<json> pass the parameters for given parameter study
"""


from docopt import docopt
from OBR.metadata import versions
from OBR import setFunctions as sf
from OBR import CaseRunner as cr
from OBR import ResultsAggregator as ra
from OBR.OpenFOAMCase import OpenFOAMCase
from pathlib import Path
import os
import json
import datetime
from subprocess import check_output


def can_be_symlinked(path):
    path = Path(path)
    num_procs = path.parts[-2]
    variation_root = path / "../../../.."
    _, dirs, _ = next(os.walk(variation_root))
    for d in dirs:
        variation = (
            variation_root / d / "Variation_mpiRank" / num_procs / "base" / "processor0"
        )
        if variation.exists():
            return variation.parents[0].resolve()
    return False


def symlink_all_procs(link_base, current):
    link_base = Path(link_base)
    current = Path(current)
    _, dirs, _ = next(os.walk(link_base))
    procs = [proc for proc in dirs if "processor" in proc]
    if link_base == current:
        print("link_base is current target, skipping")
        return
    try:
        for proc in procs:
            Path(current / proc).symlink_to(link_base / proc, True)
    except Exception as e:
        print("can not symlink: ", e)


def decompose_tree(kwargs):
    metadata = {
        "node_data": {
            "host": sf.get_process(["hostname"]),
            "top": sf.get_process(["top", "-bn1"]).split("\n")[:15],
            "uptime": sf.get_process(["uptime"]),
            "libOGL.so": sf.get_process(
                ["md5sum", os.getenv("FOAM_USER_LIBBIN") + "/libOGL.so"]
            ),
        },
    }
    metadata.update(versions)
    print(metadata)

    arguments = docopt(__doc__, version=metadata["OBR_VERSION"])

    start = datetime.datetime.now()
    for root, folder, files in os.walk(Path(arguments["folder"]).expanduser()):
        if arguments.get("filter"):
            filt = arguments.get("filter").split(",")
            filt = [f in root for f in filt]
            if any(filt):
                continue
        if not "mpiRank" in root:
            continue
        if "obr.json" in files:
            symlink_base = can_be_symlinked(root)
            if symlink_base:
                print("symlinking", root, "to", symlink_base)
                symlink_all_procs(symlink_base, root)
            else:
                print("decomposing", root)
                sf.check_output(["decomposePar", "-force"], cwd=root)
    end = datetime.datetime.now()
    print("run all selected cases in {} minutes".format((end - start).total_minutes()))

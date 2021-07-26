#!/usr/bin/env python3
"""
    run ogl benchmarks

    Usage:
        obr_run_cases.py [options]

    Options:
        -h --help           Show this screen
        -v --version        Print version and exit
        --clean             Remove existing cases [default: False].
        --filter=<json> pass the parameters for given parameter study
        --folder=<folder>   Target folder  [default: Test].
"""


from docopt import docopt
from OBR.metadata import versions
from OBR import setFunctions as sf
from pathlib import Path
import os
import json
from subprocess import check_output

if __name__ == "__main__":
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

    arguments = docopt(__doc__, version=metadata["OBR_VERSION"])

    for root, folder, files in os.walk(Path(arguments["--folder"]).expanduser()):
        if "obr.json" in files:
            print("read json file", root)
            fn = Path(root) / "obr.json"
            with open(fn, "r") as parameters_handle:
                parameters_str = parameters_handle.read()
            solver_arguments = json.loads(parameters_str)
            cmd = solver_arguments["exec"]
            print(check_output(cmd, cwd=root))

    metadata.update(versions)
    print(metadata)

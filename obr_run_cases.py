#!/usr/bin/env python3

from OBR.metadata import versions
from OBR import setFunctions as sf

if __name__ == "__main__":
    metadata = {
        "node_data": {
            "host": sf.get_process(["hostname"]),
            "top": sf.get_process(["top", "-bn1"]).split("\n")[:15],
            "uptime": sf.get_process(["uptime"]),
        },
    }

    metadata.update(versions)
    print(metadata)

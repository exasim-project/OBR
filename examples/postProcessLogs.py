from Owls.parser.LogFile import LogFile, LogKey
from pathlib import Path
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from collections import defaultdict
from obr.signac_wrapper.operations import JobCache
from obr.OpenFOAM.case import OpenFOAMCase


def append_update(d, key, updater):
    prev_res = d.get(key, [])
    prev_res.append(updater())
    d[key] = prev_res


def call(jobs):
    col_iter = ["init", "final", "iter"]
    col_time = ["time"]
    p_steps = ["_p", "_pFinal"]
    U_components = ["_Ux", "_Uy", "_Uz"]

    pIter = LogKey("Solving for p", col_iter, p_steps)
    UIter = LogKey("Solving for U", col_iter, U_components)
    Time = LogKey("ExecutionTime", ["ExecutionTime", "ClockTime"])

    logKeys = [pIter, UIter, Time]

    cache = JobCache(jobs)

    for job in jobs:
        solver = job.doc["obr"].get("solver")

        # skip jobs without a solver
        if not solver:
            continue

        case_path = Path(job.path) / "case"
        of_case = OpenFOAMCase(case_path, job)

        # get latest log
        runs = job.doc["obr"][solver]
        solver = job.sp["solver"]
        # pop old results
        for k in CombinedKeys:
            try:
                job.doc["obr"].pop(k)
                job.doc["obr"].pop(k + "_rel")
            except Exception as e:
                print(e)

        job.doc["obr"]["nCells"] = cache.search_parent(job, "nCells")
        job.doc["obr"]["nSubDomains"] = int(
            of_case.decomposeParDict.get("numberOfSubdomains")
        )

        post_pro_dict = {}
        post_pro_dict["numberRuns"] = len(runs)

        for i, run in enumerate(runs):
            log_path = case_path / run["log"]

            # parse logs for given keys
            log_file = LogFile(logKeys)
            try:
                df = log_file.parse_to_df(log_path)
            except Exception as e:
                print("failed parsing log", log_path, e)
                continue

            # write information from header
            append_update(post_pro_dict, "host", lambda: log_file.header.host)

            # write average times to job.doc
            print(df)
            # for k in CombinedKeys:
            #     try:
            #         append_update(
            #             post_pro_dict,
            #             "time_" + k,
            #             lambda: df.iloc[1:].mean()["time_" + k],
            #         )
            #     except Exception as e:
            #         print(e)

            # write iters to job.doc

            # check if run was completed
            append_update(post_pro_dict, "completed", lambda: log_file.is_complete)

        print(post_pro_dict)
        job.doc["obr"]["postProcessing"] = post_pro_dict

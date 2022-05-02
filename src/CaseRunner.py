#!/usr/bin/env python3
""" This module implements Runner needed to run cases and collect statistics """
from subprocess import check_output
import datetime
import sys
import Owls as ow
import setFunctions as sf
from OpenFOAMCase import OpenFOAMCase
import hashlib
from copy import deepcopy


class SlurmCaseRunner:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.p = arguments["partition"]
        self.t = arguments["time"]
        self.task_per_node = int(arguments.get("ntasks_per_node", 1))

    def run(self, path, execution_parameter, case_parameter):
        import time
        from pathlib import Path

        run_path = Path(path)

        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)
        execution_parameter["prefix"] = [
            "mpirun",
            "--bind-to",
            "core",
            "--map-by",
            "core",
        ]
        execution_parameter["flags"] = ["-parallel"]
        app_cmd_prefix = execution_parameter.get("prefix", [])
        app_cmd_flags = execution_parameter.get("flags", [])
        app_cmd = (
            app_cmd_prefix + execution_parameter["exec"] + app_cmd_flags + [" > log"]
        )

        print("writing run.sh to", run_path)
        with open(run_path / "run.sh", "w+") as fh:
            fh.write("#!/bin/bash\n")
            fh.write(" ".join(app_cmd))

        number_nodes = max(int(sub_domains / self.task_per_node), 1)
        tasks = min(sub_domains, self.task_per_node)

        sbatch_cmd = [
            "sbatch",
            "-J",
            str(sub_domains),
            "-p",
            str(self.p),
            "-N",
            str(number_nodes),
            "-t",
            str(self.t),
        ]

        if self.p == "accelerated":
            sbatch_cmd += [
                "--ntasks-per-node",
                str(tasks),
                "--gpus-per-node",
                str(tasks),
            ]
        else:
            sbatch_cmd += [
                "--ntasks-per-node",
                str(tasks),
            ]

        sbatch_cmd.append("run.sh")

        print("call", sbatch_cmd)
        check_output(sbatch_cmd, cwd=run_path)


class ResultsCollector:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.log_name = arguments["log_name"]

    def hash_and_store_log(self, ret, path, log_fold):
        log_hash = hashlib.md5(ret.encode("utf-8")).hexdigest()
        log_path = path / self.log_name
        log_path = log_path.with_suffix(".log")
        log_str = ret
        log_file = log_fold / self.log_name
        with open(log_file, "a") as log_handle:
            print("writing to log", log_file, type(log_str))
            log_str_ = "hash: {}\n{}{}\n".format(log_hash, log_str, "=" * 80)
            log_handle.write(log_str_)
        return log_hash

    def run(self, path, execution_parameter, case_parameter):
        import time
        from pathlib import Path

        run_path = Path(path)

        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)

        with open(run_path / "log","r",encoding='utf-8') as fh:
            ret = fh.read()
        log_hash = self.hash_and_store_log(ret, case.path, self.results.log_fold)

        self.results.set_case(case, execution_parameter, case_parameter)

        self.results.add(
            timestamp=str(datetime.datetime.utcnow()),
            log_id=log_hash,
            run_time=0,
        )


class LocalCaseRunner:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.time_runs = int(arguments["time_runs"])
        self.min_runs = int(arguments["min_runs"])
        self.continue_on_failure = arguments["continue_on_failure"]
        self.test_run = arguments["single_run"]
        self.fail = arguments["fail_on_error"]
        self.log_name = arguments["log_name"]
        self.mpi_flags = arguments["mpi_flags"]

    def continue_running(self, accumulated_time, number_of_runs):
        if self.test_run and number_of_runs == 1:
            return False
        else:
            return accumulated_time < self.time_runs or number_of_runs < self.min_runs

    def hash_and_store_log(self, ret, path, log_fold):
        log_hash = hashlib.md5(ret).hexdigest()
        log_path = path / self.log_name
        log_path = log_path.with_suffix(".log")
        log_str = ret.decode("utf-8")
        log_file = log_fold / self.log_name
        with open(log_file, "a") as log_handle:
            print("writing to log", log_file, type(log_str))
            log_str_ = "hash: {}\n{}{}\n".format(log_hash, log_str, "=" * 80)
            log_handle.write(log_str_)
        return log_hash

    def run(self, path, execution_parameter, case_parameter):
        import time
        from pathlib import Path

        run_path = Path(path)

        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)
        if sub_domains:
            execution_parameter["prefix"] = [
                "mpirun",
                "--bind-to",
                "core",
                "-np",
                str(sub_domains),
            ]
            execution_parameter["flags"] = ["-parallel"]
        app_cmd_prefix = execution_parameter.get("prefix", [])
        app_cmd_flags = execution_parameter.get("flags", [])
        app_cmd = app_cmd_prefix + execution_parameter["exec"] + app_cmd_flags

        self.results.set_case(case, execution_parameter, case_parameter)

        # timed runs
        accumulated_time = 0
        number_of_runs = 0
        ret = ""

        # on first run get number of iterations and write log if demanded
        iterations = 0
        print("running", app_cmd, case.path)
        while self.continue_running(accumulated_time, number_of_runs):
            number_of_runs += 1
            try:
                start = datetime.datetime.now()
                ret = check_output(app_cmd, cwd=case.path, timeout=180 * 60)
                end = datetime.datetime.now()
                run_time = (end - start).total_seconds()  # - self.init_time
                accumulated_time += run_time
            except Exception as e:
                print(e)
                if not self.continue_on_failure:
                    break
                print("Exception running while running the case", e)
                if self.fail:
                    sys.exit(1)
                break

            log_hash = self.hash_and_store_log(ret, case.path, self.results.log_fold)

            self.results.add(
                timestamp=str(datetime.datetime.utcnow()),
                log_id=log_hash,
                run_time=run_time,
            )

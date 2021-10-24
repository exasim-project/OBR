#!/usr/bin/env python3
""" This module implements Runner needed to run cases and collect statistics """
from subprocess import check_output
import datetime
import sys
import Owls as ow
import OBR.setFunctions as sf
from OBR.OpenFOAMCase import OpenFOAMCase
import hashlib
from copy import deepcopy


class CaseRunner:
    def __init__(self, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.time_runs = int(arguments["--time_runs"])
        self.min_runs = int(arguments["--min_runs"])
        self.continue_on_failure = arguments["--continue_on_failure"]
        self.test_run = arguments["--test-run"]
        self.fail = arguments["--fail_on_error"]

    def continue_running(self, accumulated_time, number_of_runs):
        if self.test_run and number_of_runs == 1:
            return False
        else:
            return accumulated_time < self.time_runs or number_of_runs < self.min_runs

    def hash_and_store_log(self, ret, path, log_fold):
        log_hash = hashlib.md5(ret).hexdigest()
        log_path = path / "logs"
        log_path = log_path.with_suffix(".log")
        log_str = ret.decode("utf-8")
        log_file = log_fold / "logs"
        with open(log_file, "a") as log_handle:
            print("writing to log", log_file, type(log_str))
            log_str_ = "hash: {}\n{}{}\n".format(log_hash, log_str, "=" * 80)
            log_handle.write(log_str_)
        return log_hash

    def run(self, path, execution_parameter, case_parameter):
        import time
        from pathlib import Path

        path_orig = Path(path)
        run_path = Path(path).parents[0] / str(int(time.time()))

        check_output(["cp", "-r", path_orig, run_path])

        case = OpenFOAMCase(run_path)
        sub_domains = sf.get_number_of_subDomains(case.path)
        if sub_domains:
            execution_parameter["prefix"] = ["mpirun", "-np", str(sub_domains)]
            execution_parameter["flags"] = ["-parallel"]
        app_cmd_prefix = execution_parameter.get("prefix", [])
        app_cmd_flags = execution_parameter.get("flags", [])
        app_cmd = app_cmd_prefix + execution_parameter["exec"] + app_cmd_flags

        self.results.set_case(case, execution_parameter, case_parameter)

        # warm up run
        warm_up = self.warm_up(case, app_cmd)

        # timed runs
        accumulated_time = 0
        number_of_runs = 0
        ret = ""

        # on first run get number of iterations and write log if demanded
        iterations = 0
        print("running", app_cmd)
        while self.continue_running(accumulated_time, number_of_runs):
            number_of_runs += 1
            try:
                start = datetime.datetime.now()
                ret = check_output(app_cmd, cwd=case.path, timeout=60 * 60)
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

            self.results.add(log_id=log_hash, run_time=run_time)

            check_output(["rm", "-rf", run_path])

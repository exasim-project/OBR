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

    def warm_up(self, case, solver_cmd):
        original_end_time = sf.get_end_time(case.controlDict)
        deltaT = sf.read_deltaT(case.controlDict)

        sf.set_end_time(case.controlDict, 1 * deltaT)

        # first warm up run
        print("Start warm up run #1")
        check_output(solver_cmd, cwd=case.path, timeout=15 * 60)
        print("Done warm up run #1")

        # timed warmup run
        start = datetime.datetime.now()
        print("Start timed warm up run #2")
        check_output(solver_cmd, cwd=case.path, timeout=15 * 60)
        print("Done timed warm up run #2")
        end = datetime.datetime.now()
        sf.set_end_time(case.controlDict, original_end_time)
        return (end - start).total_seconds()

    def post_pro_logs_for_timings(self, ret):
        try:
            log_str = ret.decode("utf-8")
            keys_timings = {
                "linear solve p": ["linear_solve"],
                "linear solve U": ["linear_solve"],
            }
            ff = ow.read_log_str(log_str, deepcopy(keys_timings))
            ff = ff.after(0)
            return [
                (ff[ff.index.get_level_values("Key") == k]).sum()["linear_solve"]
                for k in keys_timings.keys()
            ]
        except Exception as e:
            print("logs_for_timings", e)
            return (0, 0)

    def post_pro_logs_for_iters(self, path, ret, solver, log_fold):
        try:
            log_hash = hashlib.md5(ret).hexdigest()
            log_path = path / log_hash
            log_path = log_path.with_suffix(".log")
            log_str = ret.decode("utf-8")
            with open(log_path, "w") as log_handle:
                log_handle.write(log_str)
            check_output(["cp", log_path, log_fold])
            keys = {
                "{}:  Solving for {}".format(s, f): [
                    "init_residual",
                    "final_residual",
                    "iterations",
                ]
                for f, s in zip(["p", "U"], solver)
            }
            ff = ow.read_log_str(log_str, deepcopy(keys))
            return log_hash, [
                (ff[ff.index.get_level_values("Key") == k]).sum()["iterations"]
                for k in keys.keys()
            ]
        except Exception as e:
            print("Exception processing logs", e, ret)
            return 0, [0, 0]

    def run(self, path, parameter):

        case = OpenFOAMCase(path)
        solver_cmd = parameter["exec"]

        self.results.set_case(case, parameter)

        # warm up run
        warm_up = self.warm_up(case, solver_cmd)

        # timed runs
        accumulated_time = 0
        number_of_runs = 0
        ret = ""

        # on first run get number of iterations and write log if demanded
        iterations = 0
        print("running", solver_cmd)
        while self.continue_running(accumulated_time, number_of_runs):
            number_of_runs += 1
            try:
                start = datetime.datetime.now()
                ret = check_output(solver_cmd, cwd=case.path, timeout=15 * 60)
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

            time_u, time_p = self.post_pro_logs_for_timings(ret)

            if number_of_runs == 1:
                solver = self.results.get_solver(case)
                log_hash, iterations = self.post_pro_logs_for_iters(
                    case.path, ret, solver, self.results.log_fold
                )

            self.results.add(
                log_hash,
                warm_up,
                run_time,
                iterations[0],
                iterations[1],
                time_p,
                time_u,
            )

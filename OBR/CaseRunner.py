#!/usr/bin/env python3
""" This module implements Runner needed to run cases and collect statistics """
from subprocess import check_output
import datetime


class CaseRunner:
    def __init__(self, solver, results_aggregator, arguments):
        self.results = results_aggregator
        self.arguments = arguments
        self.solver = solver
        self.time_runs = int(arguments["--time_runs"])
        self.min_runs = int(arguments["--min_runs"])

    def run(self, case):

        for processes in [1]:
            print("start runs", processes)

            # self.executor.prepare_enviroment(processes)

            self.results.set_case(
                domain=case.query_attr("domain", "").name,
                executor=case.query_attr("executor", ""),
                solver=case.query_attr("solver", ""),
                number_of_iterations=0,  # self.iterations,
                resolution=case.query_attr("cells", ""),
                processes=processes,
            )
            accumulated_time = 0
            iters = 0
            ret = ""
            while accumulated_time < self.time_runs or iters < self.min_runs:
                iters += 1
                start = datetime.datetime.now()
                success = 0
                try:
                    print(case.path)
                    ret = check_output([self.solver], cwd=case.path, timeout=15 * 60)
                    success = 1
                except Exception as e:
                    print(e)
                    break
                end = datetime.datetime.now()
                run_time = (end - start).total_seconds()  # - self.init_time
                self.results.add(run_time, success)
                accumulated_time += run_time
            # self.executor.clean_enviroment()
            try:
                with open(
                    self.log_path.with_suffix("." + str(processes)), "a+"
                ) as log_handle:
                    log_handle.write(ret.decode("utf-8"))
            except Exception as e:
                print(e)
                pass

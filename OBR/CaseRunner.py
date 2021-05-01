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

        processes = case.get_processes()
        print("start runs processes", processes)
        for process in processes:

            # self.executor.prepare_enviroment(processes)

            self.results.set_case(
                domain=case.query_attr("domain", "").name,
                executor=case.query_attr("domain", "").executor.name,
                solver=case.query_attr("get_solver", []),
                preconditioner=case.query_attr("preconditioner", "").name,
                number_of_iterations=0,  # self.iterations,
                resolution=case.query_attr("cells", ""),
                processes=process,
            )
            accumulated_time = 0
            iters = 0
            ret = ""
            while accumulated_time < self.time_runs or iters < self.min_runs:
                iters += 1
                start = datetime.datetime.now()
                success = 0
                try:
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
            # TODO FIXME
            # Sets enviroment for next run
            try:
                print("set processes", process)
                case.others[0].domain.executor.enviroment_setter.set_up()
            except:
                pass
            try:
                log_path = case.path / "log"
                log_path = log_path.with_suffix("." + str(process))
                self.results.write_comment(["Log " + str(log_path)], prefix="LOG: ")
                self.results.write_comment(
                    ret.decode("utf-8").split("\n"), prefix="LOG: "
                )
            except Exception as e:
                print(e)
                pass

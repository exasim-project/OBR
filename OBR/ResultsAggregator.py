#!/usr/bin/env python3

from pathlib import Path
from OBR import setFunctions as sf


class Results:
    """ A class to collect results and writ to a csv file """

    def __init__(self, fn):
        self.fn = Path(fn)

        self.columns = [
            "executor_p",
            "solver_p",
            "preconditioner_p",
            "executor_U",
            "solver_U",
            "preconditioner_U",
            "resolution",
            "processes",
            "node",
            "log_id",
            "setup_time",
            "run_time",
            "number_of_iterations",
            "linear_solve_p",
            "linear_solve_U",
        ]

        self.current_col_vals = []
        self.report_handle = open(self.fn, "a+", 1)
        self.report_handle.write(",".join(self.columns) + "\n")

    def write_comment(self, comment, prefix=""):
        for line in comment:
            self.report_handle.write("#" + line + "\n")

    def get_solver(self, case):
        return [
            sf.get_solver(case.fvSolution, "p"),
            sf.get_solver(case.fvSolution, "U"),
        ]

    def set_case(self, case, args):
        import socket

        self.current_col_vals = [
            sf.get_executor(case.fvSolution, "p"),
            sf.get_preconditioner(case.fvSolution, "p"),
            sf.get_solver(case.fvSolution, "p"),
            sf.get_executor(case.fvSolution, "U"),
            sf.get_preconditioner(case.fvSolution, "U"),
            sf.get_solver(case.fvSolution, "U"),
            args["resolution"],
            args["processes"],
            socket.gethostname(),
        ]
        print(self.current_col_vals)

    def add(self, log, warm_up, run, iterations, linear_p, linear_u):
        """ Add results and success status of a run and write to file """
        outp = self.current_col_vals + [
            log,
            warm_up,
            run,
            iterations,
            linear_p,
            linear_u,
        ]
        outps = ",".join(map(str, outp))
        print("writing to report", outps)
        self.report_handle.write(outps + "\n")

    def close_file(self):
        close(self.report_handle)

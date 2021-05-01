#!/usr/bin/env python3

from pathlib import Path


class Results:
    """ A class to collect results and writ to a csv file """

    def __init__(self, fn, fields):
        self.fn = Path(fn)
        fields = ["solver-" + f for f in fields]

        self.columns = (
            [
                "backend",
                "executor",
            ]
            + fields
            + [
                "preconditioner",
                "number_of_iterations",
                "resolution",
                "processes",
                "run_time",
                "success",
            ]
        )
        self.current_col_vals = []
        self.report_handle = open(self.fn, "a+", 1)
        self.report_handle.write(",".join(self.columns) + "\n")

    def set_case(
        self,
        domain,
        executor,
        solver,
        preconditioner,
        number_of_iterations,
        resolution,
        processes,
    ):
        self.current_col_vals = (
            [
                domain,
                executor,
            ]
            + solver
            + [
                preconditioner,
                number_of_iterations,
                resolution,
                processes,
            ]
        )

    def add(self, run, success):
        """ Add results and success status of a run and write to file """
        outp = self.current_col_vals + [run, success]
        outps = ",".join(map(str, outp))
        print(outps)
        self.report_handle.write(outps + "\n")

    def close_file(self):
        close(self.report_handle)

#!/usr/bin/env python3


class Case:
    def __init__(self, variation, parent_path="."):
        self.variation = variation

    def copy_base(self, src, dst):
        print("copying base case", src, dst)
        check_output(["cp", "-r", src, dst])

    def set_matrix_solver(self, fn):
        print("setting solver", fn)
        matrix_solver = self.executor.prefix + self.solver
        # fmt: off
        solver_str = (
            '"p.*"{\\n'
            + "solver {};\
\\ntolerance {};\
\\nrelTol 0.0;\
\\nsmoother none;\
\\npreconditioner {};\
\\nminIter {};\
\\nmaxIter 10000;\
\\nupdateSysMatrix no;\
\\nsort yes;\
\\nexecutor {};".format(
                matrix_solver,
                self.tolerance,
                self.preconditioner,
                self.iterations,
                self.executor.executor
            )
        )
        # fmt: on
        sed(fn, "p{}", solver_str)

    def run(self, results_accumulator, min_runs, time_runs):
        if self.is_base_case:
            return

        print("start runs")
        for processes in self.executor:
            print("start runs", processes)

            self.executor.prepare_enviroment(processes)

            self.results_accumulator.set_case(
                domain=self.executor.domain,
                executor=self.executor.executor,
                solver=self.solver,
                number_of_iterations=self.iterations,
                resolution=self.resolution,
                processes=processes,
            )
            accumulated_time = 0
            iters = 0
            ret = ""
            while accumulated_time < time_runs or iters < min_runs:
                iters += 1
                start = datetime.datetime.now()
                success = 0
                try:
                    ret = check_output([self.of_solver], cwd=self.path, timeout=15 * 60)
                    success = 1
                except:
                    break
                end = datetime.datetime.now()
                run_time = (end - start).total_seconds()  # - self.init_time
                self.results_accumulator.add(run_time, success)
                accumulated_time += run_time
            self.executor.clean_enviroment()
            try:
                with open(
                    self.log_path.with_suffix("." + str(processes)), "a+"
                ) as log_handle:
                    log_handle.write(ret.decode("utf-8"))
            except Exception as e:
                print(e)
                pass

        self.executor.current_num_processes = 1

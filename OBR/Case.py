#!/usr/bin/env python3


class Case:
    def __init__(self, variation, parent_path="."):
        self.variation = variation
        self.parent_path = parent_path

        # self.variable = None
        # self.preconditioner = preconditioner
        # self.is_base_case = is_base_case
        # self.test_base = test_base
        # self.of_base_case = "boxTurb16"
        # self.fields = "p"
        # self.tolerance = "1e-06"
        # self.resolution = resolution
        # self.executor = executor
        # self.solver = solver
        # self.iterations = iterations
        # self.base_case_path_ = base_case
        # self.results_accumulator = results
        # self.init_time = 0
        # self.of_solver = of_solver
        # self.of_tutorial_case = of_tutorial_case
        # self.of_tutorial_domain = of_tutorial_domain
        # self.number_of_processes = number_of_processes

    @property
    def base_path(self):
        return self.parent_path / self.variation.local_path

    @property
    def path(self):
        return self.base_path / self.variation.root.case

    @property
    def system_folder(self):
        return self.path / "system"

    @property
    def zero_folder(self):
        return self.path / "0"

    @property
    def init_p(self):
        return self.zero_folder / "p"

    @property
    def init_U(self):
        return self.zero_folder / "U.orig"

    @property
    def controlDict(self):
        return self.system_folder / "controlDict"

    @property
    def blockMeshDict(self):
        return self.system_folder / "blockMeshDict"

    @property
    def fvSolution(self):
        return self.system_folder / "fvSolution"

    def create(self):
        ensure_path(self.base_path)
        self.copy_base(self.variation.base_path, self.base_path)
        # self.set_matrix_solver(self.fvSolution)

    @property
    def base_case_path(self):
        return self.base_case_path_ / self.of_base_case

    @property
    def log_path(self):
        return self.path / "log"

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

        # if self.is_base_case:
        #     deltaT = 0.1 * 16 / self.resolution
        #     new_cells = "{} {} {}".format(
        #         self.resolution, self.resolution, self.resolution
        #     )
        #     set_cells(self.blockMeshDict, "16 16 16", new_cells)
        #     set_mesh_boundary_type_to_wall(self.blockMeshDict)
        #     set_p_init_value(self.init_p)
        #     set_U_init_value(self.init_U)
        #     add_libOGL_so(self.controlDict)
        #     set_end_time(self.controlDict, 10 * deltaT)
        #     set_deltaT(self.controlDict, deltaT)
        #     set_writeInterval(self.controlDict)
        #     clear_solver_settings(self.fvSolution)
        #     print("Meshing", self.path)
        #     check_output(["blockMesh"], cwd=self.path)
        #     return

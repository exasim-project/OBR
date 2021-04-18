#!/usr/bin/env python3
from itertools import product
from pathlib import Path


class OpenFOAMCase:

    parent_path_ = "."
    child = None

    def set_parent_path(self, parent_path):
        self.parent_path_ = parent_path

    @property
    def parent_path(self):
        return Path(self.parent_path_)

    @property
    def base_path(self):
        return self.parent_path

    @property
    def path(self):
        return self.base_path / self.child.local_path / self.child.root.case

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
        self.copy_base(self.child.cache_path, self.base_path)
        # self.set_matrix_solver(self.fvSolution)

    @property
    def base_case_path(self):
        return self.base_case_path_ / self.of_base_case

    @property
    def log_path(self):
        return self.path / "log"


class Setter(OpenFOAMCase):
    """base class to set case properties

    TODO merge with Executor
    needs to support following operations:
    - get solver prefix ie P or GKO or none

    """

    def __init__(self, name, child):
        self.others = []
        self.name = name
        self.child = child

    def set_enviroment_setter(self, enviroment_setter):
        self.enviroment_setter = enviroment_setter

    def set_root_case(self, root):
        self.root = root

    def set_up(self):
        self.enviroment_setter.case_name = self.child.root.case
        self.enviroment_setter.local_path = self.path
        self.enviroment_setter.set_up()
        for other in self.others:
            other.set_up()

    def clean_up(self):
        self.enviroment_setter.clean_up()
        for other in self.clean_up:
            other.clean_up()

    def combine(self, other):
        self.others.append(other)
        return self

    @property
    def own_path(self):
        return self.name

    @property
    def local_path(self):
        """returns just the base path of the current case
        ie 4/cuda-p-IR-BJ/
           |  |   |   |_ solver
           |  |   |______field
           |  |__________executor
           |___ previous setter from combine

        """
        ret = self.own_path
        for other in self.others:
            ret += "/" + other.name
        return Path(ret)


class CellSetter(Setter):
    def __init__(self, cells):
        self.cells = cells
        super().__init__(name="{}".format(cells), child=self)
        super().set_enviroment_setter(CellsPrepare(cells))

    @property
    def cache_path(self):
        return self.enviroment_setter.base_path(str(self.cells)) / self.root.case


class SolverSetter(Setter):
    def __init__(
        self,
        namespace,
        prefix,
        solver,
        field,
        child,
        preconditioner="none",
        tolerance="1e-06",
        min_iters="0",
        max_iters="1000",
        update_sys_matrix="no",
    ):

        super().__init__(name="{}-{}-{}".format(field, namespace, solver), child=child)
        self.prefix = prefix
        self.solver = solver
        self.preconditioner = preconditioner
        self.update_sys_matrix = update_sys_matrix
        self.tolerance = tolerance
        self.min_iters = min_iters
        self.max_iters = max_iters

    def set_up(self):
        print("setting solver")
        matrix_solver = self.prefix + self.solver
        executor = "none"
        if hasattr(self.child, "executor"):
            executor = self.child.executor
        # fmt: off
        solver_str = (
            '"p.*"{\\n'
            + "solver {};\
\\ntolerance {};\
\\nrelTol 0.0;\
\\nsmoother none;\
\\npreconditioner {};\
\\nminIter {};\
\\nmaxIter {};\
\\nupdateSysMatrix {};\
\\nsort yes;\
\\nexecutor {};".format(
                matrix_solver,
                self.tolerance,
                self.preconditioner,
                self.min_iters,
                self.max_iters,
                self.update_sys_matrix,
                executor
            )
        )
        # fmt: on
        print(solver_str)
        # sed(fn, "p{}", solver_str)


class CG(SolverSetter):
    def __init__(self, namespace, prefix, field):
        super().__init__(
            namespace=namespace, prefix=prefix, solver="CG", field=field, child=self
        )


class OFCG(CG):
    def __init__(self, field):
        super().__init__(namespace="OF", prefix="P", field=field)


class GKOExecutor:
    def __init__(self, name):
        self.name = name


class DefaultPrepareEnviroment:
    def __init__(self):
        pass

    def set_up(self):
        pass

    def clean_up(self):
        pass


class PrepareOMPMaxThreads:
    """ Sets the enviroment variable for OMP """

    def __init__(self):
        self.processes = 1

    def set_up(self):
        print(" use ", self.processes, " threads")
        os.environ["OMP_NUM_THREADS"] = str(self.processes)

    def clean_up(self):
        pass


class CachePrepare:
    """ copies cases from a base """

    def __init__(self, name):
        self.name = name

    def cache_path(self, path, case):
        return Path(path) / (self.name + "-cache") / case


class CellsPrepare(CachePrepare):
    """ sets the number of cells or copies from a base to avoid remeshing """

    def __init__(self, cells):
        super().__init__(name="mesh")
        self.cells = cells

    def set_up(self):
        # check if cache_path exists otherwise copy
        print(
            "copying from",
            self.cache_path(str(self.cells), self.case_name),
            " to ",
            self.local_path,
        )

    def clean_up(self):
        pass


class OpenFOAMTutorialCase:
    def __init__(self, tutorial_domain, solver, case):
        self.tutorial_domain = tutorial_domain
        self.solver = solver
        self.case = case

    @property
    def of_case_path(self):
        import os

        foam_tutorials = Path(os.environ["FOAM_TUTORIALS"])
        return Path(foam_tutorials / self.tutorial_domain / self.solver / self.case)


class OMP(GKOExecutor):
    def __init__(self):
        super().__init__(name="omp")


class GKOCG(CG):
    def __init__(self, gko_executor, field):
        super().__init__(namespace="GKO", prefix="GKO", field=field)
        self.executor = gko_executor

    @property
    def local_path(self):
        return Path(super().local_path + "-" + self.executor.name)


def combine(setters):
    """ combines a tuple of setters """
    primary = setters[0]
    primary.others.append(setters[1])
    return primary


class ParameterStudy:
    """A class to create a range of cases and potentially run them

    Here parameter studies are created the following way. First,
    a set of cases is defined via
    """

    def __init__(self, test_path, results_aggregator, setters):
        self.test_path = test_path
        self.results_aggregator = results_aggregator
        self.setters = setters

    def build_parameter_study(self): # test_path, results, executor, setter, arguments):
        cases = product(*self.setters)
        cases_combined = map(combine, cases)
        for case in cases_combined:
            print(case.path)
            case.set_up()
            # check if solver supported by executor
            # path = test_path / e.local_path / str(n.value)
            # exist = os.path.isdir(path)
            # skip = False
            # clean = arguments["--clean"]
            # if exist and clean:
            #     shutil.rmtree(path)
            #     skip = False
            # if exist and not clean:
            #     skip = True
            # is_base_case = False
            # base_case_path = (
            #     test_path / Path("base") / Path("p-" + s.name) / str(n.value)
            # )

            # if e.domain == "base":
            #     print("is base case")
            #     is_base_case = True

            # if not skip:
            #     case = Case(
            #         test_base=test_path,
            #         solver=s.name,
            #         executor=e,
            #         base_case=base_case_path,
            #         results=results,
            #         is_base_case=is_base_case,
            #     )
            #     n.run(case)
            #     case.create()
            #     case.run(
            #         results,
            #         int(arguments["--min_runs"]),
            #         int(arguments["--run_time"]),
            #     )
            # else:
            #     print("skipping")

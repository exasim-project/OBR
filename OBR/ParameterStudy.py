#!/usr/bin/env python3
import os
from itertools import product
from pathlib import Path
from subprocess import check_output
from copy import deepcopy

from . import setFunctions as sf


class OpenFOAMCase:

    parent_path_ = "."
    path_ = None
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
        if self.path_:
            return self.path_
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

    primary = None

    def __init__(self, name, child):
        self.others = []
        self.name = name
        self.child = child

    def set_enviroment_setter(self, enviroment_setter):
        self.enviroment_setter = enviroment_setter

    def set_root_case(self, root):
        self.root = root

    def set_up(self, test_path):
        self.enviroment_setter.case_name = self.child.root.case
        self.enviroment_setter.root = self.child.root.of_case_path
        self.enviroment_setter.local_path = self.path
        self.enviroment_setter.set_up(test_path)
        for other in self.others:
            other.set_up(test_path)

    def clean_up(self):
        self.enviroment_setter.clean_up()
        for other in self.clean_up:
            other.clean_up()

    def combine(self, other):
        self.others.append(other)
        return self

    def query_attr(self, attr, default):
        """ check if attr is set on this object or others """
        if hasattr(self, attr):
            return getattr(self, attr)
        if hasattr(self.others[0], attr):
            return getattr(self.others[0], attr)
        # TODO implement
        return default

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
        if self.primary:
            return self.primary.local_path

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

    def set_up(self, test_path):
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
        self.path_ = Path(test_path / self.local_path) / self.root.case
        print(solver_str, self.controlDict)
        print(solver_str, self.controlDict)
        sf.sed(self.fvSolution, "p{}", solver_str)


class CG(SolverSetter):
    def __init__(self, namespace, prefix, field, suffix=None):
        name = "CG"
        if suffix:
            name += suffix
        super().__init__(
            namespace=namespace, prefix=prefix, solver=name, field=field, child=self
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

    def set_up(self, _):
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

    def set_up_cache(self, path):
        print("setup cache", path)
        cache_case = OpenFOAMCase()
        cache_case.set_parent_path(Path(path))
        cache_case.path_ = path
        deltaT = 0.1 * 16 / self.cells
        new_cells = "{} {} {}".format(self.cells, self.cells, self.cells)
        sf.set_cells(cache_case.blockMeshDict, "16 16 16", new_cells)
        sf.set_mesh_boundary_type_to_wall(cache_case.blockMeshDict)
        sf.set_p_init_value(cache_case.init_p)
        sf.set_U_init_value(cache_case.init_U)
        sf.add_libOGL_so(cache_case.controlDict)
        sf.set_end_time(cache_case.controlDict, 10 * deltaT)
        sf.set_deltaT(cache_case.controlDict, deltaT)
        sf.set_writeInterval(cache_case.controlDict)
        sf.clear_solver_settings(cache_case.fvSolution)
        print("Meshing", cache_case.path)
        check_output(["blockMesh"], cwd=cache_case.path)

    def set_up(self, test_path):
        cache_path = test_path / self.cache_path(str(self.cells), self.case_name)
        target_path = test_path / self.local_path
        sf.ensure_path(cache_path.parent)
        if not os.path.exists(cache_path):
            print("cache does not exist")
            check_output(["cp", "-r", self.root, cache_path])
            self.set_up_cache(cache_path)

        # check if cache_path exists otherwise copy
        print("copying from", cache_path, " to ", target_path)
        sf.ensure_path(target_path.parent)
        check_output(["cp", "-r", cache_path, target_path.parent])

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
        self.executor = gko_executor
        super().__init__(
            namespace="GKO", prefix="GKO", field=field, suffix=gko_executor.name
        )


def combine(setters):
    """ combines a tuple of setters """
    primary = deepcopy(setters[0])
    primary.others.append(setters[1])
    # TODO find a better way to propagate the root case
    # cases need a way to check if they have a primary case
    if hasattr(primary, "root"):
        primary.others[0].root = primary.root
    primary.others[0].primary = primary
    return primary


class CaseRunner:
    def __init__(self, solver, base_path, results_aggregator, arguments):
        self.base_path = base_path
        self.results = results_aggregator
        self.arguments = arguments
        self.solver = solver
        self.time_runs = int(arguments["--time_runs"])
        self.min_runs = int(arguments["--min_runs"])

    def run(self, case):
        import datetime

        for processes in [1]:
            print("start runs", processes)

            # self.executor.prepare_enviroment(processes)

            self.results.set_case(
                domain=case.query_attr("domain", ""),
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
                    ret = check_output(
                        [self.solver], cwd=self.base_path / case.path, timeout=15 * 60
                    )
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


def build_with_executors(arguments):

    solvers = []

    if arguments["--ir"]:
        pass

    if arguments["--cg"]:
        pass

    if arguments["--bicgstab"]:
        pass

    if arguments["--smooth"]:
        pass

    return solvers


class ParameterStudy:
    """A class to create a range of cases and potentially run them

    Here parameter studies are created the following way. First,
    a set of cases is defined via
    """

    def __init__(self, test_path, results_aggregator, setters, runner):
        self.test_path = test_path
        self.results_aggregator = results_aggregator
        self.setters = setters
        self.runner = runner

    def build_parameter_study(
        self,
    ):  # test_path, results, executor, setter, arguments):
        cases = product(*self.setters)
        cases_combined = map(combine, cases)
        for case in cases_combined:
            case.set_up(self.test_path)
            # check if solver supported by executor
            # path = test_path / e.local_path / str(n.value)
            # exist = os.path.isdir(path)
            skip = False
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

            #     n.run(case)
            self.runner.run(case)
            # .run(
            #     results,
            #     int(arguments["--min_runs"]),
            #     int(arguments["--run_time"]),
            # )
            # else:
            #     print("skipping")

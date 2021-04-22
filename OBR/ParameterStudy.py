#!/usr/bin/env python3
from OBR.EnviromentSetters import DefaultPrepareEnviroment
import os
from itertools import product
from pathlib import Path
from subprocess import check_output
from copy import deepcopy
from OBR.Setter import Setter
from OBR.MatrixSolver import SolverSetter
from OBR.EnviromentSetters import CellsPrepare

from . import setFunctions as sf


class CellSetter(Setter):
    def __init__(self, base_path, cells, case_name):
        self.cells = cells
        super().__init__(
            base_path=base_path,
            variation_name="{}".format(cells),
            case_name=case_name,
        )
        super().set_enviroment_setter(CellsPrepare(self.path))

    @property
    def cache_path(self):
        return self.enviroment_setter.base_path(str(self.cells)) / self.root.case


class OF:

    name = "OF"
    executor_support = False
    executor = None

    def __init__(self, prefix="P"):
        self.prefix = prefix


class GKOExecutor:
    def __init__(self, name):
        self.name = name


class RefExecutor(GKOExecutor):
    def __init__(self):
        super().__init__(name="Reference")


class OMPExecutor(GKOExecutor):
    def __init__(self):
        super().__init__(name="omp")


class CUDAExecutor(GKOExecutor):
    def __init__(self):
        super().__init__(name="cuda")


class GKO:

    name = "GKO"
    prefix = "GKO"
    executor_support = True
    executor = None

    def __init__(self):
        pass


class CG(SolverSetter):
    def __init__(
        self,
        base_path,
        field,
        case_name,
    ):
        name = "CG"
        super().__init__(
            base_path=base_path,
            solver=name,
            field=field,
            case_name=case_name,
        )
        self.avail_domain_handler = {"OF": OF(), "GKO": GKO()}


def construct(
    base_path, case_name, field, solver, domain, executor=None, preconditioner=None
):
    """
    construct case variant from string arguments

    usage:
       solver = construct("CG", "GKO", "OMP")
    """
    executor_inst = None
    if executor == "Ref":
        executor_inst = RefExecutor()
    if executor == "OMP":
        executor_inst = OMPExecutor()
    if executor == "CUDA":
        executor_inst = CUDAExecutor()

    if solver == "CG":
        cg = CG(base_path, field, case_name)
        try:
            # try to set domain this fails if the domain is not in the map
            # of domains which implement the given solver
            cg.set_domain(domain)
            cg.set_executor(executor_inst)
            return True, cg
        except Exception as e:
            print(e)
            return False, None


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


def combine(setters):
    """ combines a tuple of setters """
    primary = deepcopy(setters[0])
    primary.others.append(setters[1])
    if hasattr(primary, "root"):
        primary.others[0].root = primary.root
    primary.others[0].primary = primary
    return primary


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

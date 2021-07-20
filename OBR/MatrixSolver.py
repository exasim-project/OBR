#!/usr/bin/env python3

from OBR.Setter import Setter
from OBR.EnviromentSetters import PrepareOMPMaxThreads
from pathlib import Path
import OBR.setFunctions as sf


class SolverSetter(Setter):
    def __init__(
        self,
        base_path,
        solver,
        field,
        case_name,
        solver_stub,
        preconditioner="none",
        tolerance="1e-06",
        min_iters="0",
        max_iters="1000",
        update_sys_matrix="no",
    ):

        super().__init__(
            base_path=base_path,
            variation_name="{}-{}".format("-".join(field), solver),
            case_name=case_name,
        )
        self.solver_stub = solver_stub
        self.solver = solver
        self.preconditioner = preconditioner
        self.update_sys_matrix = update_sys_matrix
        self.tolerance = tolerance
        self.min_iters = min_iters
        self.max_iters = max_iters
        self.fields = field

    def set_domain(self, domain):
        self.domain = self.avail_domain_handler[domain]["domain"]
        self.add_property(self.domain.name)
        return self

    def set_preconditioner(self, domain, preconditioner):
        avail_precond = self.avail_domain_handler[domain]["preconditioner"]
        self.preconditioner = avail_precond[preconditioner]

        self.add_property(self.preconditioner.name)
        return self

    def set_executor(self, executor):
        self.domain.executor = executor
        self.add_property(executor.name)
        if hasattr(executor, "enviroment_setter"):
            self.set_enviroment_setter(executor.enviroment_setter)

    @property
    def get_solver(self):
        ret = []
        for field in self.fields:
            solver = self.solver
            if field == "U" and solver == "CG":
                solver = "BiCGStab"
            ret.append(solver)

        return ret

    def set_up(self):
        for field in self.fields:
            if hasattr(self, "enviroment_setter"):
                print("has an enviroment setter")
                self.enviroment_setter.set_up()
            solver = self.solver
            if field == "U" and solver == "CG":
                solver = "BiCGStab"

            matrix_solver = self.prefix + solver
            raw_solver_str = "".join(self.solver_stub[field])
            solver_str = raw_solver_str.format(
                solver=matrix_solver,
                tolerance=self.tolerance,
                preconditioner=self.preconditioner.name,
                minIter=self.min_iters,
                maxIter=self.max_iters,
                executor=self.domain.executor.name,
            )
            solver_str = '"' + field + '.*"{ ' + solver_str

            print("writing", solver_str, "to", self.controlDict)
            sf.sed(self.fvSolution, field + "{}", solver_str)


# Executor


class OFExecutor:
    def __init__(self, name):
        self.name = name


class GKOExecutor:
    def __init__(self, name):
        self.name = name


class RefExecutor(GKOExecutor):
    def __init__(self):
        super().__init__(name="reference")


class OMPExecutor(GKOExecutor):
    def __init__(self, max_processes=4):
        super().__init__(name="omp")
        self.enviroment_setter = PrepareOMPMaxThreads(max_processes)


class CUDAExecutor(GKOExecutor):
    def __init__(self):
        super().__init__(name="cuda")


class HIPExecutor(GKOExecutor):
    def __init__(self):
        super().__init__(name="hip")


class MPIExecutor(OFExecutor):
    def __init__(self):
        super().__init__(name="mpi")


# Preconditioner


class BJ:
    name = "BJ"


class DIC:
    name = "DIC"


class DILU:
    name = "DILU"


class FDIC:
    name = "FDIC"


class GAMG:
    name = "GAMG"


class Diag:
    name = "diagonal"


class NoPrecond:
    name = "none"


# Domain handler


class OF:

    name = "OF"
    executor_support = ["MPI", "Ref"]
    executor = None

    def __init__(self, prefix="P"):
        self.prefix = prefix


class GKO:

    name = "GKO"
    prefix = "GKO"
    executor_support = ["OMP", "CUDA", "Ref", "HIP"]
    executor = None

    def __init__(self):
        pass


# Solver


class CG(SolverSetter):
    def __init__(
        self,
        base_path,
        field,
        case_name,
        solver_stub,
    ):
        name = "CG"
        super().__init__(
            base_path=base_path,
            solver=name,
            field=field,
            case_name=case_name,
            solver_stub=solver_stub,
        )
        self.avail_domain_handler = {
            "OF": {
                "domain": OF(),
                "preconditioner": {
                    "DIC": DIC(),
                    "FDIC": FDIC(),
                    "GAMG": GAMG(),
                    "Diag": Diag(),
                    "NoPrecond": NoPrecond(),
                },
            },
            "GKO": {
                "domain": GKO(),
                "preconditioner": {
                    "BJ": BJ(),
                    "NoPrecond": NoPrecond(),
                },
            },
        }


class BiCGStab(SolverSetter):
    def __init__(
        self,
        base_path,
        field,
        case_name,
        solver_stub,
    ):
        name = "BiCGStab"
        super().__init__(
            base_path=base_path,
            solver=name,
            field=field,
            case_name=case_name,
            solver_stub=solver_stub,
        )
        self.avail_domain_handler = {
            "OF": {
                "domain": OF(),
                "preconditioner": {
                    "DIC": DIC(),
                    "FDIC": FDIC(),
                    "GAMG": GAMG(),
                    "Diag": Diag(),
                    "NoPrecond": NoPrecond(),
                },
            },
            "GKO": {
                "domain": GKO(),
                "preconditioner": {
                    "BJ": BJ(),
                    "NoPrecond": NoPrecond(),
                },
            },
        }


class smooth(SolverSetter):
    def __init__(
        self,
        base_path,
        field,
        case_name,
        solver_stub,
    ):
        name = "smooth"
        super().__init__(
            base_path=base_path,
            solver=name,
            field=field,
            case_name=case_name,
            solver_stub=solver_stub,
        )
        self.avail_domain_handler = {
            "OF": {"domain": OF(prefix=""), "preconditioner": []},
        }


class IR(SolverSetter):
    def __init__(
        self,
        base_path,
        field,
        case_name,
        solver_stub,
    ):
        name = "IR"
        super().__init__(
            base_path=base_path,
            solver=name,
            field=field,
            case_name=case_name,
            solver_stub=solver_stub,
        )
        self.avail_domain_handler = {
            "GKO": {
                "domain": GKO(),
                "preconditioner": {
                    "NoPrecond": NoPrecond(),
                },
            }
        }

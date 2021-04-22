#!/usr/bin/env python3

from OBR.Setter import Setter


class SolverSetter(Setter):
    def __init__(
        self,
        base_path,
        solver,
        field,
        case_name,
        preconditioner="none",
        tolerance="1e-06",
        min_iters="0",
        max_iters="1000",
        update_sys_matrix="no",
    ):

        super().__init__(
            base_path=base_path,
            variation_name="{}-{}".format(field, solver),
            case_name=case_name,
        )
        self.solver = solver
        self.preconditioner = preconditioner
        self.update_sys_matrix = update_sys_matrix
        self.tolerance = tolerance
        self.min_iters = min_iters
        self.max_iters = max_iters

    def set_domain(self, domain):
        self.domain = self.avail_domain_handler[domain]
        self.add_property(self.domain.name)
        return self

    def set_executor(self, executor):
        self.domain.executor = executor
        self.add_property(executor.name)

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

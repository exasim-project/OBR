# #!/usr/bin/env python3
# from OBR.EnviromentSetters import DefaultPrepareEnviroment
# from itertools import product
# from pathlib import Path
# from subprocess import check_output
# from copy import deepcopy
# from OBR.Setter import Setter
# from OBR.MatrixSolver import SolverSetter
# from OBR.EnviromentSetters import CellsPrepare, PathPrepare, RefineMeshPrepare

# from . import setFunctions as sf


class Variant:  # At some point this inherits from Setter
    def __init__(self, root_dir):
        self.root_dir = root_dir


class Remesh(Variant):
    def __init__(self, base_path, refinement, case_name, root, fields):
        self.cells = refinement
        self.root = root
        super().__init__(
            base_path=base_path,
            variation_name="{}".format(refinement),
            case_name=case_name,
        )

    def set_mesh_modifier(self, remesh):

        prepare_mesh = remesh
        prepare_mesh.root = self.root.path
        super().set_enviroment_setter(prepare_mesh)

    @property
    def cache_path(self):
        return self.enviroment_setter.base_path(str(self.cells)) / self.root.case


class ReBlockMesh(Variant):
    """ class to set cells and  calls blockMesh  """

    def __init__(
        self,
        base_path,
        cells,
        case_name,
        root,
        fields,
        meshArgs,
        controlDictArgs,
    ):
        super().__init__(
            base_path,
            cells,
            case_name,
            root,
            fields,
        )

        self.set_mesh_modifier(
            CellsPrepare(
                self.path,
                fields,
                meshArgs,
                controlDictArgs,
            )
        )


class RefineMesh(Variant):
    """ class that calls refineMesh several times """

    def __init__(self, root_dir, input_dict, value_dict):
        super().__init__(root_dir)
        self.input_dict = input_dict
        self.value = value_dict
        self.name = str(self.value[0])

        # self.set_mesh_modifier(
        #     RefineMeshPrepare(
        #         self.path,
        #         refinements,
        #         fields,
        #         meshArgs,
        #         controlDictArgs,
        #     )
        # )


class ChangeMatrixSolver(Variant):
    """ class that calls refineMesh several times """

    def __init__(self, root_dir, input_dict, value_dict):
        super().__init__(root_dir)
        self.input_dict = input_dict
        self.value = value_dict
        self.name = str("_".join(self.value))


# class PathSetter(Variant):
#     def __init__(self, base_path, path, case_name, root, fields):
#         super().__init__(
#             base_path=base_path,
#             variation_name="{}".format(path),
#             case_name=case_name,
#         )
#         prepare_mesh = PathPrepare(self.path, fields)
#         prepare_mesh.root = root.path
#         super().set_enviroment_setter(prepare_mesh)

#     @property
#     def cache_path(self):
#         return self.enviroment_setter.base_path(str(self.cells)) / self.root.case


def construct(
    base_path,
    case_name,
    field,
    solver_stubs,
    extra_args,
    solver,
    domain,
    executor,
    preconditioner,
):
    """
    construct case variant from string arguments

    usage:
       solver = construct("CG", "GKO", "OMP")
    """
    from OBR.MatrixSolver import (
        CUDAExecutor,
        RefExecutor,
        OMPExecutor,
        HIPExecutor,
        MPIExecutor,
    )
    import OBR.MatrixSolver as ms

    executor_inst = None
    if executor == "Ref":
        executor_inst = RefExecutor()
    if executor == "OMP":
        executor_inst = OMPExecutor(**extra_args[executor])
    if executor == "CUDA":
        executor_inst = CUDAExecutor()
    if executor == "HIP":
        executor_inst = HIPExecutor()
    if executor == "MPI":
        executor_inst = MPIExecutor()

    solver_setter = getattr(ms, solver)(base_path, field, case_name, solver_stubs)
    try:
        # try to set domain this fails if the domain is not in the map
        # of domains which implement the given solver
        solver_setter.set_domain(domain)
        # try to set preconditioner this fails if the preconditioner is not in the map
        # of preconditioners domains which implement the given solver
        solver_setter.set_preconditioner(domain, preconditioner)
        if executor not in solver_setter.domain.executor_support:
            0 / 0
        solver_setter.set_executor(executor_inst)
        return True, solver_setter
    except Exception as e:
        return False, None

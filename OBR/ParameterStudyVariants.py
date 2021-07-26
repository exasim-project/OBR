# #!/usr/bin/env python3
from OBR.OpenFOAMCase import OpenFOAMCase
from subprocess import check_output
from . import MatrixSolver as ms
from . import EnviromentSetters as es
from .OpenFOAMCase import OpenFOAMCase


class Variant(OpenFOAMCase):  # At some point this inherits from Setter
    def __init__(self, root_dir, name):
        self.name = name
        super().__init__(root_dir / self.name / "base")


class MeshVariant(Variant):
    def __init__(self, root_dir, name, cell_ratio, controlDictArgs):
        super().__init__(root_dir, name)
        self.prepare_controlDict = es.PrepareControlDict(
            self, cell_ratio, controlDictArgs
        )


class LinearSolverVariant(Variant):
    def __init__(self, root_dir, name):
        super().__init__(root_dir, name)


class RefineMesh(MeshVariant):
    """ class that calls refineMesh several times """

    def __init__(self, root_dir, input_dict, value_dict):
        self.value = value_dict[0]
        name = str(self.value)
        cell_ratio = 4 ** self.value
        print(input_dict)
        super().__init__(root_dir, name, cell_ratio, input_dict["controlDict"])

    def set_up(self):
        self.prepare_controlDict.set_up()
        for _ in range(self.value):
            check_output(["refineMesh", "-overwrite"], cwd=self.path)


class Remesh(MeshVariant):
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


class ReBlockMesh(MeshVariant):
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


# class PathSetter(MeshVariant):
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


class ChangeMatrixSolver(Variant):
    """ class that calls refineMesh several times """

    def __init__(self, root_dir, input_dict, value_dict):
        print(input_dict, value_dict)
        self.value = value_dict
        name = str("_".join(self.value))
        super().__init__(root_dir, name)
        self.input_dict = input_dict
        self.solver_setter = getattr(ms, value_dict[0])(
            self.path, input_dict["fields"], input_dict["defaults"]
        )
        self.solver_setter.preconditioner = getattr(ms, value_dict[1])()
        self.solver_setter.executor = getattr(ms, value_dict[2])()

    def set_up(self):
        self.solver_setter.set_up()


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

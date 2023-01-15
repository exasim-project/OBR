# #!/usr/bin/env python3
from OpenFOAMCase import OpenFOAMCase
import subprocess
import sys
from subprocess import check_output
import multiprocessing
import MatrixSolver as ms
import EnviromentSetters as es
import setFunctions as sf

from pathlib import Path


class Variant(OpenFOAMCase):
    """A Variant is an OpenFOAM case which is derived from a base case

    Child classes implement concrete operations
    """

    def __init__(self, job, base_job):
        super().__init__(Path(job.path) / "case")
        self.base_job = OpenFOAMCase(Path(base_job) / "case")
        self.link_mesh = True
        self.map_fields = False


class MeshVariant(Variant):
    def __init__(self, job, base_job, cell_ratio, controlDictArgs):
        super().__init__(job, base_job)
        # TODO use a member function of OpenFOAMCase class here
        self.prepare_controlDict = es.PrepareControlDict(
            self, cell_ratio, controlDictArgs
        )
        self.link_mesh = False
        self.map_fields = True


class ExistingCaseVariants(Variant):
    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict[0][1]
        name = str(self.value)
        self.build = input_dict.get("build", False)
        self.prepare_controlDict = es.PrepareControlDict(
            self, 1, input_dict["controlDict"]
        )
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.track_args["case_parameter"]["resolution"] = self.value
        self.link_mesh = False
        self.map_fields = False
        self.base = "../../../base/" + value_dict[0][0]
        print("base", self.base)
        print("value", self.value)

    def set_up(self):
        self.prepare_controlDict.set_up()

        # execute build command
        print("track args", self.track_args)
        if self.build:
            for step in self.build:
                try:
                    print(step.split(" "))
                    print(check_output(step.split(" "), cwd=self.path))
                except:
                    print(step, "failed")
                    pass


class ChangeMatrixSolver(Variant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict
        self.solver = value_dict[0]
        self.preconditioner = value_dict[1]
        self.root_dir = root_dir
        self.track_args_init = track_args

        self.executors = input_dict["variants"]["backend"][value_dict[2]]
        self.backend_name = value_dict[2]
        self.executor = None

        self.input_dict = input_dict
        self.fields = input_dict["fields"][0]
        self.defaults = input_dict.get("properties")[self.fields]
        # eg CG, BiCGStab
        print(value_dict, input_dict["variants"])

    @property
    def valid(self):
        self.name = "{}_{}_{}_{}".format(
            self.solver, self.preconditioner, self.backend_name, self.executor
        )
        super().__init__(
            self.root_dir,
            self.name,
            self.track_args_init,
            variant_of=self.input_dict.get("variant_of", False),
        )
        backend = getattr(ms, self.backend_name)(
            solver=self.solver,
            preconditioner=self.preconditioner,
            executor=self.executor,
            options=self.defaults,
        )

        self.setter = ms.SolverSetter(backend, self.path, self.fields, self.defaults)

        # check whether preconditioner and executor combinations are
        # supported/valid
        self.is_valid = backend.is_valid()
        # eg, GKO, DefaultOF, PETSC
        self.track_args["case_parameter"]["solver_" + self.fields] = self.solver
        self.track_args["case_parameter"][
            "preconditioner_" + self.fields
        ] = self.preconditioner
        self.track_args["case_parameter"]["backend_" + self.fields] = self.backend_name
        self.track_args["case_parameter"]["executor_" + self.fields] = self.executor
        return self.is_valid

    def set_up(self):
        print("[OBR] change linear solver", self.path)
        self.setter.set_up()


# TODO this is a lot of duplicated boilerplate
class ChangeMatrixSolverProperties(Variant):
    """class that calls refineMesh several times"""

    def __init__(self, root_dir, input_dict, value_dict, track_args):
        self.value = value_dict
        name = str(self.value[0])
        super().__init__(
            root_dir,
            name,
            track_args,
            variant_of=input_dict.get("variant_of", False),
        )
        self.input_dict = input_dict
        self.field = input_dict["field"][0]
        self.exclude = input_dict.get("exclude", ["Final"])
        self.track_args["case_parameter"][input_dict["name"]] = self.value[0]

    def set_up(self):
        print(
            "[OBR] add or set linear solver settings",
            self.path,
            self.field,
            self.value[0],
        )
        sf.add_or_set_solver_settings(
            self.fvSolution, self.field, self.input_dict, self.value[0], self.exclude
        )

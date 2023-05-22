#!/usr/bin/env python3

import errno
import os
from pathlib import Path
from subprocess import check_output

from ..core.core import (
    logged_execute,
    logged_func,
    modifies_file,
)

from .BlockMesh import BlockMesh, calculate_simple_partition

from Owls.parser.FoamDict import FileParser


class File(FileParser):
    def __init__(self, **kwargs):
        # forwards all unused arguments
        self._file = kwargs["file"]
        self._folder = kwargs["folder"]
        kwargs["path"] = Path(self._folder) / self._file
        super().__init__(**kwargs)
        self.job = kwargs["job"]
        self._optional = kwargs.get("optional", False)
        self._md5sum = None

    def get(self, name: str):
        """Get a value from an OpenFOAM dictionary file"""
        # TODO replace with a safer option
        # also consider moving that to Owls
        try:
            return eval(super().get(name))
        except:
            return super().get(name)

    def md5sum(self, refresh=False) -> str:
        """Compute a files md5sum"""
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        if not self._md5sum or refresh:
            self._md5sum = check_output(["md5sum", str(self.path)], text=True)
        return self._md5sum

    # @decorator_modifies_file
    def set(self, args: dict):
        """modifies the current controlDict by the given dictionary

        if the key exists in the controlDict the values are replaced
        non-existent keys are added
        """
        args_copy = {k: v for k, v in args.items()}

        modifies_file(self.path)
        if self.job:
            logged_func(
                self.set_key_value_pairs,
                # FIXME add job.doc reference
                self.job.doc,
                dictionary=args_copy,
            )
        else:
            self.set_key_value_pairs(args_copy)

        self.update()
        self.md5sum(refresh=True)


class OpenFOAMCase(BlockMesh):
    """A class for simple access to typical OpenFOAM files"""

    def __init__(self, path, job):
        self.path_ = Path(path)
        self.job = job
        self.controlDict = File(folder=self.system_folder, file="controlDict", job=job)
        self.fvSolution = File(folder=self.system_folder, file="fvSolution", job=job)
        # FIXME fvSchemes does not exist when using this class in post hooks?
        if Path(self.system_folder / "fvSchemes").exists():
            self.fvSchemes = File(folder=self.system_folder, file="fvSchemes", job=job)
        # decomposeParDict might not exist in some test cases
        if Path(self.system_folder / "decomposeParDict").exists():
            self.decomposeParDict = File(
                folder=self.system_folder, file="decomposeParDict", job=job, optional=True
            )
        self.file_dict: dict[str, File] = dict()
        self.config_file_tree

    @property
    def path(self):
        return self.path_

    @property
    def system_folder(self):
        return self.path / "system"

    @property
    def constant_folder(self):
        return self.path / "constant"

    @property
    def zero_folder(self):
        """TODO check for 0.orig folder"""
        return self.path / "0"

    @property
    def init_p(self):
        return self.zero_folder / "p"

    @property
    def init_U(self):
        return self.zero_folder / "U.orig"

    @property
    def is_decomposed(self):
        proc_zero = self.path / "processor0"
        if not proc_zero.exists():
            return False
        return True

    @property
    def processor_folder(self) -> list[Path]:
        if not self.is_decomposed:
            return []
        _, folds, files = next(os.walk(self.path))
        proc_folds = [self.path / f for f in folds if "processor" in f]
        return proc_folds

    def _exec_operation(self, operation):
        logged_execute(operation, self.path, self.job.doc)

    def decomposePar(self, args={}):
        """Sets decomposeParDict and calls decomposePar"""
        method = args["method"]
        if method == "simple":
            if not args.get("numberOfSubDomains"):
                coeffs = [int(i) for i in args["coeffs"]]
                numberSubDomains = coeffs[0] * coeffs[1] * coeffs[2]
            else:
                numberSubDomains = int(args["numberOfSubDomains"])
                coeffs = args.get("coeffs", None)
                if not coeffs:
                    coeffs = calculate_simple_partition(numberSubDomains, [1, 1, 1])

            self.decomposeParDict.set(
                {
                    "method": method,
                    "numberOfSubdomains": numberSubDomains,
                    "coeffs": {"n": coeffs},
                }
            )
        else:
            numberSubDomains = int(args["numberOfSubDomains"])
            self.decomposeParDict.set(
                {
                    "method": method,
                    "numberOfSubdomains": numberSubDomains,
                }
            )

        self._exec_operation(["decomposePar", "-force"])
        fvSolutionArgs = args.get("fvSolution", {})
        if fvSolutionArgs:
            self.fvSolution.set(fvSolutionArgs)

    def setKeyValuePair(self, args: dict):
        path = Path(args.pop("file"))
        file_handle = File(
            folder=self.path_ / path.parents[0], file=path.parts[-1], job=self.job
        )
        file_handle.set_key_value_pairs(args)

    def run(self, args: dict):
        solver = self.controlDict.get("application")
        self._exec_operation([solver])

#!/usr/bin/env python3

import setFunctions as sf
import errno
import os
from copy import deepcopy
from pathlib import Path

from core import (
    logged_execute,
    logged_func,
    modifies_file,
)

from .BlockMesh import BlockMesh

from Owls.FoamDictParser import FileParser


class File(FileParser):
    def __init__(self, **kwargs):
        # forwards all unused arguments
        super().__init__(**kwargs)
        self._file = kwargs["file"]
        self._folder = kwargs["folder"]
        self.job = kwargs["job"]
        self._parse_file()
        self._optional = kwargs.get("optional", False)

    def _parse_file(self):
        if self.path.exists():
            self._parsed_file = self.parse_file_to_dict()
        else:
            self._parsed_file = {}

    @property
    def path(self):
        return self._folder / self._file

    def get(self, name: str):
        # TODO replace with a safer option
        # also consider moving that to Owls
        if self.path.exists():
            try:
                return eval(self._parsed_file.get(name))
            except:
                return self._parsed_file.get(name)
        else:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), self.path)

    # @decorator_modifies_file
    def set(self, args: dict):
        """modifies the current controlDict by the given dictionary

        if the key exists in the controlDict the values are replaced
        non-existent keys are added
        """
        modifies_file(self.path)
        if self.job:
            logged_func(
                self.set_key_value_pairs,
                # FIXME add job.doc reference
                self.job.doc,
                dictionary=args,
            )
        else:
            self.set_key_value_pairs(args)

        self._parsed_file = self.parse_file_to_dict()


class OpenFOAMCase(BlockMesh):
    """A class for simple access to typical OpenFOAM files"""

    def __init__(self, path, job):
        self.path_ = Path(path)
        self.job = job
        self.controlDict = File(folder=self.system_folder, file="controlDict", job=job)
        self.fvSolution = File(folder=self.system_folder, file="fvSolution", job=job)
        self.fvSchemes = File(folder=self.system_folder, file="fvSchemes", job=job)
        self.decomposeParDict = File(
            folder=self.system_folder, file="decomposeParDict", job=job, optional=True
        )

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

    def _exec_operation(self, operation):
        logged_execute(operation, self.path, self.job.doc)

    def decomposePar(self, args={}):
        """Sets decomposeParDict and calls decomposePar"""
        method = args["method"]
        if method == "simple":
            if not args.get("numberSubDomains"):
                coeffs = [int(i) for i in args["coeffs"]]
                numberSubDomains = coeffs[0] * coeffs[1] * coeffs[2]
            else:
                numberSubDomains = int(args["numberSubDomains"])
                coeffs = args.get("coeffs", None)
                if not coeffs:
                    coeffs = sf.calculate_simple_partition(numberSubDomains, [1, 1, 1])

            self.decomposeParDict.set(
                {
                    "method": method,
                    "numberOfSubdomains": numberSubDomains,
                    "coeffs": {"n": coeffs},
                }
            )
        self._exec_operation(["decomposePar", "-force"])
        fvSolutionArgs = args.get("fvSolution", False)
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

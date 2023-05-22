#!/usr/bin/env python3

import errno
from typing import Union, Generator, Tuple, Any
import os
from pathlib import Path
from subprocess import check_output
import re
from ..core.core import logged_execute, logged_func, modifies_file, path_to_key

from .BlockMesh import BlockMesh, calculate_simple_partition

from Owls.parser.FoamDict import FileParser

OF_HEADER_REGEX = r"""(/\*--------------------------------\*- C\+\+ -\*----------------------------------\*\\
(\||)\s*=========                 \|(\s*\||)
(\||)\s*\\\\      /  F ield         \| (OpenFOAM:|foam-extend:)\s*[\d\w\W]*\s*(\||)
(\||)\s*\\\\    /   O peration     \| (Version:|Website:)\s*[\d\w\W]*\s*(\||)
(\||)\s*\\\\  /    A nd           \| (Web:|Version:|Website)\s*[\d\w\W]*\s*(\||)
(\||)\s*\\\\/     M anipulation  \|(\s*\||)
\\\*---------------------------------------------------------------------------\*/)"""


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

    def is_modified(self) -> bool:
        if not self._md5sum:
            return False
        current_md5sum = check_output(["md5sum", str(self.path)], text=True)
        return self._md5sum != current_md5sum

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
    def const_polyMesh_folder(self):
        cpf = self.constant_folder / "polyMesh"
        if cpf.exists():
            return cpf
        return None

    @property
    def system_include_folder(self):
        cpf = self.system_folder / "include"
        if cpf.exists():
            return cpf
        return None

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

    def config_files_in_folder(
        self, folder: Path
    ) -> Generator[Tuple[File, str], Any, None]:
        """Yields all OF config files  in given folder"""
        if not folder:
            # const_polymesh and system_include can be None
            return
        if folder.is_dir():
            for f_path in folder.iterdir():
                if f_path.is_file() and not f_path.is_symlink():
                    if self.has_openfoam_header(f_path):
                        rel_path = str(f_path.relative_to(self.path))
                        file_obj = File(folder=folder, file=f_path.name, job=self.job)
                        yield file_obj, rel_path

    @property
    def config_file_tree(self) -> list[str]:
        """Iterates through case file tree and returns a list of paths to non-symlinked files.
        """
        for file, rel_path in self.config_files_in_folder(self.system_folder):
            self.file_dict[rel_path] = file
        for file, rel_path in self.config_files_in_folder(self.constant_folder):
            self.file_dict[rel_path] = file
        for file, rel_path in self.config_files_in_folder(self.system_include_folder):
            self.file_dict[rel_path] = file
        for file, rel_path in self.config_files_in_folder(self.const_polyMesh_folder):
            self.file_dict[rel_path] = file
        return list(self.file_dict.keys())

    def get(self, key: str) -> Union[File, None]:
        return self.file_dict.get(key, None)

    def has_openfoam_header(self, path: Path) -> bool:
        with path.open() as f:
            try:
                header = "".join(f.readlines()[:7])
                return re.match(OF_HEADER_REGEX, header) is not None
            except UnicodeDecodeError:
                return False

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

    def is_file_modified(self, path: str) -> bool:
        """
        checks if a file has been modified by comparing the current md5sum with the previously saved one inside `self.job.dict`
        """
        if "md5sum" not in self.job.doc["obr"]:
            return False  # no md5sum has been calculated for this file
        current_md5sum, last_modified = self.job.doc["obr"]["md5sum"].get(path)
        if os.path.getmtime(path) == last_modified:
            # if modification dates dont differ, the md5sums wont, either
            return False
        md5sum = check_output(["md5sum", path], text=True)
        return current_md5sum != md5sum

    def is_tree_modified(self) -> list[str]:
        """
        iterates all files inside the case tree and returns a list of files that were modified, based on their md5sum.
        """
        m_files = []
        for file in self.config_file_tree:
            if self.is_file_modified(file):
                m_files.append(file)
        return m_files

    def perform_post_md5sum_calculations(self):
        """
        calculates md5sums for all case files. Primarily called from `dispatch_post_hooks`
        """
        for case_path in self.config_file_tree:
            case_file = Path(self.job.path) / "case" / case_path
            md5sum = check_output(["md5sum", case_file], text=True)
            if "md5sum" not in self.job.doc["obr"]:
                self.job.doc["obr"]["md5sum"] = dict()
            signac_friendly_path = path_to_key(
                str(case_path)
            )  # signac does not allow . inside paths or job.doc keys
            last_modified = os.path.getmtime(case_file)
            self.job.doc["obr"]["md5sum"][signac_friendly_path] = (md5sum.split()[0], last_modified)

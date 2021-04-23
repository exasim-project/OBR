#!/usr/bin/env python3

from pathlib import Path


class OpenFOAMCase:
    """ A class for simple access to typical OpenFOAM files"""

    def __init__(self, path):
        self.path_ = path

    @property
    def path(self):
        print("path ", self.path_)
        return self.path_

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

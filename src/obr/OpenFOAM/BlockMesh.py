#!/usr/bin/env python3

from ..core.core import modifies_file
from typing import TYPE_CHECKING, Any, Optional
from subprocess import check_output
import sys
from pathlib import Path
import shutil


if TYPE_CHECKING:

    class OpenFOAMCase:
        constant_folder: Any
        controlDict: Any
        path: Any
        time_folder: Any
        system_folder: Any
        _exec_operation: Any

    _Base = OpenFOAMCase
else:
    _Base = object


def calculate_simple_partition(nSubDomains, decomp):
    """Calculates a simple domain decomposition based on nSubDomains

    Returns
    -------
        number of subdomains

    """

    domains = lambda x: x[0] * x[1] * x[2]
    remainder = lambda x: nSubDomains - domains(x)

    def next_position(x):
        if x[0] == x[1]:
            return 0
        if x[1] == x[2]:
            return 1
        return 2

    def isPrime(n):
        for i in range(2, n):
            if n % i == 0:
                return False, i  # i at this iteration is equal to the smallest factor
        return True, n

    i = next_position(decomp)
    is_prime, factor = isPrime(nSubDomains)

    if is_prime:
        decomp[i] *= factor
        return decomp
    if nSubDomains > 0:
        decomp[i] *= factor
        return calculate_simple_partition(int(nSubDomains / factor), decomp)
    else:
        return decomp


def sed(fn, in_reg_exp, out_reg_exp, inline=True):
    """wrapper around sed"""
    if sys.platform == "darwin":
        ret = check_output(
            ["sed", "-i", "", "s/" + in_reg_exp + "/" + out_reg_exp + "/g", fn]
        )
    else:
        ret = check_output(
            ["sed", "-i", "s/" + in_reg_exp + "/" + out_reg_exp + "/g", fn]
        )


def set_cells(blockMeshDict, old_cells, new_cells):
    """ """
    sed(blockMeshDict, old_cells, new_cells)


# TODO use FileParse as a base for modifying the blockMeshDict
class BlockMesh(_Base):
    """A mixin class to add block mesh functionalities and wrapper"""

    def __init__(self, **kwargs):
        # forwards all unused arguments
        super().__init__(**kwargs)

    @property
    def blockMeshDict(self) -> Optional[Path]:
        sys_block_mesh = self.system_folder / "blockMeshDict"
        if sys_block_mesh.exists():
            return sys_block_mesh
        const_block_mesh = self.constant_folder / "blockMeshDict"
        if const_block_mesh.exists():
            return const_block_mesh
        return None

    @property
    def polyMesh(self) -> list[Path]:
        return [
            self.constant_folder / "polyMesh" / "points",
            self.constant_folder / "polyMesh" / "boundary",
            self.constant_folder / "polyMesh" / "faces",
            self.constant_folder / "polyMesh" / "owner",
            self.constant_folder / "polyMesh" / "neighbour",
        ]

    def blockMeshDictmd5sum(self) -> Optional[str]:
        fn = self.blockMeshDict
        if not fn:
            return None
        return check_output(["md5sum", str(fn)], text=True)

    def modifyBlockMesh(self, args: dict):
        modifies_file(self.blockMeshDict)
        blocks = args["modifyBlock"]
        if isinstance(blocks, str):
            blocks = [blocks]

        for block in blocks:
            orig_block, target_block = block.split("->")
            set_cells(
                self.blockMeshDict,
                orig_block,
                target_block,
            )

    def blockMesh(self, args: dict = {}):
        # TODO replace this with writes_file and clean polyMesh folder
        modifies_file(self.polyMesh)
        controlDictArgs = args.pop("controlDict", False)
        if controlDictArgs:
            modifies_file(self.controlDict.path)
            self.controlDict.set(controlDictArgs)
        if args.get("modifyBlock"):
            self.modifyBlockMesh(args)
        self._exec_operation(["blockMesh"])

    def checkMesh(self, args: dict = {}):
        # TODO replace this with writes_file and clean polyMesh folder
        args.get("cli_args")
        self._exec_operation(["checkMesh"])

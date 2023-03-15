#!/usr/bin/env python3

import setFunctions as sf
from core import modifies_file
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:

    class OpenFOAMCase:
        constant_folder: Any
        controlDict: Any
        _exec_operation: Any

    _Base = OpenFOAMCase
else:
    _Base = object


# TODO use FileParse as a base for modifying the blockMeshDict
class BlockMesh(_Base):
    """A mixin class to add block mesh functionalities and wrapper"""

    def __init__(self, **kwargs):
        # forwards all unused arguments
        super().__init__(**kwargs)

    @property
    def blockMeshDict(self):
        sys_block_mesh = self.system_folder / "blockMeshDict"
        if sys_block_mesh.exists():
            return sys_block_mesh
        const_block_mesh = self.constant_folder / "blockMeshDict"
        if const_block_mesh.exists():
            return const_block_mesh
        return None

    @property
    def polyMesh(self) -> list:
        return [
            self.constant_folder / "polyMesh" / "points",
            self.constant_folder / "polyMesh" / "boundary",
            self.constant_folder / "polyMesh" / "faces",
            self.constant_folder / "polyMesh" / "owner",
            self.constant_folder / "polyMesh" / "neighbour",
        ]

    def refineMesh(self, args: dict):
        """ """
        modifies_file(self.polyMesh)
        if args.get("adapt_timestep", True):
            modifies_file(self.controlDict.path)
            deltaT = float(self.controlDict.get("deltaT"))
            self.controlDict.set({"deltaT": deltaT / 2.0})
        self._exec_operation(["refineMesh", "-overwrite"])

    def modifyBlockMesh(self, args: dict):
        modifies_file(self.blockMeshDict)
        blocks = args["modifyBlock"]
        if isinstance(blocks, str):
            blocks = [blocks]

        for block in blocks:
            orig_block, target_block = block.split("->")
            sf.set_cells(
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

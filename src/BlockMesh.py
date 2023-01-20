#!/usr/bin/env python3

import setFunctions as sf
from core import modifies_file, writes_files


class BlockMesh:
    """A mixin class to add block mesh functionalities and wrapper"""

    def __init__(self, **kwargs):
        # forwards all unused arguments
        super().__init__(**kwargs)

    @property
    def blockMeshDict(self):
        # TODO also check in constant folder
        return self.system_folder / "blockMeshDict"

    @property
    def polyMesh(self):
        return [
            self.constant_folder / "polyMesh" / "points",
            self.constant_folder / "polyMesh" / "boundary",
            self.constant_folder / "polyMesh" / "faces",
            self.constant_folder / "polyMesh" / "owner",
            self.constant_folder / "polyMesh" / "neighbour",
        ]

    # @decorator_writes_files(["polyMesh"])
    def refineMesh(self, args):
        """ """
        modifies_file(self.polyMesh)
        if args.get("adapt_timestep", True):
            deltaT = self.deltaT
            self.setControlDict({"deltaT": deltaT / 2})

    # @decorator_modifies_file(["blockMeshDict"])
    def modifyBlockMesh(self, args):
        modifies_file(self.blockMeshDict)
        for block in args["modifyBlock"]:
            orig_block, target_block = block.split("->")
            sf.set_cells(
                self.blockMeshDict,
                orig_block,
                target_block,
            )

        self._exec_operation(["refineMesh", "-overwrite"])

    # @decorator_writes_files(["polyMesh"])
    def blockMesh(self, args={}):
        modifies_file(self.polyMesh)
        if args.get("modifyBlock"):
            self.modifyBlockMesh(args)
        self._exec_operation("blockMesh")

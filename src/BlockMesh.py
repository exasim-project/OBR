#!/usr/bin/env python3

import setFunctions as sf
from core import modifies_file


# TODO use FileParse as a base for modifying the blockMeshDict
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

    def refineMesh(self, args):
        """ """
        modifies_file(self.polyMesh)
        if args.get("adapt_timestep", True):
            deltaT = self.deltaT
            self.setControlDict({"deltaT": deltaT / 2})

    def modifyBlockMesh(self, args):
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

        self._exec_operation(["blockMesh"])

    def blockMesh(self, args={}):
        # TODO replace this with writes_file and clean polyMesh folder
        modifies_file(self.polyMesh)
        controlDictArgs = args.pop("controlDict", False)
        if controlDictArgs:
            modifies_file(self.controlDict.path)
            self.controlDict.set(controlDictArgs)
        if args.get("modifyBlock"):
            self.modifyBlockMesh(args)
        self._exec_operation(["blockMesh"])

    def checkMesh(self, args={}):
        # TODO replace this with writes_file and clean polyMesh folder
        args.get("cli_args")
        self._exec_operation(["checkMesh"])

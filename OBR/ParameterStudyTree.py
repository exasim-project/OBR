#!/usr/bin/env python3
from . import ParameterStudyVariants as variants
from . import setFunctions as sf
from .OpenFOAMCase import OpenFOAMCase
from pathlib import Path
from itertools import product
from subprocess import check_output
from copy import deepcopy
import json


class ParameterStudyTree:
    """ class to construct the file system tree of the cases """

    def __init__(
        self, root_dir, root_dict, input_dict, track_args, parent=None, base=None
    ):
        """parent = the part of the tree above
        base = the base case on which the tree is based
        """
        self.parent = parent
        self.base = base
        self.input_dict = input_dict
        self.root_dir = root_dir
        self.case_dir = root_dir / "base"
        self.variation_dir = root_dir / ("Variation_" + input_dict["name"])
        self.variation_type = input_dict["type"]
        self.root_dict = root_dict

        # go through the top level
        # construct the type of variation
        self.cases = [
            getattr(variants, self.variation_type)(
                self.variation_dir, self.input_dict, variant_dict, deepcopy(track_args)
            )
            for variant_dict in product(*input_dict["variants"].values())
        ]

        self.cases = [case for case in self.cases if case.valid]

        # check for further varations
        self.subvariations = []
        if input_dict.get("variation"):
            sub_variation_dicts = input_dict.get("variation")
            for sub_variation in sub_variation_dicts:
                for case in self.cases:
                    self.subvariations.append(
                        ParameterStudyTree(
                            self.variation_dir / case.name,
                            self.root_dict,
                            sub_variation,
                            case.track_args,
                            parent=self,
                        )
                    )

        # deduplicate files later

    def copy_base_to(self, case):
        # copy or link only if case.path doesn not exist
        if case.path.exists():
            return

        if not case.link_mesh:
            # TODO copy zero if not linked
            dst = self.variation_dir / case.name / "base"
            cmd = ["mkdir", "-p", dst]
            check_output(cmd)

            if not case.map_fields:
                src = Path("../../../base/0")
                cmd = ["cp", "-r", src, "."]
                check_output(cmd, cwd=case.path)

            src = Path("../../../base/constant")
            cmd = ["cp", "-r", src, "constant"]
            check_output(cmd, cwd=case.path)

            src = Path("../../../base/system")
            cmd = ["cp", "-r", src, "."]
            check_output(cmd, cwd=case.path)

        else:
            dst = self.variation_dir / case.name / "base"
            cmd = ["mkdir", "-p", dst]
            check_output(cmd)

            src = Path("../../../base/constant")
            dst = Path("constant")
            cmd = ["ln", "-s", src, dst]
            check_output(cmd, cwd=case.path)

            src = Path("../../../base/system")
            cmd = ["cp", "-r", src, "."]
            check_output(cmd, cwd=case.path)

            src = Path("../../../base/0")
            dst = "0"
            cmd = ["ln", "-s", src, dst]
            check_output(cmd, cwd=case.path)

    def set_up(self):
        """ creates the tree of case variations"""

        sf.ensure_path(self.root_dir)
        sf.ensure_path(self.variation_dir)

        # copy the base case into the tree
        if self.base:
            self.base.copy_to(self.root_dir / "base")

        # if it has a parent case copy the parent case
        # and apply modifiers
        for case in self.cases:
            case_dir = self.variation_dir / case.name
            sf.ensure_path(case_dir)
            self.copy_base_to(case)
            case.set_up()
            if not self.subvariations:
                # TODO
                track_args = case.track_args
                track_args["exec"] = [self.root_dict["case"]["solver"]]
                jsonString = json.dumps(track_args)
                with open(case_dir / "base/obr.json", "w") as jsonFile:
                    jsonFile.write(jsonString)

                print("writing exec script", case_dir / "base")

        # descend one level to the subvariations
        if self.subvariations:
            for subvariation in self.subvariations:
                subvariation.set_up()

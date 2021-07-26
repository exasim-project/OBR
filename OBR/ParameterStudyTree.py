#!/usr/bin/env python3
from . import ParameterStudyVariants as variants
from . import setFunctions as sf
from itertools import product
from subprocess import check_output
import json


class ParameterStudyTree:
    """ class to construct the file system tree of the cases """

    def __init__(self, root_dir, input_dict, parent=None, base=None):
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

        # go through the top level
        # construct the type of variation
        self.cases = [
            getattr(variants, self.variation_type)(
                self.variation_dir, self.input_dict, variant_dict
            )
            for variant_dict in product(*input_dict["variants"].values())
        ]

        self.cases = [case for case in self.cases if case.valid]

        # check for further varations
        self.subvariations = []
        if input_dict.get("variation"):
            for case in self.cases:
                self.subvariations.append(
                    ParameterStudyTree(
                        self.variation_dir / case.name,
                        input_dict["variation"],
                        parent=self,
                    )
                )

        # deduplicate files later

    def copy_base_to(self, dst):
        cmd = ["cp", "-r", self.case_dir, dst]
        check_output(cmd)

    def set_up(self):
        """ creates the tree of case variations"""

        sf.ensure_path(self.root_dir)
        sf.ensure_path(self.variation_dir)

        # copy the base case into the tree
        if self.base:
            self.base.copy_to(self.root_dir / "base")
            # apply controlDict settings
        else:
            self.copy_base_to(self.variation_dir / "base")

        # if it has a parent case copy the parent case
        # and apply modifiers
        for case in self.cases:
            case_dir = self.variation_dir / case.name
            sf.ensure_path(case_dir)
            self.copy_base_to(self.variation_dir / case.name / "base")
            case.set_up()
            if not self.subvariations:
                args = {"exec": ["simpleFoam"]}
                jsonString = json.dumps(args)
                with open(case_dir / "base/obr.json", "w") as jsonFile:
                    jsonFile.write(jsonString)

                print("writing exec script", case_dir / "base")

        # descend one level to the subvariations
        if self.subvariations:
            for subvariation in self.subvariations:
                subvariation.set_up()

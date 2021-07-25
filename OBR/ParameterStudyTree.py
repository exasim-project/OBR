#!/usr/bin/env python3
from . import ParameterStudyVariants as variants
from . import setFunctions as sf
from itertools import product
from subprocess import check_output


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
        print("init", root_dir, input_dict)

        # go through the top level
        # construct the type of variation
        self.cases = [
            getattr(variants, self.variation_type)(
                self.variation_dir, self.input_dict, variant_dict
            )
            for variant_dict in product(*input_dict["variants"].values())
        ]

        # check for further varations
        self.subvariations = []
        if input_dict.get("variation"):
            print("create variation")
            for case in self.cases:
                print("create variation", case)
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
        else:
            print("copy_base_to")
            self.copy_base_to(self.variation_dir / "base")
            # self.copy_base_to(self.root_dir / "base")

        # if it has a parent case copy the parent case
        # and apply modifiers
        for case in self.cases:
            sf.ensure_path(self.variation_dir / case.name)
            self.copy_base_to(self.variation_dir / case.name / "base")

        # descend one level to the subvariations
        if self.subvariations:
            for subvariation in self.subvariations:
                subvariation.set_up()

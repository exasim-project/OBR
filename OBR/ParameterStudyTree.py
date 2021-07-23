#!/usr/bin/env python3
from . import ParameterStudyVariants as variants


class ParameterStudyTree:
    """ class to construct the file system tree of the cases """

    def __init__(self, root_dir, input_dict, parent=None):
        self.input_dict = input_dict
        self.root_dir = root_dir / ("Variation_" + input_dict["name"])
        self.variation_type = input_dict["type"]

        # go through the top level
        # construct the type of variation
        self.cases = [
            getattr(variants, self.variation_type)(
                self.root_dir, self.input_dict, variant_dict
            )
            for variant_dict in input_dict["variants"]
        ]

        # check for further varations
        self.subvariation = False
        if input_dict.get("variation"):
            self.subvariation = ParameterStudyTree(
                self.root_dir, input_dict["variation"], parent=self
            )

        # deduplicate files later

    def set_up():
        # create
        # if it is top level dont copy anything
        pass

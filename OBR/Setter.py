#!/usr/bin/env python3

from OBR.OpenFOAMCase import OpenFOAMCase


class Setter(OpenFOAMCase):
    """base class to set case properties"""

    def __init__(
        self,
        base_path,
        variation_name,
        case_name,
    ):

        super().__init__(path=self.get_full_path(base_path, variation_name, case_name))
        self.base_path = base_path
        self.case_name = variation_name

        self.others = []
        self.name = variation_name

    def get_full_path(self, base_path, variation_name, case_name):
        """ compute full path from different components """
        fp = base_path / variation_name / case_name
        print("fp", fp)
        return fp

    def combine(self, other):
        self.others.append(other)
        print("other", other.case_name)

    def add_property(self, prop_name):
        """ add a new property to the path name and update the base class path """
        self.name += "-" + prop_name

        # update the base OpenFOAM path
        self.path_ = (self.base_path, self.name, self.case_name)

    def set_enviroment_setter(self, enviroment_setter):
        self.enviroment_setter = enviroment_setter
        self.enviroment_setter.path = self.path

    @property
    def prefix(self):
        return self.domain.prefix

    def set_up(self):
        """ delegate the set_up call to enviroment setters """
        self.enviroment_setter.set_up()
        for other in self.others:
            other.set_up()

    def clean_up(self):
        self.enviroment_setter.clean_up()
        for other in self.others:
            other.clean_up()

    def combine(self, other):
        self.others.append(other)
        return self

    def query_attr(self, attr, default):
        """ check if attr is set on this object or others """
        if hasattr(self, attr):
            return getattr(self, attr)
        if hasattr(self.others[0], attr):
            return getattr(self.others[0], attr)
        # TODO implement
        return default

    def __repr__(self):
        return self.name

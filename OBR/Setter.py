#!/usr/bin/env python3

from OBR.OpenFOAMCase import OpenFOAMCase
from pathlib import Path


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
        self.case_name = case_name

        self.others = []
        self.name = variation_name

    def get_full_path(self, base_path, variation_name, case_name):
        """ compute full path from different components """
        fp = base_path / variation_name / case_name
        return fp

    def add_property(self, prop_name):
        """ add a new property to the path name and update the base class path """
        self.name += "-" + prop_name

        # update the base OpenFOAM path
        self.path_ = (self.base_path, self.name, self.case_name)

    def set_enviroment_setter(self, enviroment_setter):
        # TODO support a list of enviroment setters
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

    def get_processes(self):
        if hasattr(self, "processes_"):
            return self.processes
        else:
            try:
                return self.others[0].domain.executor.enviroment_setter.processes
            except Exception as e:
                print("Exception in get_processes", e)
                return [1]

    def clean_up(self):
        self.enviroment_setter.clean_up()
        for other in self.others:
            other.clean_up()

    def add_to_base(self, path):
        """add a path as new base to self.path
        eg. Tests/p-CG-OF/boxTurb => Tests/8/p-CG-OF/boxTurb
        """
        self.path_ = self.get_full_path(
            self.base_path, Path(path) / self.name, self.case_name
        )

    def add_to_path(self, path):
        """add a path as new base to self.path
        eg. Tests/8/boxTurb => Tests/8/p-CG-OF/boxTurb
        """
        self.path_ = self.get_full_path(
            self.base_path, self.name / Path(path), self.case_name
        )

    def combine(self, other):
        self.others.append(other)
        other.add_to_base(self.name)
        self.add_to_path(other.name)
        self.enviroment_setter.alternative_cache_path_ = Path(self.path.parent)
        self.enviroment_setter.path = self.path
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

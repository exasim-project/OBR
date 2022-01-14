import os
from pathlib import Path
from subprocess import check_output


class CaseOrigin:
    def __init__(self, args):
        self.args = args

    def copy_to(self, dst):
        cmd = ["cp", "-r", self.path, dst]
        print(cmd)
        check_output(cmd)


class OpenFOAMTutorialCase(CaseOrigin):
    def __init__(self, args_dict):
        super().__init__(args_dict)
        self.tutorial_domain = self.args["origin"]
        self.solver = self.args["solver"]
        self.case = self.args["case"]

    @property
    def path(self):
        foam_tutorials = Path(os.environ["FOAM_TUTORIALS"])
        return foam_tutorials / self.tutorial_domain / self.solver / self.case


class OpenFOAMExternalCase(CaseOrigin):
    def __init__(self, args_dict):
        super().__init__(args_dict)
        print(args_dict)
        self.path = Path(self.args["origin"]).expanduser().resolve()
        print(self.path)
        self.solver = self.args["solver"]
        self.build = self.args.get("build", [])


class TestCase(CaseOrigin):
    def __init__(self, args_dict):
        super().__init__(args_dict)
        self.path_ = path
        self.solver = solver

    @property
    def path(self):
        return Path(self.path_)

import os
from pathlib import Path
from subprocess import check_output
from core import execute


class CaseOrigin:
    def __init__(self, args):
        self.args = args

    def init(self, job):
        pass


class OpenFOAMTutorialCase(CaseOrigin):
    """Copies an OpenFOAM case from the FOAM_TUTORIALS folder
    needs a dict with origin (eg. incompressible) solver an case
    """

    def __init__(self, args_dict):
        super().__init__(args_dict)
        self.tutorial_domain = self.args["origin"]
        self.solver = self.args["solver"]
        self.case = self.args["case"]

    def init(self, job):
        check_output(["cp", "-r", self.path, job.path + "/case"])

    @property
    def path(self):
        foam_tutorials = Path(os.environ["FOAM_TUTORIALS"])
        return foam_tutorials / self.tutorial_domain / self.solver / self.case


class CaseOnDisk(CaseOrigin):
    """Copies an OpenFOAM case from disk and copies it into the workspace

    needs origin, solver to be specified
    """

    def __init__(self, args_dict):
        super().__init__(args_dict)
        raw_path = self.args["origin"]
        if raw_path.startswith("~"):
            raw_path = Path(self.args["origin"]).expanduser()
        else:
            raw_path = Path(os.path.expandvars(raw_path))
        self.path = raw_path.resolve()

    def init(self, job):
        execute(["cp -r {} case".format(self.path)], job.path)


class GitRepo(CaseOrigin):
    """Copies an OpenFOAM case from disk and copies it into the workspace

    needs origin, solver to be specified

    """

    def __init__(self, args_dict):
        super().__init__(args_dict)
        self.url = self.args["url"]
        self.commit = self.args.get("commit", None)
        self.branch = self.args.get("branch", None)
        self.folder = self.args.get("folder", None)

    def init(self, job):
        if not self.folder:
            execute(["git clone {} case".format(self.url)], cwd=job.path)
        else:
            execute(["git clone {} repo".format(self.url)], cwd=job.path)
            execute(["cp -r repo/{} case".format(self.folder)], cwd=job.path)

        if self.commit:
            execute(
                ["git checkout {}".format(self.commit)], cwd=Path(job.path) / "case"
            )
        if self.branch:
            execute(
                ["git checkout {}".format(self.branch)], cwd=Path(job.path) / "case"
            )

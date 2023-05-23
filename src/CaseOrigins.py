import os
from pathlib import Path
from subprocess import check_output


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
        self.tutorial_domain = self.args["domain"]
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
        check_output(f"cp -r {self.path} {job.path}/case".split())


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
        self.cache_folder = self.args.get("cache_folder", None)

    def init(self, job):
        if self.cache_folder and Path(self.cache_folder).exists():
            check_output(["cp", "-r", self.cache_folder, job.path + "/case"])
            return
        if not self.folder:
            check_output(["git", "clone", self.url, "case"], cwd=job.path)
            if self.commit:
                check_output(
                    ["git", "checkout", self.commit], cwd=Path(job.path) / "case"
                )
        else:
            check_output(["git", "clone", self.url, "repo"], cwd=job.path)
            if self.commit:
                check_output(
                    ["git", "checkout", self.commit], cwd=Path(job.path) / "repo"
                )
            check_output(["cp", "-r", f"repo/{self.folder}", "case"], cwd=job.path)

        if self.branch:
            check_output(["git", "checkout", self.branch], cwd=Path(job.path) / "case")

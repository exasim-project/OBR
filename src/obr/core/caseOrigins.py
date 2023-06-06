from os import environ
from os.path import expandvars
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import Union
from subprocess import check_output


class CaseOnDisk:
    """Copies an OpenFOAM case from disk and copies it into the workspace
    needs origin, solver to be specified
    """

    def __init__(self, origin: Union[str, Path], **kwargs):
        raw_path = origin
        if isinstance(origin, str):
            origin = expandvars(origin)
        self.path = Path(origin).expanduser()

    def init(self, path):
        copy_tree(str(self.path), str(Path(path) / "case"))


class OpenFOAMTutorialCase(CaseOnDisk):
    """Copies an OpenFOAM case from the FOAM_TUTORIALS folder
    needs a dict specifing:
    """

    def __init__(self, domain: str, solver: str, case: str, **args_dict):
        """
        Args:
            domain: eg. incompressible
            solver: eg. icoFoam
            case: eg. cavity/cavity
        """
        self.tutorial_domain = domain
        self.solver = solver
        self.case = case
        super().__init__(origin=self.resolve_of_path())

    def resolve_of_path(self):
        foam_tutorials = Path(environ["FOAM_TUTORIALS"])
        return foam_tutorials / self.tutorial_domain / self.solver / self.case


class GitRepo:
    """Clones an OpenFOAM case from a git repository into the workspace"""

    def __init__(
        self,
        url: str,
        commit=None,
        branch=None,
        folder=None,
        cache_folder=None,
        **kwargs,
    ):
        """
        Args:
            url: url to the repo
            commit: whether to checkout a specific commit (optional)
            branch: whether to checkout a specific branch (optional)
            folder: only use a specific subfolder (optional)
            cache_folder: prefer copying from this folder if exists (optional)
        """
        self.url = url
        self.commit = commit
        self.branch = branch
        self.folder = folder
        self.cache_folder = cache_folder

    def init(self, path):
        if self.cache_folder and Path(self.cache_folder).exists():
            check_output(["cp", "-r", self.cache_folder, path + "/case"])
            return
        if not self.folder:
            check_output(["git", "clone", self.url, "case"], cwd=path)
            if self.commit:
                check_output(["git", "checkout", self.commit], cwd=Path(path) / "case")
        else:
            check_output(["git", "clone", self.url, "repo"], cwd=path)
            if self.commit:
                check_output(["git", "checkout", self.commit], cwd=Path(path) / "repo")
            check_output(["cp", "-r", f"repo/{self.folder}", "case"], cwd=path)

        if self.branch:
            check_output(["git", "checkout", self.branch], cwd=Path(path) / "case")

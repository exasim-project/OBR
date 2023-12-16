from os import environ
from os.path import expandvars, isdir
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import Union
from subprocess import check_output
import logging
from git.repo import Repo
from git import InvalidGitRepositoryError


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
        if not isdir(self.path):
            logging.warning(
                f"{self.path.absolute} or some parent directory does not exist!"
            )
            return
        copy_tree(str(self.path), str(Path(path) / "case"))


class OpenFOAMTutorialCase(CaseOnDisk):
    """Copies an OpenFOAM case from the FOAM_TUTORIALS folder
    needs a dict specifying:
    """

    def __init__(self, domain: str, application: str, case: str, **args_dict):
        """
        Args:
            domain: eg. incompressible
            application: eg. icoFoam
            case: eg. cavity/cavity
        """
        self.tutorial_domain = domain
        self.application = application
        self.case = case
        super().__init__(origin=self.resolve_of_path())

    def resolve_of_path(self):
        foam_tutorials = Path(environ["FOAM_TUTORIALS"])
        return foam_tutorials / self.tutorial_domain / self.application / self.case


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
            # if cache folder has been cloned into before, check for new commits
            # either way, copy from cache folder to $path/case
            # if repo init or copying fails for some reason,

            if Path(self.cache_folder + "/.git").exists():
                repo = Repo(self.cache_folder)
                default_remote: str = repo.git.symbolic_ref(
                    "refs/remotes/origin/HEAD", "--short"
                )
                current_commit = repo.git.rev_parse("HEAD")
                origin_branchname = default_remote.split("/")
                # if commit is specified and if the current one does not equal, checkout given commit
                if self.commit and self.commit != current_commit:
                    repo.git.checkout(self.commit)
                # if current == self.commit, do nothing
                # if no commit is specified, simply get latest
                if not self.commit:
                    repo.git.pull(origin_branchname[0], origin_branchname[-1])
                check_output(
                    ["cp", "-r", f"{self.cache_folder}/{self.folder}", path + "/case"]
                )
                return
            else:
                logging.warning(
                    "Could not copy from cache_folder to case, will git clone into it"
                    " instead."
                )

        # No specific subfolder is specified, clone to self.path
        if not self.folder:
            check_output(["git", "clone", self.url, "case"], cwd=path)
            # also copy to cache folder if specified
            if self.commit:
                check_output(["git", "checkout", self.commit], cwd=Path(path) / "case")
            # also copy to cache folder if specified
            if self.cache_folder and "None" not in self.cache_folder:
                check_output(["cp", "-r", path + "/case/.", self.cache_folder])

        else:  # clone to specific subfolder
            check_output(["git", "clone", self.url, "repo"], cwd=path)
            if self.commit:
                check_output(["git", "checkout", self.commit], cwd=Path(path) / "repo")
            # also copy to cache folder if specified
            if self.cache_folder and "None" not in self.cache_folder:
                check_output(["cp", "-r", path + "/repo/.", self.cache_folder])
            check_output(["cp", "-r", f"repo/{self.folder}", "case"], cwd=path)
        # checkout specified branch
        if self.branch:
            check_output(["git", "checkout", self.branch], cwd=Path(path) / "case")
            check_output(["git", "checkout", self.branch], cwd=self.cache_folder)


def instantiate_origin_class(
    class_name: str, args: dict
) -> Union[CaseOnDisk, OpenFOAMTutorialCase, GitRepo, None]:
    """
    Quick factory function to instantiate the wanted class handler.
    Returns:
        - CaseOnDisk, OpenFOAMTutorialCase, or GitRepo on success
        - None on failure.
    """
    if class_name == "GitRepo":
        return GitRepo(**args)
    elif class_name == "OpenFOAMTutorialCase":
        return OpenFOAMTutorialCase(**args)
    elif class_name == "CaseOnDisk":
        return CaseOnDisk(**args)
    else:
        logging.error(
            "'type' must be 'GitRepo', 'OpenFOAMTutorialCase', or 'CaseOnDisk'!"
        )
        return None

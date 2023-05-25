from obr.OpenFOAM.case import OpenFOAMCase

import os
import pytest
from pathlib import Path
import shutil
from git.repo import Repo


@pytest.fixture
def set_up_of_case(tmpdir):
    """If OF exists and is sourced return tutorial path else download"""

    lid_driven_cavity = "incompressible/icoFoam/cavity/cavity"

    if os.environ.get("FOAM_TUTORIALS"):
        src = Path(os.environ.get("FOAM_TUTORIALS")) / lid_driven_cavity
        dst = tmpdir / lid_driven_cavity

        shutil.copytree(src, dst)
        return dst

    of_dir = Path('~/OpenFOAM/OpenFOAM-10')
    if of_dir.exists():
        shutil.copytree(of_dir, tmpdir)
    else:
        of_dir = Path(tmpdir)
        url = "https://github.com/OpenFOAM/OpenFOAM-10.git"
        Repo.clone_from(url=url, to_path=tmpdir, multi_options=['--depth 1'])



    rval = of_dir / "tutorials" / lid_driven_cavity
    return rval


def test_OpenFOAMCaseProperties(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})

    # check basic case structure
    assert of_case.path == set_up_of_case
    assert of_case.constant_folder == set_up_of_case / "constant"
    assert of_case.system_folder == set_up_of_case / "system"
    assert of_case.zero_folder == set_up_of_case / "0"
    assert of_case.blockMeshDict == of_case.system_folder / "blockMeshDict"


def test_OpenFOAMCaseControlDictGetter(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})
    # check file getter
    assert of_case.controlDict.get("application") == "icoFoam"
    assert of_case.controlDict.get("startTime") == 0


def test_OpenFOAMCasefvSolutionDictGetter(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})
    assert of_case.fvSolution.get("solvers")["p"]["solver"] == "PCG"
    assert of_case.fvSolution.get("solvers")["U"]["solver"] == "smoothSolver"


def test_OpenFOAMCaseFvSchemesGetter(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})
    # currently only get converts to integer type
    assert of_case.fvSolution.get("PISO")["nCorrectors"] == 2

    assert of_case.fvSchemes.get("ddtSchemes")["default"] == "Euler"
    assert of_case.fvSchemes.get("gradSchemes")["default"] == "Gauss linear"
    assert of_case.fvSchemes.get("divSchemes")["default"] == "none"
    assert of_case.fvSchemes.get("divSchemes")["div(phi,U)"] == "Gauss linear"


def test_OpenFOAMCaseSetter(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})
    # check file setter
    of_case.controlDict.set({"startTime": 10})
    assert of_case.controlDict.get("startTime") == 10

    assert of_case.is_decomposed is False

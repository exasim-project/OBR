from obr.OpenFOAM.case import OpenFOAMCase

import os
import pytest
from pathlib import Path
import shutil
from subprocess import check_output


@pytest.fixture
def set_up_of_case(tmpdir):
    """If OF exists and is sourced return tutorial path else download"""

    lid_driven_cavity = "incompressible/icoFoam/cavity/cavity"

    if os.environ.get("FOAM_TUTORIALS"):
        src = Path(os.environ.get("FOAM_TUTORIALS")) / lid_driven_cavity
        dst = tmpdir / lid_driven_cavity

        shutil.copytree(src, dst)
        return dst

    check_output(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            "https://github.com/OpenFOAM/OpenFOAM-10.git",
        ],
        cwd=tmpdir,
    )

    of_dir = tmpdir / "OpenFOAM-10"

    check_output(["git", "sparse-checkout", "set", "tutorials"], cwd=of_dir)

    return of_dir / "tutorials" / lid_driven_cavity


def test_OpenFOAMCaseProperties(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})

    # check basic case structure
    assert of_case.path == set_up_of_case
    assert of_case.constant_folder == set_up_of_case / "constant"
    assert of_case.system_folder == set_up_of_case / "system"
    assert of_case.zero_folder == set_up_of_case / "0"

    # check file getter
    assert of_case.controlDict.get("application") == "icoFoam"
    assert of_case.controlDict.get("startTime") == 0
    assert of_case.fvSolution.get("solvers")["p"]["solver"] == "PCG"

    # check file setter
    of_case.controlDict.set({"startTime": 10})
    assert of_case.controlDict.get("startTime") == 10

from obr.OpenFOAM.case import OpenFOAMCase
from subprocess import check_output

import os
import pytest
from pathlib import Path
import shutil
from git.repo import Repo
from pathlib import Path


def create_logs(path: Path):
    log_names = [
        "blockMesh_2023-11-30_22:13:31.log",
        "icoFoam_2023-11-30_22:14:31.log",
        "icoFoam_2023-11-30_22:15:31.log",
        "icoFoam_2023-11-30_22:13:31.log",
    ]

    for log in log_names:
        with open(path / log, "a"):
            continue


@pytest.fixture
def set_up_of_case(tmpdir):
    """If OF exists and is sourced return tutorial path else download"""

    lid_driven_cavity = "incompressible/icoFoam/cavity/cavity"

    if os.environ.get("FOAM_TUTORIALS"):
        src = Path(os.environ.get("FOAM_TUTORIALS")) / lid_driven_cavity
        dst = tmpdir / lid_driven_cavity

        shutil.copytree(src, dst)
        create_logs(dst)
        return dst

    # OpenFOAM might exist but not being sourced
    of_dir = Path("~/OpenFOAM/OpenFOAM-10")
    if of_dir.exists():
        shutil.copytree(of_dir, tmpdir)
    else:
        of_dir = Path(tmpdir)
        url = "https://github.com/OpenFOAM/OpenFOAM-10.git"
        Repo.clone_from(url=url, to_path=tmpdir, multi_options=["--depth 1"])

    rval = of_dir / "tutorials" / lid_driven_cavity
    create_logs(rval)
    return rval


def test_OpenFOAMCaseFindsLatestLog(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})
    assert (
        of_case.latest_solver_log_path
        == set_up_of_case / "icoFoam_2023-11-30_22:15:31.log"
    )


def test_OpenFOAMCaseProperties(set_up_of_case):
    of_case = OpenFOAMCase(set_up_of_case, {})

    # check basic case structure
    assert of_case.path == set_up_of_case
    assert of_case.constant_folder == set_up_of_case / "constant"
    assert of_case.system_folder == set_up_of_case / "system"
    assert of_case.zero_folder == set_up_of_case / "0"
    assert of_case.blockMeshDict == of_case.system_folder / "blockMeshDict"

    times = ["1e-06", "2", "3.0"]
    for time_folder in times:
        check_output(
            ["cp", "-r", str(of_case.zero_folder), str(of_case.path / time_folder)]
        )
    times = ["0"] + times
    times.sort()

    assert of_case.time_folder == [set_up_of_case / time for time in times]


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


def test_detailed_update(set_up_of_case):
    class mock_job:
        doc = {"state": {}}

    of_case = OpenFOAMCase(set_up_of_case, mock_job())

    # copy log file with failure
    log_folder = Path(__file__).parent
    shutil.copyfile(
        log_folder / "logs/icoFoamIncomplete.log",
        of_case.path / "icoFoam_2023-12-30_22:13:31.log",
    )
    assert of_case.finished == False
    assert of_case.job.doc["state"]["global"] == "incomplete"
    assert of_case.current_time == 0.49

    # copy log file with failure
    log_folder = Path(__file__).parent
    shutil.copyfile(
        log_folder / "logs/icoFoamFailure.log",
        of_case.path / "icoFoam_2023-12-30_22:13:31.log",
    )

    # Logs with failures return false
    with open(of_case.path / "solverExitCode.log", "w") as exitCodeLog:
        exitCodeLog.write("1")
    assert of_case.process_latest_time_stats() == False
    assert of_case.finished == False
    assert of_case.job.doc["state"]["global"] == "failure"
    assert of_case.current_time == 9

    # copy log files
    log_folder = Path(__file__).parent
    shutil.copyfile(
        log_folder / "logs/icoFoamSuccess.log",
        of_case.path / "icoFoam_2023-12-30_22:13:31.log",
    )

    # Logs with failures return false
    assert of_case.process_latest_time_stats() == True
    assert of_case.finished == True
    assert of_case.job.doc["state"]["global"] == "completed"
    assert of_case.current_time == 0.5

    shutil.copyfile(
        log_folder / "logs/icoFoamStartupFailure.log",
        of_case.path / "icoFoam_2023-12-30_22:13:31.log",
    )
    assert of_case.finished == False
    assert of_case.job.doc["state"]["global"] == "failure"

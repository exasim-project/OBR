from obr.create_tree import create_tree
from obr.signac_wrapper.operations import OpenFOAMProject

import pytest
import os


@pytest.fixture
def emit_test_config():
    return {
        "case": {
            "type": "GitRepo",
            "solver": "pisoFoam",
            "url": "https://develop.openfoam.com/committees/hpc.git",
            "folder": "Lid_driven_cavity-3d/S",
            "commit": "f9594d16aa6993bb3690ec47b2ca624b37ea40cd",
            "cache_folder": "None/S",
            "post_build": [
                {"shell": "cp system/fvSolution.fixedNORM system/fvSolution"},
                {"controlDict": {"writeFormat": "binary", "libs": ["libOGL.so"]}},
                {
                    "fvSolution": {
                        "set": "solvers/p",
                        "clear": True,
                        "tolerance": "1e-04",
                        "relTol": 0,
                        "maxIter": 3000,
                    }
                },
            ],
        },
    }


def test_create_tree(tmpdir, emit_test_config):
    project = OpenFOAMProject.init_project(root=tmpdir)

    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)

    workspace_dir = tmpdir / "workspace"

    assert workspace_dir.exists() == True

    _, folder, _ = next(os.walk(workspace_dir))

    assert len(folder) == 1
    for fold in folder:
        case_fold = workspace_dir / fold
        assert case_fold.exists() == True

    project.run(names=["fetchCase"])


def test_call_generate_tree(tmpdir, emit_test_config):
    project = OpenFOAMProject.init_project(root=tmpdir)
    workspace_dir = tmpdir / "workspace"

    operation = {
        "operation": "controlDict",
        "schema": "{endTime}",
        "values": [{"endTime": 100}],
    }
    emit_test_config["variation"] = [operation]
    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)

    assert workspace_dir.exists() == True

    project.run(names=["generate"])

    # should have two folders now
    _, folder_after, _ = next(os.walk(workspace_dir))
    assert len(folder_after) == 2

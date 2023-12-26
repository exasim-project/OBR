from obr.create_tree import create_tree, add_variations, extract_from_operation
from obr.signac_wrapper.operations import OpenFOAMProject

import pytest
import os
from pathlib import Path
import shutil
from pathlib import Path


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
            "uses": [{"fvSolution": "fvSolution.fixedNORM"}],
            "post_build": [
                {"shell": "touch test"},
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


def test_extract_from_operation():
    operation = {"operation": "op1", "key": "foo", "values": [1, 2, 3]}
    res = extract_from_operation(operation, 1)
    assert res == {"keys": ["foo"], "path": "foo/1/", "args": {"foo": 1}}

    operation = {
        "operation": "op1",
        "schema": "path/{foo}",
        "values": [{"foo": 1}, {"foo": 2}, {"foo": 3}],
    }
    res = extract_from_operation(operation, {"foo": 1})
    assert res == {"keys": ["foo"], "path": "path/1/", "args": {"foo": 1}}

    operation = {
        "operation": "op1",
        "schema": "path/{foo}",
        "common": {"c1": "v1"},
        "values": [{"foo": 1}, {"foo": 2}, {"foo": 3}],
    }
    res = extract_from_operation(operation, {"foo": 1})
    assert res == {
        "keys": ["foo", "c1"],
        "path": "path/1/",
        "args": {"foo": 1, "c1": "v1"},
    }


def test_add_variations():
    class MockJob:
        id = "0"
        sp = {}
        doc = {}

        def init(self):
            pass

    class MockProject:
        def open_job(self, statepoint):
            return MockJob()

    operations = []
    test_variation = [
        {
            "operation": "n/a",
            "schema": "n/a",
            "values": [{"foo": 1}, {"foo": 2}, {"foo": 3}],
        }
    ]
    id_path_mapping = {}
    operations = add_variations(
        operations, MockProject(), test_variation, MockJob(), id_path_mapping
    )

    assert operations == ["n/a"]


def test_create_tree(tmpdir, emit_test_config):
    project = OpenFOAMProject.init_project(path=tmpdir)

    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)

    workspace_dir = tmpdir / "workspace"

    assert workspace_dir.exists() == True

    _, folder, _ = next(os.walk(workspace_dir))

    assert len(folder) == 1
    fold = folder[0]
    case_base_fold = workspace_dir / fold
    assert case_base_fold.exists() == True

    project.run(names=["fetchCase"])

    # after fetch case we should have a base case
    case_fold = case_base_fold / "case"
    assert case_fold.exists() == True
    fvSolution_file = case_fold / "system/fvSolution"
    assert fvSolution_file.exists() == True
    shell_file = case_fold / "test"
    assert shell_file.exists() == True


def test_call_generate_tree(tmpdir, emit_test_config):
    project = OpenFOAMProject.init_project(path=tmpdir)
    workspace_dir = tmpdir / "workspace"
    view_dir = tmpdir / "view"

    operation = {
        "operation": "controlDict",
        "schema": "{endTime}",
        "values": [{"endTime": 100}],
    }
    emit_test_config["variation"] = [operation]
    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)

    assert workspace_dir.exists() == True
    assert view_dir.exists() == True
    assert (view_dir / "base" / "100").exists() == True
    assert Path(view_dir / "base" / "100").is_symlink() == True

    import os

    project.run(names=["generate"])

    # should have two folders now
    _, folder_after, _ = next(os.walk(workspace_dir))
    assert len(folder_after) == 2


def test_cache_folder(tmpdir, emit_test_config):
    emit_test_config["case"]["cache_folder"] = f"{tmpdir}/tmp"
    project = OpenFOAMProject.init_project(path=tmpdir)

    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)

    workspace_dir = tmpdir / "workspace"

    assert workspace_dir.exists()

    _, folder, _ = next(os.walk(workspace_dir))

    assert len(folder) == 1
    fold = folder[0]
    case_base_fold = workspace_dir / fold
    assert case_base_fold.exists() is True

    project.run(names=["fetchCase"])

    # after purgin and recreating the workspace, the cache folder should be used
    Path(f"{tmpdir}/tmp/test").touch()
    shutil.rmtree(workspace_dir)
    shutil.rmtree(tmpdir /".signac")
    project = OpenFOAMProject.init_project(path=tmpdir)
    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)
    project.run(names=["fetchCase"])

    job_folder = Path(workspace_dir).iterdir().__next__()
    assert Path(job_folder / "case" / "test").exists()

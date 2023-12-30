from obr.create_tree import create_tree
from obr.signac_wrapper.operations import OpenFOAMProject
from obr.OpenFOAM.case import OpenFOAMCase
from obr.core.core import key_to_path
import pytest
import os
import json


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


def test_md5sum_calculation(tmpdir, emit_test_config):
    project = OpenFOAMProject.init_project(root=tmpdir)

    create_tree(project, emit_test_config, {"folder": tmpdir}, skip_foam_src_check=True)

    workspace_dir = tmpdir / "workspace"

    assert workspace_dir.exists()

    root, folder, files = next(os.walk(workspace_dir))

    assert len(folder) == 1
    for fold in folder:
        case_fold = workspace_dir / fold
        assert case_fold.exists()
    project.run(names=["fetchCase"])

    case_path = os.path.join(root, folder[0], "case")
    job = None

    job_doc_path = os.path.join(root, folder[0], "signac_job_document.json")
    with open(job_doc_path) as job_file:
        job = json.load(job_file)
        case = OpenFOAMCase(case_path, job)

        md5summed_files_target = set([
            f.rsplit("/", 1)[1] for f in case.config_file_tree
        ])
        md5summed_files_actual = [
            key_to_path(file.rsplit("/", 1)[1])
            for file in job["cache"].get("md5sum", [])
        ]

        for fname in md5summed_files_actual:
            if fname in md5summed_files_target:
                md5summed_files_target.remove(fname)
        assert len(md5summed_files_target) == 0

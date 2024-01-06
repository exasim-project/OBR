import pytest
import yaml  # type: ignore[import]
import os

from contextlib import redirect_stdout
from pathlib import Path

from obr.create_tree import create_tree
from obr.signac_wrapper.operations import OpenFOAMProject
from obr.signac_wrapper.submit import submit_impl
from obr.core.parse_yaml import read_yaml


def create_submit_template(tmpdir):
    submit_script_content = """
{% extends "base_script.sh" %}
{% block header %}
    {% block preamble %}
#!/bin/bash
test_token
#SBATCH --job-name="{{ id }}"
        {% set memory_requested = operations | calc_memory(parallel)  %}
{% if memory_requested %}
    #SBATCH --mem={{ memory_requested|format_memory }}
{% endif %}
{% if partition %}
    #SBATCH --partition={{ partition }}
{% endif %}
{% set walltime = operations | calc_walltime(parallel) %}
{% if walltime %}
    #SBATCH -t {{ walltime|format_timedelta }}
{% endif %}
{% if job_output %}
#SBATCH --output={{ job_output }}
#SBATCH --error={{ job_output }}
{% endif %}
{% endblock preamble %}
#SBATCH --gpus-per-node={{ gpus_per_node }}
#SBATCH --tasks-per-node={{ tasks_per_node }}
#SBATCH --account={{ account }}
{% endblock header %}
"""
    with open(tmpdir / "local.sh", "w") as f:
        f.write(submit_script_content)


def test_create_tree(tmpdir):
    from flow.environment import (
        TestEnvironment,
    )

    project = OpenFOAMProject.init_project(path=tmpdir)
    project._environment = TestEnvironment()

    config_str = read_yaml({"config": str(Path(__file__).parent / "cavity.yaml")})
    config_str = config_str.replace("\n\n", "\n")
    cavity_config = yaml.safe_load(config_str)

    # remove blockMesh and decomposePar post builds from fetchCase step
    # otherwise the unit test would require functioning OpenFOAM environment
    cavity_config["case"] = {
        "type": "GitRepo",
        "solver": "pisoFoam",
        "url": "https://develop.openfoam.com/committees/hpc.git",
        "folder": "Lid_driven_cavity-3d/S",
        "commit": "f9594d16aa6993bb3690ec47b2ca624b37ea40cd",
        "cache_folder": "None/S",
        "uses": [{"fvSolution": "fvSolution.fixedNORM"}],
    }

    create_tree(project, cavity_config, {"folder": tmpdir}, skip_foam_src_check=True)

    workspace_dir = tmpdir / "workspace"
    assert workspace_dir.exists() == True

    project.run(names=["fetchCase"])
    create_submit_template(tmpdir)

    account = "account"
    partition = "partition"

    # Check if wrong template location raises a FileNotFoundError
    with pytest.raises(FileNotFoundError):
        submit_impl(
            project,
            [j for j in project],
            ["generate"],
            template=tmpdir / "does_not_exists.sh",
            account=account,
            partition=partition,
            pretend=True,
            bundling_key=None,
            scheduler_args="",
        )

    with open("submit.log", "w") as f:
        with redirect_stdout(f):
            submit_impl(
                project,
                [j for j in project],
                ["generate"],
                template=tmpdir / "local.sh",
                account=account,
                partition=partition,
                pretend=True,
                bundling_key=None,
                scheduler_args="",
            )

    templates_dir = tmpdir / "templates"
    assert templates_dir.exists() == True

    with open("submit.log", "r") as f:
        submit_log = f.read()
        assert "test_token" in submit_log
        assert "--account=account" in submit_log
        assert "--partition=partition" in submit_log
        assert "--mem=" not in submit_log

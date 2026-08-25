import pytest

from obr.signac_wrapper.operations import (
    OpenFOAMProject,
    _link_path,
    get_raw_cmds,
    has_post_cmds,
    has_pre_cmds,
    runParallelPost,
    runParallelPre,
    wrap_raw_cmds,
)
from obr.create_tree import setup_job_doc

from subprocess import check_output
from pathlib import Path

WATCHDOG_PRE = ["of_watchdog.sh --loop &", "watchdog_pid=${!}"]
WATCHDOG_POST = ["kill $watchdog_pid"]


def test_link_path(tmpdir):
    check_output(["mkdir", "src"], cwd=tmpdir)
    check_output(["touch", "src/file1"], cwd=tmpdir)
    check_output(["mkdir", "src/fold1"], cwd=tmpdir)
    check_output(["touch", "src/fold1/file2"], cwd=tmpdir)

    _link_path(tmpdir / "src", tmpdir / "dst", "", copy_instead_link=False)

    dst = Path(tmpdir) / "dst"

    assert dst.exists() == True

    dst_file = dst / "file1"

    assert dst_file.exists() == True
    assert dst_file.is_symlink() == True

    dst_fold = dst / "fold1"
    assert dst_fold.exists() == True


def make_job(tmpdir, statepoint):
    project = OpenFOAMProject.init_project(path=str(tmpdir))
    job = project.open_job(statepoint)
    job.init()
    setup_job_doc(job)
    return job


@pytest.fixture
def job_with_cmds(tmpdir):
    return make_job(
        tmpdir,
        {"pre_cmds": WATCHDOG_PRE, "post_cmds": WATCHDOG_POST, "has_child": False},
    )


def test_pre_post_ops_emit_verbatim(job_with_cmds):
    assert runParallelPre(job_with_cmds) == "of_watchdog.sh --loop &\nwatchdog_pid=${!}"
    assert runParallelPost(job_with_cmds) == "kill $watchdog_pid"


def test_wrap_raw_cmds_order_and_verbatim(job_with_cmds):
    solver_line = "mpirun -np 2 icoFoam -parallel -case c > log 2>&1|| true && echo $? > e "
    body = wrap_raw_cmds(job_with_cmds, solver_line)
    assert body.splitlines() == WATCHDOG_PRE + [solver_line] + WATCHDOG_POST
    # provenance recorded, raw lines untouched
    hist = [e["cmd"] for e in job_with_cmds.doc["history"]]
    assert "watchdog_pid=${!}" in hist
    assert "kill $watchdog_pid" in hist


def test_no_cmds_paths(tmpdir):
    job = make_job(tmpdir, {"has_child": False})
    assert not has_pre_cmds(job)
    assert not has_post_cmds(job)
    assert wrap_raw_cmds(job, "solver") == "solver"
    assert runParallelPre(job).startswith(":")
    assert runParallelPost(job).startswith(":")


def test_single_string_promoted(tmpdir):
    job = make_job(tmpdir, {"pre_cmds": "echo hi", "has_child": False})
    assert get_raw_cmds(job, "pre_cmds") == ["echo hi"]


def test_parent_statepoint_inheritance(tmpdir):
    job = make_job(tmpdir, {"parent": {"pre_cmds": WATCHDOG_PRE}, "has_child": False})
    assert get_raw_cmds(job, "pre_cmds") == WATCHDOG_PRE

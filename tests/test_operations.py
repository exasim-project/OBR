import pytest

from obr.signac_wrapper.operations import (
    OpenFOAMProject,
    _link_path,
    get_raw_cmds,
    has_post_cmds,
    has_pre_cmds,
    runParallelPost,
    runParallelPre,
    needs_own_proc_mesh,
    prepare_cmds,
    raw_cmd_env,
    solver_args,
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
    env = raw_cmd_env(job_with_cmds)
    assert runParallelPre(job_with_cmds) == env + "\nof_watchdog.sh --loop &\nwatchdog_pid=${!}"
    assert runParallelPost(job_with_cmds) == env + "\nkill $watchdog_pid"


def test_wrap_raw_cmds_order_and_verbatim(job_with_cmds):
    solver_line = (
        "mpirun -np 2 icoFoam -parallel -case c > log 2>&1|| true && echo $? > e "
    )
    body = wrap_raw_cmds(job_with_cmds, solver_line)
    assert body.splitlines() == [raw_cmd_env(job_with_cmds)] + WATCHDOG_PRE + [solver_line] + WATCHDOG_POST
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


def test_solver_args(tmpdir):
    assert solver_args(make_job(tmpdir, {"has_child": False})) == ""
    pool = "-pool fixedSizeMemoryPool -poolSize 200"
    job = make_job(tmpdir, {"parent": {"solver_args": pool}, "has_child": False})
    assert solver_args(job) == pool
    job = make_job(tmpdir, {"solver_args": ["-pool", "fixedSizeMemoryPool"], "has_child": False})
    assert solver_args(job) == "-pool fixedSizeMemoryPool"


def test_raw_cmd_env(tmpdir):
    job = make_job(tmpdir, {"numberOfSubdomains": 8, "has_child": False})
    env = raw_cmd_env(job)
    assert env.startswith("export OBR_JOB=")
    assert f"OBR_CASE={job.path}/case" in env
    assert "OBR_NP=8" in env


def test_needs_own_proc_mesh(tmpdir):
    assert not needs_own_proc_mesh(make_job(tmpdir, {"has_child": False}))
    flag = {"copy_proc_constant": True}
    assert needs_own_proc_mesh(make_job(tmpdir, {"parent": flag, "has_child": False}))
    # intermediate levels keep the symlinks
    assert not needs_own_proc_mesh(make_job(tmpdir, {"parent": flag, "has_child": True}))
    # former key still selects the copy
    assert needs_own_proc_mesh(make_job(tmpdir, {"renumber": "parallel", "has_child": False}))


PREPARE = [{"parallel": "renumberMesh -overwrite"}, {"run": "cfdPrepare --launcher 'srun -n'"}]


def test_prepare_cmds_parallel_and_run(tmpdir):
    job = make_job(tmpdir, {"prepare": PREPARE, "numberOfSubdomains": 8, "has_child": False})
    lines = prepare_cmds(job, "t")
    case = f"{job.path}/case"
    assert lines[0] == f"mkdir -p {case}/.obr"
    assert f"( cd {case} && mpirun -np 8 renumberMesh -overwrite -parallel -case {case} ) > {case}/log.renumberMesh 2>&1" in lines[1]
    assert f"[ -f {case}/.obr/prepare_1_renumberMesh.done ] ||" in lines[1]
    assert "exit 1" in lines[1]
    assert f"( cd {case} && cfdPrepare --launcher 'srun -n' ) > {case}/log.cfdPrepare 2>&1" in lines[2]
    assert [e["type"] for e in job.doc["history"]].count("prepare") == 2


def test_prepare_cmds_serial_and_none(tmpdir):
    job = make_job(tmpdir, {"parent": {"prepare": PREPARE[:1]}, "numberOfSubdomains": 1, "has_child": False})
    assert f"( cd {job.path}/case && renumberMesh -overwrite -case {job.path}/case )" in prepare_cmds(job, "t")[1]
    assert prepare_cmds(make_job(tmpdir, {"has_child": False}), "t") == []


def test_prepare_cmds_invalid(tmpdir):
    job = make_job(tmpdir, {"prepare": [{"source": "env"}], "has_child": False})
    with pytest.raises(ValueError):
        prepare_cmds(job, "t")

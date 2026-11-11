import re
from pathlib import Path

import pytest

from obr import foamLog
from obr.postPro.runtime import runtime_record, case_write_interval

LOGS = Path(__file__).parent / "logs"


def write_timed_log(dst: Path, seconds_per_step: float = 1.0) -> Path:
    """icoFoamSuccess.log with ExecutionTime/ClockTime advancing by seconds_per_step per Timestep,
    the original advances less than the 1 s ClockTime resolution"""
    step = iter(range(1, 10**6))

    def timed(_):
        t = next(step) * seconds_per_step
        return f"ExecutionTime = {t:g} s  ClockTime = {t:g} s"

    text = (LOGS / "icoFoamSuccess.log").read_text()
    text = re.sub(r"ExecutionTime = \S+ s\s+ClockTime = \S+ s", timed, text)
    dst.write_text(text)
    return dst


def make_case(path: Path, n_cells: int = None, write_interval: str = None) -> Path:
    case = path / "case"
    (case / "constant/polyMesh").mkdir(parents=True)
    (case / "system").mkdir()
    if n_cells:
        (case / "constant/polyMesh/owner").write_text(
            "FoamFile\n{\n    version 2.0;\n    format ascii;\n    class labelList;\n"
            f'    note "nPoints:1 nCells:{n_cells} nFaces:1 nInternalFaces:1";\n'
            "    object owner;\n}\n"
        )
    if write_interval:
        (case / "system/controlDict").write_text(
            "FoamFile\n{\n    version 2.0;\n    format ascii;\n    class dictionary;\n"
            "    object controlDict;\n}\n"
            "application icoFoam;\nwriteControl timeStep;\n"
            f"writeInterval {write_interval};\n"
        )
    return case


def test_runtime_record(tmpdir):
    case = make_case(Path(tmpdir), n_cells=400)
    log = write_timed_log(Path(tmpdir) / "icoFoam.log")
    record = runtime_record(log, case, {"write_interval": 0, "t_skip": 0})

    assert "runtime_error" not in record
    assert record["n_cells"] == 400
    assert record["n_procs"] == 1
    assert record["t_per_timestep"] == pytest.approx(1.0)
    # NCT: core seconds per cell and outer iteration
    assert record["nct"] == pytest.approx(1.0 / 400)
    assert record["n_writes"] == 0
    assert record["foamLog_version"] == foamLog.__version__
    # flat, json-serialisable record as written to postpro.json
    assert all(not isinstance(v, (list, dict)) for v in record.values())


def test_runtime_record_options(tmpdir):
    case = make_case(Path(tmpdir), n_cells=400)
    log = write_timed_log(Path(tmpdir) / "icoFoam.log")
    record = runtime_record(
        log, case, {"write_interval": 0, "t_skip": 0, "n_cells": 800, "prefix": "rt_"}
    )
    assert record["rt_n_cells"] == 800
    assert record["rt_nct"] == pytest.approx(1.0 / 800)
    assert not any(k for k in record if not k.startswith("rt_"))


def test_runtime_record_write_interval_from_case(tmpdir):
    """The log has no controlDict dump: the write interval comes from the case"""
    log = write_timed_log(Path(tmpdir) / "icoFoam.log")
    with_interval = make_case(Path(tmpdir) / "a", n_cells=400, write_interval="20")
    assert case_write_interval(with_interval) == 20
    record = runtime_record(log, with_interval, {"t_skip": 0})
    assert record["write_interval"] == 20
    assert record["n_writes"] == 5

    variable = make_case(Path(tmpdir) / "b", n_cells=400, write_interval="$interval")
    assert case_write_interval(variable) is None
    assert "writeInterval" in runtime_record(log, variable, {"t_skip": 0})["runtime_error"]


@pytest.mark.parametrize(
    "log", ["icoFoamFailure.log", "icoFoamIncomplete.log", "icoFoamStartupFailure.log"]
)
def test_runtime_record_error(tmpdir, log):
    case = make_case(Path(tmpdir), n_cells=400)
    record = runtime_record(LOGS / log, case, {"write_interval": 0})
    assert list(record) == ["runtime_error"]

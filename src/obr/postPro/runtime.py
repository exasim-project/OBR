"""Runtime statistics of a solver log for obr postprocess, computed by foamLog.py.

Enabled by a `runtime` section in the postProcess block of the yaml file:

    postProcess:
      queries: [...]
      runtime:
        t_skip: auto         # optional: auto (MSER-5, default) or a time, 0 keeps all Timesteps
        write_interval: 100  # optional: Timesteps between writes, 0 if the run never writes
        n_cells: 1000        # optional: overrides the cell count of the case
        prefix: ""           # optional: prefix of the record keys

Every scalar field of foamLog.RuntimeStatistics (nct, nct_se, t_per_timestep, t_write, ...) is
added to the job's record in postpro.json under its field name. A log that cannot be evaluated
gives a `runtime_error` entry instead.
"""

import dataclasses
import re
from pathlib import Path
from typing import Union

from obr import foamLog
from obr.core.core import get_mesh_stats

CONTINUITY_KEYS = ("continuity_sum_local", "continuity_global", "continuity_cumulative")


def _number(value) -> Union[float, None]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def case_write_interval(case_path: Path) -> Union[int, None]:
    """writeInterval of system/controlDict if writeControl is timeStep and the value is a plain
    number (not a $variable). Fallback for logs without a controlDict dump."""
    control_dict = case_path / "system" / "controlDict"
    if not control_dict.exists():
        return None
    text = control_dict.read_text(errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    entries = foamLog.parse_dict_block(text)
    if entries.get("writeControl") != "timeStep":
        return None
    interval = _number(entries.get("writeInterval"))
    return int(interval) if interval else None


def runtime_record(log_path: Path, case_path: Path, config: dict) -> dict:
    """Run foamLog on log_path and return the flat record entries"""
    config = config or {}
    prefix = config.get("prefix", "")
    t_skip = config.get("t_skip", "auto")
    t_skip = None if t_skip in (None, "auto") else float(t_skip)
    write_interval = config.get("write_interval")
    n_cells = config.get("n_cells") or get_mesh_stats(
        str(case_path / "constant/polyMesh/owner")
    ).get("nCells")

    def statistics(log, interval):
        return foamLog.runtime_statistics(
            log, n_cells=_number(n_cells), write_interval=interval, t_skip=t_skip
        )

    try:
        log = foamLog.read_log(log_path)
        try:
            stats = statistics(log, write_interval)
        except foamLog.FoamLogError as error:
            # the log has no controlDict dump: take the write interval from the case
            fallback = case_write_interval(case_path)
            if write_interval is not None or fallback is None or "writeInterval" not in str(error):
                raise
            stats = statistics(log, fallback)
    except (foamLog.FoamLogError, OSError) as error:
        return {f"{prefix}runtime_error": str(error)}

    record = {}
    for f in dataclasses.fields(stats):
        if not f.repr:
            continue
        value = getattr(stats, f.name)
        if f.name == "continuity_errors":
            if value:
                record.update({prefix + k: v for k, v in zip(CONTINUITY_KEYS, value)})
            continue
        if f.name == "warnings":
            value = "; ".join(value)
        record[prefix + f.name] = value
    record[prefix + "foamLog_version"] = foamLog.__version__
    return record

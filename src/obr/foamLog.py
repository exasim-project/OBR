#!/usr/bin/env python3
"""Read an OpenFOAM solver Log into Timesteps and compute its Runtime statistics.

Timing logic of obr postprocess (runtime section). Everything is taken from the Log
itself; case files on disk are never read. Depends on numpy only, so the file can be
used on its own; compare __version__ when copies are kept elsewhere.
"""

import os
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np

__author__ = "Hendrik Hetmann"
__license__ = "BSD-3-Clause"
__version__ = "2.0.0"

NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"

# Anchored on the stable tail of a Solver line; the solver text before it is kept verbatim (any Dialect).
SOLVER_LINE = re.compile(
    rf"^(?P<solver>\S.*?):\s+Solving for (?P<field>[^\s,]+), Initial residual = (?P<initial>{NUM}), "
    rf"Final residual = (?P<final>{NUM}), No Iterations (?P<iterations>\d+)"
)
TIME_LINE = re.compile(rf"^Time = ({NUM})")
EXECUTION_LINE = re.compile(rf"\bExecutionTime = ({NUM}).*?ClockTime = ({NUM})")
OUTER_ITERATION_LINE = re.compile(r"^PIMPLE: [Ii]teration \d+")
CONTINUITY_LINE = re.compile(
    rf"\btime step continuity errors\s*:\s*sum local\s*=\s*({NUM}),\s*global\s*=\s*({NUM}),\s*cumulative\s*=\s*({NUM})"
)


class FoamLogError(Exception):
    """The Log cannot yield what was asked for; the message says why."""


@dataclass
class SolverLine:
    solver: str
    field: str
    initial: float
    final: float
    iterations: int


@dataclass
class OuterIteration:
    solver_lines: list = field(default_factory=list)
    n_continuity: int = 0


@dataclass
class Timestep:
    time: float
    execution_time: float = None
    clock_time: float = None
    outer_iterations: list = field(default_factory=lambda: [OuterIteration()])
    continuity_errors: tuple = None  # (sum local, global, cumulative), last values in this Timestep

    def solver_lines(self, field_name=None):
        return [l for o in self.outer_iterations for l in o.solver_lines if field_name in (None, l.field)]


@dataclass
class Header:
    case: str
    date: str
    time: str
    host: str
    n_procs: int
    version: str
    executable: str


@dataclass
class Log:
    text: str
    header: Header
    timesteps: list  # complete Timesteps only, i.e. those that reached their ExecutionTime line
    n_cells: int = None
    clock_time: float = None  # last ClockTime anywhere in the Log, i.e. its overall wall time

    @cached_property
    def _uncommented(self):
        text = re.sub(r"//.*?$", "", self.text, flags=re.MULTILINE)
        return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    def dump(self, name):
        """Parsed `<name> { ... }` Dictionary dump (or any named block) of the Log, {} if absent."""
        return parse_named_dict(self._uncommented, name)

    def fields(self):
        """Field names in order of their first Solver line."""
        return list(dict.fromkeys(l.field for t in self.timesteps for l in t.solver_lines()))


def read_log(path):
    return parse_log(Path(path).read_text(errors="replace"))


def parse_log(text):
    timesteps = []
    current = None
    clock_time = None
    for number, line in enumerate(text.splitlines(), 1):
        m = TIME_LINE.match(line)
        if m:
            current = Timestep(float(m.group(1)))
            continue
        m = EXECUTION_LINE.search(line)
        if m:
            clock_time = float(m.group(2))
            if current is not None and current.execution_time is None:
                current.execution_time, current.clock_time = float(m.group(1)), clock_time
                timesteps.append(current)
            continue
        if current is None or current.execution_time is not None:
            continue
        m = SOLVER_LINE.match(line)
        if m:
            current.outer_iterations[-1].solver_lines.append(SolverLine(
                m["solver"], m["field"], float(m["initial"]), float(m["final"]), int(m["iterations"])))
            continue
        if "Solving for" in line:
            raise FoamLogError(f"Unrecognised Solver line {number}: {line.strip()!r}")
        if OUTER_ITERATION_LINE.match(line):
            last = current.outer_iterations[-1]
            if last.solver_lines or last.n_continuity:
                current.outer_iterations.append(OuterIteration())
            continue
        m = CONTINUITY_LINE.search(line)
        if m:
            current.outer_iterations[-1].n_continuity += 1
            current.continuity_errors = tuple(float(v) for v in m.groups())
    n_cells = re.search(r"Total number of cells\s*=\s*(\d+)", text)
    return Log(text, _parse_header(text), timesteps, int(n_cells.group(1)) if n_cells else None, clock_time)


def _parse_header(text):
    head = text.split("\nCreate time", 1)[0]

    def entry(key, default=None):
        m = re.search(rf"^{key}\s*:\s*(.*?)\s*$", head, re.MULTILINE)
        return m.group(1) if m else default

    executable = os.path.basename((entry("Exec") or "unknown").split()[0])
    revision = re.search(r"Revision.*:\s+(\d+)", head)
    if revision:
        executable += " Rev-" + revision.group(1)
    version = re.search(r"Version.*:\s+(\w+)", head)
    return Header(
        case=os.path.basename((entry("Case") or "").rstrip("/")),
        date=entry("Date"),
        time=entry("Time"),
        host=entry("Host"),
        n_procs=int(entry("nProcs", 1)),
        version=version.group(1) if version else None,
        executable=executable,
    )


# ── Dictionary dumps ───────────────────────────────────────────────────────────


def _split_dict_key(text):
    """Split an OpenFOAM dict key off the front of text, keeping parentheses like div(phi,U) intact."""
    depth = 0
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and (char in "{;" or char.isspace()):
            return text[:i].strip(), text[i:]
    return text.strip(), ""


def parse_dict_block(text):
    """Recursively parse the body of an OpenFOAM dict (without its outer braces) into nested dicts of strings."""
    result = {}
    text = text.strip()
    i = 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        key, remainder = _split_dict_key(text[i:])
        if not key:
            i += 1
            continue
        i += len(text[i:]) - len(remainder)
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        if text[i] == "{":
            end = _matching_brace(text, i)
            result[key] = parse_dict_block(text[i + 1:end])
            i = end + 1
        elif text[i] != ";":
            semi = text.find(";", i)
            if semi == -1:
                i += 1
                continue
            result[key] = text[i:semi].strip()
            i = semi + 1
        else:
            result[key] = None
            i += 1
    return result


def _matching_brace(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def parse_named_dict(text, name):
    """Parse the first `<name> { ... }` block of comment-free text, {} if absent."""
    m = re.search(re.escape(name) + r"\s*\{", text)
    if not m:
        return {}
    start = m.end() - 1
    return parse_dict_block(text[start + 1:_matching_brace(text, start)])


# ── Runtime statistics ─────────────────────────────────────────────────────────


@dataclass
class RuntimeStatistics:
    """Runtime statistics of the Timesteps after the Initial transient, on wall time (ClockTime).

    Times in s; *_se is the standard error of the mean; None where the Log cannot tell.
    """
    n_procs: int
    n_cells: int
    t_skip: float
    t_skip_source: str
    n_skipped: int
    n_outer_mean: float
    n_outer_min: int
    n_outer_max: int
    n_correctors: int
    n_non_ortho_correctors: int
    pressure_field: str
    pressure_iterations_mean: float
    timestep_size: float
    end_time: float
    clock_time: float
    t_init: float
    t_per_timestep: float
    t_per_timestep_se: float
    nct: float
    nct_se: float
    cpu_wall_ratio: float
    write_source: str
    n_writes: int
    write_interval: float
    t_write: float
    t_write_se: float
    nwt: float
    nwt_se: float
    continuity_errors: tuple
    warnings: list
    # Per Timestep after the first kept one, for plotting: time, ExecutionTime increment and write flags
    times: np.ndarray = field(repr=False)
    execution_per_timestep: np.ndarray = field(repr=False)
    write_timesteps: np.ndarray = field(repr=False)
    after_write_timesteps: np.ndarray = field(repr=False)


def runtime_statistics(log, n_cells=None, write_interval=None, t_skip=None):
    """Explicit n_cells / write_interval (in Timesteps, 0: the run never writes) / t_skip win over the Log;
    t_skip None detects the Initial transient."""
    steps = log.timesteps
    if len(steps) < 3:
        raise FoamLogError(f"Only {len(steps)} complete Timesteps in Log, at least 3 are needed")
    n_cells = n_cells or log.n_cells
    if not n_cells:
        raise FoamLogError("nCells not in Log, pass it explicitly (--nCells)")
    pressure = next((f for f in ("p", "p_rgh") if f in log.fields()), None)
    if pressure is None:
        raise FoamLogError("No pressure Solver lines (p or p_rgh) in Log")
    n_procs = log.header.n_procs

    times = np.array([t.time for t in steps])
    execution = np.array([t.execution_time for t in steps])
    clock = np.array([t.clock_time for t in steps])
    n_outer = np.array([len(t.outer_iterations) for t in steps])
    pressure_solves = [t.solver_lines(pressure) for t in steps]
    pressure_iterations = np.array([sum(l.iterations for l in s) for s in pressure_solves])
    writes, write_source, write_interval = _write_steps(log, write_interval, times)

    t_skip_source = "explicit"
    if t_skip is None:
        transient = detect_tskip(times, {
            "p_initial_residual": [s[0].initial if s else np.nan for s in pressure_solves],
            "pressure_lin_solver_iterations": pressure_iterations,
            "n_outer_corr": n_outer,
        })
        t_skip = transient.t_skip
        t_skip_source = f"MSER-5, dominated by {transient.dominating_indicator}" if transient.n_skip else "MSER-5"
    keep = times > t_skip if t_skip > 0 else np.ones(len(times), dtype=bool)
    if keep.any() and writes[keep][0]:
        # A Write event must lie wholly in the window: start it after a write in its first Timestep
        t_skip = float(times[keep][0])
        keep = times > t_skip
    if keep.sum() < 3:
        raise FoamLogError(f"Only {keep.sum()} Timesteps left after t_skip={t_skip}, at least 3 are needed")

    first = steps[0]
    n_correctors = int(sum(o.n_continuity for o in first.outer_iterations) / len(first.outer_iterations))
    kept = [s for s, k in zip(steps, keep) if k]
    n_sub_iterations = round(
        sum(len(t.solver_lines(pressure)) for t in kept) / sum(len(t.outer_iterations) for t in kept))
    n_non_ortho = int((n_sub_iterations - n_correctors) / n_correctors) if n_correctors else None

    times, execution, clock, n_outer, writes = times[keep], execution[keep], clock[keep], n_outer[keep], writes[keep]
    pressure_iterations = pressure_iterations[keep]
    # Increment j is the cost of kept Timestep j+1. The field write lands in the write Timestep, the
    # function-object writes in the next one (they run at the top of the next time loop): one Write event.
    d_clock, d_exec, n_outer_dt = np.diff(clock), np.diff(execution), n_outer[1:]
    write_step, after_write = writes[1:], writes[:-1]
    plain = ~(write_step | after_write)
    if not plain.any():
        raise FoamLogError("Every Timestep is part of a write, NCT cannot be measured")
    if not d_clock[plain].sum():
        raise FoamLogError("ClockTime does not advance over the kept Timesteps: Log too short for wall-time statistics")

    wall_per_outer, wall_per_outer_se = _wall_per_outer_iteration(d_clock, n_outer_dt, plain)
    outer_per_timestep = n_outer_dt[plain].mean()
    warnings = []
    if wall_per_outer_se is None:
        warnings.append("Too few Timesteps for a standard error of NCT")
    elif wall_per_outer_se > 0.05 * wall_per_outer:
        warnings.append(f"NCT standard error is {100 * wall_per_outer_se / wall_per_outer:.0f} % of its value: "
                        "Log too short for the 1 s ClockTime resolution")

    # Extra wall time of each Write event over plain Timesteps with the same Outer iterations. The
    # function-object writes of a write in the last Timestep never reach the Log: that event counts only alone.
    extra = np.append(d_clock - wall_per_outer * n_outer_dt, 0.0)
    events = np.flatnonzero(write_step)
    complete = events[events + 1 < len(d_clock)]
    used = complete if len(complete) else events
    t_writes = extra[used] + extra[used + 1]
    t_write = float(np.mean(t_writes)) if len(used) else None
    t_write_se = float(np.std(t_writes, ddof=1) / np.sqrt(len(used))) if len(used) > 1 else None
    if len(used) and not len(complete):
        warnings.append("t_write from the write in the last Timestep: its function-object writes are not in the Log")
    if len(used) == 1:
        warnings.append("t_write from 1 Write event: no standard error")
    elif t_write_se is not None and t_write_se > 0.05 * abs(t_write):
        warnings.append(f"t_write standard error is {100 * t_write_se / abs(t_write):.0f} % of its value")

    def per_cell(seconds):  # core-seconds (MPI ranks = cores or GPUs) per cell
        return None if seconds is None else float(n_procs * seconds / n_cells)

    t_per_timestep = float(wall_per_outer * outer_per_timestep)
    continuity = next((t.continuity_errors for t in reversed(steps) if t.continuity_errors), None)
    return RuntimeStatistics(
        n_procs=n_procs,
        n_cells=int(n_cells),
        t_skip=float(t_skip),
        t_skip_source=t_skip_source,
        n_skipped=int((~keep).sum()),
        n_outer_mean=float(np.mean(n_outer_dt)),
        n_outer_min=int(np.min(n_outer_dt)),
        n_outer_max=int(np.max(n_outer_dt)),
        n_correctors=n_correctors,
        n_non_ortho_correctors=n_non_ortho,
        pressure_field=pressure,
        pressure_iterations_mean=float(np.mean(pressure_iterations)),
        timestep_size=float(times[-1] - times[-2]),
        end_time=float(times[-1]),
        clock_time=log.clock_time,
        t_init=float(first.clock_time - t_per_timestep),
        t_per_timestep=t_per_timestep,
        t_per_timestep_se=None if wall_per_outer_se is None else float(wall_per_outer_se * outer_per_timestep),
        nct=per_cell(wall_per_outer),
        nct_se=per_cell(wall_per_outer_se),
        cpu_wall_ratio=float(d_exec[plain].sum() / d_clock[plain].sum()),
        write_source=write_source,
        n_writes=len(events),
        write_interval=write_interval,
        t_write=t_write,
        t_write_se=t_write_se,
        nwt=per_cell(t_write),
        nwt_se=per_cell(t_write_se),
        continuity_errors=continuity,
        warnings=warnings,
        times=times[1:],
        execution_per_timestep=d_exec,
        write_timesteps=write_step,
        after_write_timesteps=after_write,
    )


def _wall_per_outer_iteration(d_clock, n_outer, plain):
    """Wall time per Outer iteration over the plain increments, with its standard error from 20 batch means.

    ClockTime is whole seconds, so its rounding cancels between neighbouring increments: consecutive batches
    see it only at their ends. Adjacent batches share an end, which makes the standard error conservative.
    """
    ratio = d_clock[plain].sum() / n_outer[plain].sum()
    starts = np.linspace(0, len(d_clock), min(20, len(d_clock)), endpoint=False).astype(int)
    wall = np.add.reduceat(np.where(plain, d_clock, 0.0), starts)
    outer = np.add.reduceat(np.where(plain, n_outer, 0), starts)
    wall, outer = wall[outer > 0], outer[outer > 0]
    if len(outer) < 2:
        return float(ratio), None
    return float(ratio), float(np.sqrt(np.sum((wall - ratio * outer) ** 2) / (len(outer) * (len(outer) - 1))) / outer.mean())


def _write_steps(log, write_interval, times):
    """Flag the write Timesteps as OpenFOAM's Time::operator++ does: explicit interval, else controlDict dump.

    Returns (flags, source, Timesteps between writes or None).
    """
    steps = np.arange(1, len(times) + 1)
    if write_interval is not None:
        n = int(write_interval)
        return (steps % n == 0) if n else np.zeros(len(times), dtype=bool), "explicit", float(n) if n else None
    control = log.dump("controlDict")
    write_control, interval = control.get("writeControl"), control.get("writeInterval")
    if write_control == "timeStep" and interval:
        # shortcut: counts from the first Timestep of the Log, while OpenFOAM counts the absolute index from
        # <startTime>/uniform/time, so writes shift after a restart from an off-interval write (writeNow);
        # read that index from the Log if such restarts need exact write Timesteps.
        n = int(float(interval))
        return steps % n == 0, "controlDict", float(n)
    if write_control in ("runTime", "adjustableRunTime") and interval:
        # OpenFOAM counts from the time the run started; only startFrom startTime (default latestTime) puts it
        # in the dump
        start = (float(control["startTime"]) if control.get("startFrom", "latestTime") == "startTime"
                 and control.get("startTime") else times[0] - (times[1] - times[0]))
        size = np.diff(times, prepend=start)
        index = np.floor((times - start + 0.5 * size) / float(interval))
        flags = index > np.maximum.accumulate(np.concatenate(([0.0], index[:-1])))
        spacing = np.diff(np.flatnonzero(flags))
        return flags, "controlDict", float(spacing.mean() if len(spacing) else float(interval) / np.mean(size))
    raise FoamLogError("No controlDict dump with writeControl timeStep, runTime or adjustableRunTime in Log: "
                       "pass --writeInterval N (0 if the run never writes)")


# ── Initial transient (MSER-5) ─────────────────────────────────────────────────
#
# MSER-5 (Marginal Standard Error Rule, White 1997): pick the truncation point that minimises the
# standard error of the mean of the remaining data, applied to per-Timestep indicators of numerical
# effort. Effort settles earlier than physical quantities, so this t_skip is right for averaging
# solver statistics but only a lower bound for averaging e.g. force coefficients.


@dataclass
class TransientResult:
    t_skip: float                # value for the `time > t_skip` cutoff
    n_skip: int                  # number of leading Timesteps that cutoff drops
    indicator_indices: dict      # per-indicator truncation index (in Timesteps)
    dominating_indicator: str    # indicator that produced the final (max) index


def mser(series, batch_size=5, max_fraction=0.5, _allow_detrend=True):
    """MSER truncation index in samples of series, searched over batch means within the first max_fraction.

    A minimum on the search limit means the series is trend-dominated; MSER is then re-run once on its
    increments, which removes the trend but keeps the initial spike.
    """
    x = np.asarray(series, dtype=float)
    finite = np.isfinite(x)
    if x.size == 0 or not finite.any():
        return 0
    # Missing samples are patched with the median so indices keep their Timestep alignment
    if not finite.all():
        x = np.where(finite, x, np.median(x[finite]))
    if x.size < 2 * batch_size:
        batch_size = 1
    n_batches = x.size // batch_size
    if n_batches < 4:
        return 0
    batch_means = x[: n_batches * batch_size].reshape(n_batches, batch_size).mean(axis=1)
    if np.allclose(batch_means, batch_means[0]):
        return 0
    d_max = max(1, int(n_batches * max_fraction))
    mser_values = [np.var(batch_means[d:]) / (n_batches - d) for d in range(d_max + 1)]
    d_star = int(np.argmin(mser_values))
    if d_star == d_max and _allow_detrend:
        return mser(np.diff(x), batch_size=batch_size, max_fraction=max_fraction, _allow_detrend=False)
    return d_star * batch_size


def detect_tskip(sim_time, indicators, batch_size=5):
    """t_skip from per-Timestep indicator series; the most conservative (largest) truncation wins."""
    n = len(sim_time)
    indices = {name: mser(list(series)[:n], batch_size=batch_size) for name, series in indicators.items()}
    n_skip = max(indices.values(), default=0)
    dominating = max(indices, key=indices.get) if indices else ""
    if n_skip <= 0 or n == 0:
        return TransientResult(0.0, 0, indices, dominating)
    n_skip = min(n_skip, n)
    return TransientResult(float(sim_time[n_skip - 1]), n_skip, indices, dominating)

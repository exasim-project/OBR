"""Automatic detection of the initial transient (t_skip) from solver-log statistics.

Implements the MSER-5 rule (Marginal Standard Error Rule, White 1997), the
standard warm-up truncation rule from discrete-event simulation: pick the
truncation point that minimises the standard error of the mean of the remaining
data. It is applied to per-timestep indicator series extracted from the log
(first p initial residual per step, pressure solver iterations per step, PIMPLE
outer correctors per step).

Note: this detects when the *numerical effort* settles, which happens earlier
than statistical stationarity of physical quantities (e.g. force coefficients).
It is the right cutoff for averaging solver statistics, but only a lower bound
for a t_skip used to average physical quantities.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class TransientResult:
    t_skip: float                # value for the existing `simTime > t_skip` cutoff
    n_skip: int                  # number of leading timesteps that cutoff drops
    indicator_indices: dict      # per-indicator truncation index (in timesteps)
    dominating_indicator: str    # indicator that produced the final (max) index


def mser(series, batch_size=5, max_fraction=0.5, _allow_detrend=True):
    """Return the MSER truncation index, in samples of the original series.

    MSER(d) = var(X[d:]) / (n - d); the returned index minimises it, i.e. leading
    samples are dropped as long as that reduces the standard error of the mean of
    the remaining data. The series is reduced to non-overlapping batch means of
    `batch_size` first (MSER-5) to smooth per-step noise, and the search is
    limited to the first `max_fraction` of the batches (the standard guard
    against end-of-series artifacts).

    If the minimum lands on that search boundary the series is trend-dominated
    (truncating ever more keeps "improving" the standard error, e.g. residuals
    that keep creeping down over the whole run) and the raw MSER index is an
    artifact. In that case MSER is re-run once on the increments of the series,
    which removes the trend but keeps the initial spike.
    """
    x = np.asarray(series, dtype=float)
    finite = np.isfinite(x)
    if x.size == 0 or not finite.any():
        return 0
    # Occasional missing samples (e.g. an interrupted step) are patched with the
    # series median so indices keep their timestep alignment.
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
    mser_values = [
        np.var(batch_means[d:]) / (n_batches - d) for d in range(d_max + 1)
    ]
    d_star = int(np.argmin(mser_values))
    if d_star == d_max and _allow_detrend:
        return mser(
            np.diff(x), batch_size=batch_size, max_fraction=max_fraction,
            _allow_detrend=False,
        )
    return d_star * batch_size


def detect_tskip(sim_time, indicators, batch_size=5):
    """Estimate t_skip from per-timestep indicator series.

    `indicators` maps an indicator name to its per-timestep series (aligned with
    `sim_time`). Each indicator is truncated with MSER independently and the
    maximum (most conservative) truncation wins. The returned t_skip is chosen
    such that the existing `simTime > t_skip` cutoff drops exactly `n_skip`
    timesteps.
    """
    n = len(sim_time)
    indices = {
        name: mser(list(series)[:n], batch_size=batch_size)
        for name, series in indicators.items()
    }
    n_skip = max(indices.values(), default=0)
    dominating = max(indices, key=indices.get) if indices else ""
    if n_skip <= 0 or n == 0:
        return TransientResult(0.0, 0, indices, dominating)
    n_skip = min(n_skip, n)
    return TransientResult(float(sim_time[n_skip - 1]), n_skip, indices, dominating)


def transient_report(n_skip, quantities):
    """Format a bias/overhead report for the dropped initial transient.

    `quantities` maps a display name to its *full-run* per-timestep series. For
    each one, the full-run mean is compared against the steady mean (first
    `n_skip` samples dropped), and the excess accumulated during the transient
    (sum of transient samples above the steady mean) is given absolutely and as
    a share of the run total.
    """
    lines = [f"Initial-transient report ({n_skip} leading timesteps dropped):"]
    for name, series in quantities.items():
        x = np.asarray(series, dtype=float)
        if n_skip <= 0 or x.size <= n_skip or not np.isfinite(x).any():
            continue
        full_mean = np.nanmean(x)
        steady_mean = np.nanmean(x[n_skip:])
        bias_pct = (
            100.0 * (full_mean - steady_mean) / steady_mean
            if steady_mean != 0 else float("nan")
        )
        excess = np.nansum(x[:n_skip] - steady_mean)
        total = np.nansum(x)
        excess_pct = 100.0 * excess / total if total != 0 else float("nan")
        lines.append(
            f"  {name}: mean {full_mean:.4g} (full run) vs {steady_mean:.4g} (steady), "
            f"bias {bias_pct:+.2f}%; transient excess {excess:+.4g} "
            f"({excess_pct:+.2f}% of run total); "
            f"std {np.nanstd(x[:n_skip]):.3g} (transient) vs {np.nanstd(x[n_skip:]):.3g} (steady)"
        )
    if len(lines) == 1:
        lines.append("  no transient dropped or series too short - nothing to report")
    return "\n".join(lines)

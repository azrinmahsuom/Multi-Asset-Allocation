"""Resampling tools: i.i.d. bootstrap and variance ratios.

All randomness flows through a numpy Generator seeded from config.RANDOM_SEED.
"""

import numpy as np

from analysis.config import BOOTSTRAP_REPS, RANDOM_SEED


def rng(seed: int = RANDOM_SEED) -> np.random.Generator:
    return np.random.default_rng(seed)


def variance_ratio(log_returns: np.ndarray, k: int) -> float:
    """Var of overlapping k-period log returns / (k * var of 1-period log returns).

    1 under i.i.d. returns; below 1 means mean reversion, above 1 means momentum. Missing
    values must be removed first.
    """
    x = np.asarray(log_returns, dtype=float)
    sums = np.convolve(x, np.ones(k), mode="valid")
    return float(np.var(sums, ddof=1) / (k * np.var(x, ddof=1)))


def iid_variance_ratios(
    log_returns: np.ndarray,
    horizons: list[int],
    reps: int = BOOTSTRAP_REPS,
    seed: int = RANDOM_SEED,
) -> np.ndarray:
    """Variance ratios of `reps` i.i.d. resamples (same length, with replacement).

    Returns an array of shape (reps, len(horizons)): the distribution of variance ratios
    expected if returns had no time dependence, including small-sample bias of overlapping
    windows.
    """
    x = np.asarray(log_returns, dtype=float)
    generator = rng(seed)
    out = np.empty((reps, len(horizons)))
    for i in range(reps):
        sample = generator.choice(x, size=len(x), replace=True)
        out[i] = [variance_ratio(sample, k) for k in horizons]
    return out

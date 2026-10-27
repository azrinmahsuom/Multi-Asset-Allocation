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


def block_length(n: int) -> int:
    """Rule-of-thumb block length for a moving-block bootstrap: n^(1/3), at least 1."""
    return max(1, round(n ** (1 / 3)))


def moving_block_indices(n: int, block: int, generator: np.random.Generator) -> np.ndarray:
    """Indices for one moving-block resample: random blocks of consecutive periods, joined
    and cut to length n. block = 1 is the ordinary i.i.d. bootstrap."""
    starts = generator.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return (starts[:, None] + np.arange(block)).ravel()[:n]


def correlation_ci(
    x: np.ndarray,
    y: np.ndarray,
    block: int | None = None,
    reps: int = BOOTSTRAP_REPS,
    level: float = 0.95,
    seed: int = RANDOM_SEED,
) -> tuple[float, float]:
    """Percentile confidence interval for corr(x, y) from a moving-block bootstrap.

    Pairs are resampled together. block defaults to block_length(n).
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    n = len(x)
    block = block or block_length(n)
    generator = rng(seed)
    stats = np.empty(reps)
    for i in range(reps):
        idx = moving_block_indices(n, block, generator)
        stats[i] = np.corrcoef(x[idx], y[idx])[0, 1]
    tail = (1 - level) / 2 * 100
    return float(np.percentile(stats, tail)), float(np.percentile(stats, 100 - tail))

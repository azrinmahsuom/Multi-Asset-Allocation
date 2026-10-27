"""Covariance and mean estimators and long-only portfolio optimisers.

- ledoit_wolf: shrinks the sample covariance towards a scaled identity matrix with the
  intensity of Ledoit and Wolf (2004, Journal of Multivariate Analysis 88(2)).
- bayes_stein_means: shrinks sample means towards the minimum-variance portfolio's mean
  (Jorion 1986, Journal of Financial and Quantitative Analysis 21(3)).
- min_variance, max_sharpe, risk_parity: long-only, fully invested (weights sum to 1).
"""

import numpy as np
from scipy.optimize import minimize


def ledoit_wolf(returns: np.ndarray) -> tuple[np.ndarray, float]:
    """Shrunk covariance and the shrinkage intensity (0 = sample, 1 = target)."""
    x = np.asarray(returns, dtype=float)
    t, n = x.shape
    x = x - x.mean(axis=0)
    sample = x.T @ x / t
    mu = np.trace(sample) / n
    target = mu * np.eye(n)
    d2 = np.sum((sample - target) ** 2) / n
    b2_bar = sum(np.sum((np.outer(row, row) - sample) ** 2) for row in x) / (t**2 * n)
    b2 = min(b2_bar, d2)
    intensity = b2 / d2 if d2 > 0 else 1.0
    return intensity * target + (1 - intensity) * sample, float(intensity)


def _solve(objective, n: int) -> np.ndarray:
    result = minimize(
        objective,
        np.full(n, 1 / n),
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n,
        constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not result.success:
        raise RuntimeError(f"Optimiser failed: {result.message}")
    w = np.clip(result.x, 0, None)
    return w / w.sum()


def min_variance(cov: np.ndarray) -> np.ndarray:
    return _solve(lambda w: w @ cov @ w, len(cov))


def max_sharpe(means: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Weights maximising (w'means) / sqrt(w'cov w); means are excess returns."""
    return _solve(lambda w: -(w @ means) / np.sqrt(w @ cov @ w), len(cov))


def risk_parity(cov: np.ndarray) -> np.ndarray:
    """Equal risk contributions w_i (cov w)_i across assets."""

    def objective(w):
        contrib = w * (cov @ w)
        return np.sum((contrib[:, None] - contrib[None, :]) ** 2)

    return _solve(objective, len(cov))


def bayes_stein_means(returns: np.ndarray, cov: np.ndarray) -> tuple[np.ndarray, float]:
    """Means shrunk towards the minimum-variance portfolio's mean; returns (means, weight)."""
    x = np.asarray(returns, dtype=float)
    t, n = x.shape
    mu = x.mean(axis=0)
    inv = np.linalg.inv(cov)
    ones = np.ones(n)
    w_mv = inv @ ones / (ones @ inv @ ones)
    mu0 = float(w_mv @ mu)
    diff = mu - mu0
    weight = (n + 2) / ((n + 2) + t * diff @ inv @ diff)
    return (1 - weight) * mu + weight * mu0, float(weight)

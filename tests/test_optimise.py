import numpy as np
import pytest

from analysis import optimise


def test_min_variance_two_uncorrelated_assets():
    # Uncorrelated variances 1 and 4: weights proportional to 1/var -> 0.8 / 0.2.
    cov = np.diag([1.0, 4.0])
    assert optimise.min_variance(cov) == pytest.approx([0.8, 0.2], abs=1e-6)


def test_risk_parity_equalises_contributions():
    cov = np.array([[0.04, 0.006], [0.006, 0.01]])
    w = optimise.risk_parity(cov)
    contrib = w * (cov @ w)
    assert contrib[0] == pytest.approx(contrib[1], rel=1e-4)


def test_max_sharpe_two_uncorrelated_assets():
    # Uncorrelated: tangency weights proportional to mean / variance = 0.1/0.04, 0.05/0.01.
    cov = np.diag([0.04, 0.01])
    w = optimise.max_sharpe(np.array([0.1, 0.05]), cov)
    expected = np.array([2.5, 5.0]) / 7.5
    assert w == pytest.approx(expected, abs=1e-4)


def test_ledoit_wolf_is_between_sample_and_target():
    x = np.random.default_rng(0).normal(size=(60, 4))
    shrunk, intensity = optimise.ledoit_wolf(x)
    assert 0 <= intensity <= 1
    assert np.all(np.linalg.eigvalsh(shrunk) > 0)


def test_bayes_stein_means_shrink_towards_common_value():
    x = np.random.default_rng(1).normal(loc=[0.01, 0.02, 0.03], scale=0.05, size=(40, 3))
    cov = np.cov(x, rowvar=False)
    means, weight = optimise.bayes_stein_means(x, cov)
    assert 0 < weight < 1
    assert np.ptp(means) < np.ptp(x.mean(axis=0))

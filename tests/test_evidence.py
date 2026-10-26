import matplotlib.pyplot as plt
import pytest

from analysis import charts
from analysis.evidence import FAILS, HOLDS, NOT_TESTABLE, PARTIAL, verdict_from_share


@pytest.mark.parametrize(
    ("n_true", "n_total", "expected"),
    [(16, 16, HOLDS), (15, 16, PARTIAL), (9, 16, PARTIAL), (8, 16, FAILS), (0, 0, NOT_TESTABLE)],
)
def test_verdict_from_share(n_true, n_total, expected):
    assert verdict_from_share(n_true, n_total) == expected


def test_save_refuses_private_sources(tmp_path):
    fig, _ = plt.subplots()
    with pytest.raises(PermissionError):
        charts.save(fig, "x", "Source: test", {"nareit", "jst"})
    plt.close(fig)


def test_variance_ratio_by_hand():
    from analysis import bootstrap

    # Alternating +1/-1: 2-period sums are all 0, so VR(2) = 0 (perfect mean reversion).
    assert bootstrap.variance_ratio([1.0, -1.0, 1.0, -1.0, 1.0], 2) == 0.0
    # Constant trend +1,+1,+1,... has zero variance; use 1,2,3,4: 2-sums 3,5,7 (var 4),
    # 1-period var 5/3 -> VR(2) = 4 / (2 * 5/3) = 1.2.
    assert bootstrap.variance_ratio([1.0, 2.0, 3.0, 4.0], 2) == pytest.approx(1.2)


def test_iid_variance_ratios_is_reproducible():
    import numpy as np

    from analysis import bootstrap

    x = np.random.default_rng(0).normal(size=200)
    a = bootstrap.iid_variance_ratios(x, [2, 5], reps=20, seed=1)
    b = bootstrap.iid_variance_ratios(x, [2, 5], reps=20, seed=1)
    assert a.shape == (20, 2) and np.array_equal(a, b)

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


def test_moving_block_indices_are_consecutive_runs():
    import numpy as np

    from analysis import bootstrap

    idx = bootstrap.moving_block_indices(10, 3, np.random.default_rng(0))
    assert len(idx) == 10
    # Within each block of 3, indices step by 1.
    for start in range(0, 9, 3):
        block = idx[start : start + 3]
        assert all(np.diff(block) == 1)


def test_correlation_ci_brackets_a_strong_correlation():
    import numpy as np

    from analysis import bootstrap

    x = np.random.default_rng(1).normal(size=300)
    y = x + 0.3 * np.random.default_rng(2).normal(size=300)
    lo, hi = bootstrap.correlation_ci(x, y, reps=300)
    assert lo < np.corrcoef(x, y)[0, 1] < hi and lo > 0.8


def test_block_length_rule():
    from analysis import bootstrap

    # 32^(1/5) = 2 exactly; 243^(1/5) = 3.
    assert bootstrap.block_length(32) == 2 and bootstrap.block_length(243) == 3
    assert bootstrap.block_length(1) == 1


def test_dollar_weighted_return_equals_time_weighted_for_constant_returns():
    import numpy as np

    from analysis.evidence import claim13_behaviour_gap as c13

    r = np.full(24, 0.01)
    assert c13.dollar_weighted_return(r) == pytest.approx(1.01**12 - 1)

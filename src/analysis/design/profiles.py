"""Horizon profiles and their risk-capacity limits, set by the owner on 2026-10-27 (short
profile loosened from -10% to -15% the same day; see docs/decisions.md).

Limits are tested on real SGD monthly returns from February 1998 (owner decision,
2026-10-27); JST worst-country results are reported as stress scenarios.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    horizon: str
    purpose: str
    window_years: int
    worst_window_floor: float  # worst rolling real return over window_years
    floor_is_annualised: bool
    max_drawdown_cap: float | None = None


PROFILES = [
    Profile("Short", "about 5 years", "a known spend at a set date", 5, -0.15, False),
    Profile(
        "Medium", "about 10 years", "a flexible goal that could wait a few years", 10, -0.20, False
    ),
    Profile(
        "Long", "20+ years", "wealth building with no planned withdrawals", 20, 0.0, True, -0.35
    ),
]


def describe(p: Profile) -> str:
    floor = (
        f"at least {p.worst_window_floor:.0%} a year"
        if p.floor_is_annualised
        else f"no worse than {p.worst_window_floor:.0%} cumulative"
    )
    text = f"Worst real SGD return over any {p.window_years}-year period: {floor}"
    if p.max_drawdown_cap is not None:
        text += f"; peak-to-trough fall no worse than {p.max_drawdown_cap:.0%}"
    return text

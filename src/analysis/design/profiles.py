"""Horizon profiles and their risk-capacity limits, set by the owner on 2026-10-27.

Limits are tested on all 16 JST countries (annual, real, local currency); the long profile's
drawdown cap is also checked on the monthly SGD backtest, and the worse of the two applies.
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
    Profile("Short", "about 5 years", "a known spend at a set date", 5, -0.10, False),
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
    text = f"Worst real return over any {p.window_years}-year period, in any country: {floor}"
    if p.max_drawdown_cap is not None:
        text += f"; peak-to-trough fall no worse than {p.max_drawdown_cap:.0%}"
    return text

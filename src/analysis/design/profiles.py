"""Horizon profiles and their risk-capacity limits.

v2 (owner-approved 2026-10-27, set after the v1 holdout; see docs/decisions.md): every measure
uses real SGD returns over rolling windows of the profile's horizon. Limits loosen with
horizon in cumulative terms (the per-year floors tighten, which the owner accepted).
v1 limits are kept for the record of the v1 finding.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    horizon: str
    purpose: str
    window_years: int
    worst_window_floor: float  # worst rolling real return over the window
    floor_is_annualised: bool
    max_drawdown_cap: float | None = None
    loss_probability_max: float | None = None  # share of windows with a real loss


PROFILES = [
    Profile("Short", "about 5 years", "a known spend at a set date", 5, -0.15, False, -0.20, 0.10),
    Profile(
        "Medium",
        "about 10 years",
        "a flexible goal that could wait a few years",
        10,
        -0.20,
        False,
        None,
        0.15,
    ),
    Profile(
        "Long",
        "20+ years",
        "wealth building with no planned withdrawals",
        20,
        -0.25,
        False,
        None,
        0.20,
    ),
]

PROFILES_V1 = [
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
    parts = [f"worst real SGD return over any {p.window_years}-year period {floor}"]
    if p.loss_probability_max is not None:
        parts.append(
            f"real loss in at most {p.loss_probability_max:.0%} of {p.window_years}-year periods"
        )
    if p.max_drawdown_cap is not None:
        parts.append(f"peak-to-trough fall no worse than {p.max_drawdown_cap:.0%}")
    text = "; ".join(parts)
    return text[0].upper() + text[1:]

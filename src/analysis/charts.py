"""Shared chart style and the only place figures are saved.

save() enforces two rules: every figure has a source line, and no figure may be built from
a source whose terms forbid public display (see PRIVATE_SOURCES).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from analysis.config import FIGURES  # noqa: E402

# Reference palette, light mode, in its fixed categorical order (validated: first three
# slots pass all-pairs colour-vision checks, so dot and scatter charts use at most three).
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

# Sources that may be analysed privately but never shown in a published figure.
PRIVATE_SOURCES = {"nareit"}

WIDTH_IN, DPI = 8.0, 150  # 1200 px wide


def style() -> None:
    """Apply the house style to matplotlib."""
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.edgecolor": GRID,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "text.color": TEXT,
            "legend.frameon": False,
            "lines.linewidth": 2,
        }
    )


def figure(height_in: float = 5.0) -> tuple[plt.Figure, plt.Axes]:
    style()
    return plt.subplots(figsize=(WIDTH_IN, height_in))


def titles(fig: plt.Figure, title: str, subtitle: str) -> None:
    """Title (the takeaway) and subtitle (what is plotted), aligned to the figure's left edge.

    Titles over 80 characters and subtitles over 108 don't fit the 1200 px width and are
    rejected.
    """
    if len(title) > 80:
        raise ValueError(f"Title too long for the figure ({len(title)} > 80): {title!r}")
    if len(subtitle) > 108:
        raise ValueError(f"Subtitle too long ({len(subtitle)} > 108): {subtitle!r}")
    fig.text(0.01, 0.975, title, fontsize=12, fontweight="bold", color=TEXT, va="top")
    fig.text(0.01, 0.935, subtitle, fontsize=9, color=TEXT_SECONDARY, va="top")


def save(fig: plt.Figure, name: str, source_line: str, sources: set[str]) -> Path:
    """Add the source line and save to reports/figures/<name>.png.

    sources lists the raw-data folders the figure was built from; any private one raises.
    """
    private = sources & PRIVATE_SOURCES
    if private:
        raise PermissionError(
            f"Figure {name!r} uses {sorted(private)}, which may not be published."
        )
    fig.text(
        0.01,
        0.01,
        source_line,
        fontsize=7.5,
        color=TEXT_SECONDARY,
        ha="left",
        va="bottom",
        wrap=True,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.91))
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"{name}.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path

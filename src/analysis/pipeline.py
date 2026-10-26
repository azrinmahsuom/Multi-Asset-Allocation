"""End-to-end run: load -> clean -> analyse -> save figures.

Run with: uv run python -m analysis.pipeline
"""

from analysis.config import FIGURES


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    # 1. Load:    prices = data.load_prices()
    # 2. Clean:   ...
    # 3. Analyse: rets = metrics.simple_returns(prices)
    # 4. Report:  save charts to FIGURES, print summary table
    print("Pipeline skeleton ran. Fill in the steps for this project.")


if __name__ == "__main__":
    main()

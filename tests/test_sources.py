import re

import pandas as pd
import pytest

from analysis import sources

# Shape of the MAS CSV: title lines, a repeated header, blank year/month after their first
# row, then a second table whose dates restart.
MAS_SAMPLE = """MAS: Financial Database - Domestic Interest Rates

End of Period / SORA Value Date,,,Interbank Overnight,Interbank 3-Month,SORA
1987,Jul,01,2.75,4.31,-
,,02,7.00,4.38,-
,Aug,01,3.50,4.19,-
End of Period / SORA Value Date,,,Interbank Overnight,Interbank 3-Month,SORA
1988,Jan,04,1.00,2.00,-

SORA Value Date,,,SORA Publication Date,SORA,SORA Index,Compound SORA - 3 month
1987,Jul,01,-,-,-,-
"""


def test_mas_first_table_parses_dates_and_stops_at_second_table(tmp_path):
    path = tmp_path / "mas.csv"
    path.write_text(MAS_SAMPLE)
    rows = sources.mas_first_table(path)
    assert [d for d, _ in rows] == list(
        pd.to_datetime(["1987-07-01", "1987-07-02", "1987-08-01", "1988-01-04"])
    )
    assert rows[1][1] == ["7.00", "4.38", "-"]


def test_missing_manual_file_fails_naming_the_url(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "DATA_RAW", tmp_path)
    raw = next(r for r in sources.REGISTRY if r.manual)
    with pytest.raises(FileNotFoundError, match=re.escape(raw.resolve_url())):
        sources.fetch(raw)


def test_registry_paths_are_unique():
    keys = [raw.path for raw in sources.REGISTRY]
    assert len(keys) == len(set(keys))

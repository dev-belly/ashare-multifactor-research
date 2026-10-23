"""Persisted factor panels must retain their format and identifiers."""

import pandas as pd
import pytest

from factorlab.factors.engineering import load_factor_panel, save_factor_panel


def _factor_panel():
    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2024-01-02"), "000001"), (pd.Timestamp("2024-01-03"), "600000")],
        names=["date", "code"],
    )
    return pd.DataFrame({"mom_1m": [0.1, 0.2]}, index=index)


@pytest.mark.parametrize("as_path", [False, True])
def test_csv_round_trip_preserves_leading_zero_security_codes(tmp_path, as_path):
    path = tmp_path / "factors.csv"
    argument = path if as_path else str(path)
    save_factor_panel(_factor_panel(), argument)

    pd.testing.assert_frame_equal(load_factor_panel(argument), _factor_panel())


def test_unavailable_parquet_engine_does_not_write_disguised_csv(tmp_path, monkeypatch):
    path = tmp_path / "factors.parquet"

    def unavailable(*args, **kwargs):
        raise ImportError("parquet engine unavailable")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", unavailable)
    with pytest.raises(ImportError, match="parquet engine"):
        save_factor_panel(_factor_panel(), path)
    assert not path.exists()

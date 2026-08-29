import numpy as np
import pandas as pd
import pytest

from factorlab.data.processor import forward_returns
from factorlab.pipeline import (
    _forward_compound_return,
    _forward_return_panel,
    _purge_training_label_overlap,
    _returns_to_nav,
)


def _realized_return_panel() -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=4, freq="B")
    index = pd.MultiIndex.from_product(
        [dates, ["000001.SZ", "600000.SH"]], names=["date", "code"]
    )
    # Values on the first date are deliberately extreme: a forward label at
    # that date must only use the following dates, never the current return.
    values = [9.0, -0.9, 0.10, -0.10, 0.20, -0.20, 0.30, -0.30]
    return pd.DataFrame({"ret_1d": values}, index=index).sample(
        frac=1.0, random_state=7
    )


def test_forward_one_day_return_is_shifted_inside_each_symbol() -> None:
    realized = _realized_return_panel()
    forward = _forward_return_panel(realized)
    dates = sorted(realized.index.get_level_values("date").unique())

    assert forward.loc[(dates[0], "000001.SZ"), "ret_1d"] == 0.10
    assert forward.loc[(dates[0], "600000.SH"), "ret_1d"] == -0.10
    assert forward.loc[(dates[2], "000001.SZ"), "ret_1d"] == 0.30
    assert forward.loc[(dates[2], "600000.SH"), "ret_1d"] == -0.30
    assert np.isnan(forward.loc[(dates[-1], "000001.SZ"), "ret_1d"])
    assert np.isnan(forward.loc[(dates[-1], "600000.SH"), "ret_1d"])


def test_forward_compound_label_never_crosses_symbol_boundaries() -> None:
    realized = _realized_return_panel()["ret_1d"]
    forward = _forward_compound_return(realized, horizon=2)
    dates = sorted(realized.index.get_level_values("date").unique())

    # T+1 and T+2 only: (1.10 * 1.20) - 1 and (0.90 * 0.80) - 1.
    assert np.isclose(forward.loc[(dates[0], "000001.SZ")], 0.32)
    assert np.isclose(forward.loc[(dates[0], "600000.SH")], -0.28)
    # The next label uses returns on dates 3 and 4, still inside each symbol.
    assert np.isclose(forward.loc[(dates[1], "000001.SZ")], 0.56)
    assert np.isclose(forward.loc[(dates[1], "600000.SH")], -0.44)
    for code in ("000001.SZ", "600000.SH"):
        assert np.isnan(forward.loc[(dates[2], code)])
        assert np.isnan(forward.loc[(dates[3], code)])


def test_training_labels_are_purged_before_oos_fold() -> None:
    dates = pd.bdate_range("2024-01-02", periods=50)
    index = pd.MultiIndex.from_product(
        [dates[:40], ["000001.SZ", "600000.SH"]],
        names=["date", "code"],
    )

    kept = _purge_training_label_overlap(
        index,
        dates,
        test_start=dates[40],
        horizon=21,
    )

    # T+21 must still be strictly before the first OOS trading date. The
    # observation at dates[19] would end exactly on dates[40] and is excluded.
    assert kept.get_level_values("date").max() == dates[18]
    assert len(kept) == 19 * 2


def test_public_forward_return_helper_uses_full_requested_horizon() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4)
    quotes = {"A": pd.DataFrame({"close": [100.0, 110.0, 121.0, 133.1]}, index=dates)}

    result = forward_returns(quotes, horizon=2)["A"]

    assert result.iloc[0] == pytest.approx(0.21)
    assert result.iloc[1] == pytest.approx(0.21)
    assert result.iloc[2:].isna().all()


def test_return_compounding_preserves_the_first_observation() -> None:
    returns = pd.Series(
        [0.10, -0.05],
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    nav = _returns_to_nav(returns)

    assert nav.iloc[0] == 1.0
    assert nav.iloc[1] == pytest.approx(1.10)
    assert nav.iloc[2] == pytest.approx(1.045)

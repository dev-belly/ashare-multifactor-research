"""分层组合测试：分组标签、等权收益、多空价差。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factorlab.models.sort_portfolio import SortPortfolio


def _panels(n_dates: int = 30, n_codes: int = 20, seed: int = 1):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates)
    codes = [f"S{i:02d}" for i in range(n_codes)]
    idx = pd.MultiIndex.from_product([dates, codes], names=["date", "code"])
    factor = rng.normal(size=len(idx))
    # 收益与因子正相关 → G5 应显著跑赢 G1
    ret = 0.02 * factor + rng.normal(scale=0.002, size=len(idx))
    factor_df = pd.DataFrame({"mom": factor}, index=idx)
    ret_df = pd.DataFrame({"ret_1d": ret}, index=idx)
    return factor_df, ret_df


def test_assign_produces_labels_1_to_n():
    f, _ = _panels()
    labels = SortPortfolio(n_groups=5).assign(f, "mom")["group"]
    assert set(labels.unique()) == {1, 2, 3, 4, 5}
    counts = labels.groupby(level="date").value_counts()
    assert counts.groupby(level="date").nunique().eq(1).all(), "每个截面上各组应等量"


def test_backtest_high_group_beats_low_group():
    f, r = _panels()
    sp = SortPortfolio(n_groups=5)
    group_ret = sp.backtest(f, r, "mom")

    assert list(group_ret.columns) == ["G1", "G2", "G3", "G4", "G5"]
    assert group_ret["G5"].mean() > group_ret["G1"].mean(), "因子有效时最高组应跑赢最低组"


def test_long_short_spread_matches_manual():
    f, r = _panels()
    sp = SortPortfolio(n_groups=5)
    group_ret = sp.backtest(f, r, "mom")
    spread = sp.long_short_spread(group_ret)

    expected = group_ret["G5"] - group_ret["G1"]
    pd.testing.assert_series_equal(spread, expected, check_names=False)
    assert spread.mean() > 0


def test_backtest_drops_dates_without_returns():
    f, r = _panels()
    first_date = r.index[0][0]
    r = r.copy()
    # 首个交易日全部标的无收益 → 该日应被整体丢弃
    r.loc[first_date, "ret_1d"] = np.nan
    group_ret = SortPortfolio(n_groups=5).backtest(f, r, "mom")
    assert first_date not in group_ret.index

    # 部分缺失只影响当期截面均值，不应改变日期集合
    f2, r2 = _panels()
    r2.loc[r2.index[:5], "ret_1d"] = np.nan
    group_ret2 = SortPortfolio(n_groups=5).backtest(f2, r2, "mom")
    assert group_ret2.index[0] == r2.index[0][0]


def test_long_short_spread_degenerate_with_single_group():
    single = pd.DataFrame({"G1": [0.01, 0.02]}, index=pd.date_range("2020-01-01", periods=2))
    spread = SortPortfolio().long_short_spread(single)
    assert (spread == 0.0).all()

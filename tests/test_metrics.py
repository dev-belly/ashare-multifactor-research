"""评估指标测试：净值统计、最大回撤、IC。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factorlab.evaluation.ic import calc_ic_series, ic_summary
from factorlab.evaluation.returns import max_drawdown, perf_stats
from factorlab.evaluation.turnover import turnover_stats


def test_max_drawdown_on_known_series():
    nav = pd.Series([1.0, 1.2, 0.9, 1.1], index=pd.date_range("2020-01-01", periods=4))
    mdd, peak, trough = max_drawdown(nav)
    # 1.2 -> 0.9，回撤 -25%
    assert abs(mdd - (-0.25)) < 1e-9
    assert peak == nav.index[1]
    assert trough == nav.index[2]


def test_max_drawdown_zero_when_monotonic():
    nav = pd.Series([1.0, 1.1, 1.2], index=pd.date_range("2020-01-01", periods=3))
    mdd, _, _ = max_drawdown(nav)
    assert mdd == 0.0


def test_perf_stats_on_flat_nav():
    nav = pd.Series([1.0] * 252, index=pd.date_range("2020-01-01", periods=252))
    stats = perf_stats(nav)
    assert stats["annual_return"] == 0.0
    assert stats["annual_vol"] == 0.0
    assert stats["max_drawdown"] == 0.0
    assert stats["n_periods"] == 252


def test_perf_stats_positive_drift_has_positive_sharpe():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 504)
    nav = pd.Series(np.cumprod(1 + r), index=pd.date_range("2020-01-01", periods=504))
    stats = perf_stats(nav, rf_annual=0.0)
    assert stats["sharpe"] > 0, "正漂移序列的 Sharpe 应为正"
    assert stats["annual_return"] > 0
    assert stats["max_drawdown"] <= 0


def test_perf_stats_too_short_returns_empty():
    assert perf_stats(pd.Series([1.0])) == {}


def _ic_panel(seed: int = 0, n_dates: int = 60, n_codes: int = 20):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=n_dates)
    codes = [f"S{i:03d}" for i in range(n_codes)]
    idx = pd.MultiIndex.from_product([dates, codes], names=["date", "code"])
    factor = rng.normal(size=len(idx))
    # 让收益与因子正相关，保证 IC 显著为正
    ret = 0.05 * factor + rng.normal(scale=0.01, size=len(idx))
    return pd.DataFrame({"mom": factor, "ret_1d": ret}, index=idx)


def test_calc_ic_series_recovers_positive_signal():
    ic = calc_ic_series(_ic_panel(), "mom", method="pearson")
    assert len(ic) == 60
    assert ic.mean() > 0.9, "构造的强相关信号应得到接近 1 的 IC"


def test_calc_ic_series_spearman_vs_pearson_both_work():
    panel = _ic_panel()
    for method in ("pearson", "spearman"):
        ic = calc_ic_series(panel, "mom", method=method)
        assert ic.notna().all(), f"{method} 不应产生全 NaN"


def test_calc_ic_series_handles_empty():
    empty = pd.DataFrame({"mom": [], "ret_1d": []},
                         index=pd.MultiIndex.from_arrays([[], []], names=["date", "code"]))
    assert calc_ic_series(empty, "mom").empty


def test_ic_summary_keys_and_ir():
    ic = calc_ic_series(_ic_panel(), "mom")
    s = ic_summary(ic)
    assert s["n_periods"] == 60
    assert s["ic_mean"] > 0
    assert set(["n_periods", "ic_mean", "ic_std", "ir", "ic_pos_ratio", "abs_ic_mean"]).issubset(s.keys())
    assert 0.0 <= s["ic_pos_ratio"] <= 1.0


def test_ic_summary_empty_is_safe():
    s = ic_summary(pd.Series(dtype=float))
    assert s["n_periods"] == 0
    assert np.isnan(s["ic_mean"])


def test_turnover_stats_annualization():
    t = pd.Series([0.5, 0.5, 0.5])
    s = turnover_stats(t)
    assert abs(s["avg"] - 0.5) < 1e-9
    # 输入序列按日记录；年化应使用真实样本长度，而不是假设每 21 日调仓。
    assert abs(s["annualized"] - 0.5 * 252) < 1e-9
    assert s["n_rebalances"] == 3


def test_turnover_stats_all_zero():
    s = turnover_stats(pd.Series([0.0, 0.0]))
    assert s["n_rebalances"] == 0
    assert s["avg"] == 0.0

"""因子工程测试：动量因子、截面处理、注册表完整性。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factorlab.factors.base import (
    cross_section_standardize,
    cross_section_winsorize,
    filter_universe,
    industry_neutralize,
)
from factorlab.factors.engineering import default_factor_registry
from factorlab.factors.momentum import Mom1M, Mom12_10, MomentumFactor


def _quotes(n_days: int = 300, codes=("000001.SZ", "000002.SZ", "600000.SH")):
    rng = np.random.default_rng(42)
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    out = {}
    for code in codes:
        r = rng.normal(0.0005, 0.02, n_days)
        close = 10.0 * np.cumprod(1 + r)
        out[code] = pd.DataFrame(
            {
                "open": close * (1 + rng.normal(0, 0.001, n_days)),
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": rng.integers(1e6, 1e7, n_days).astype(float),
            },
            index=dates,
        )
    return out


def test_momentum_factor_output_shape():
    quotes = _quotes()
    factor = Mom1M()
    out = factor.compute(quotes)

    assert list(out.columns) == ["mom_1m"]
    assert isinstance(out.index, pd.MultiIndex)
    assert out.index.names == ["date", "code"]
    assert out["mom_1m"].notna().any()


def test_momentum_lookback_and_skip_are_consistent():
    """Mom1M(21,0) 与手动 shift 计算必须一致。"""
    quotes = _quotes()
    code = "000001.SZ"
    manual = quotes[code]["close"].shift(0) / quotes[code]["close"].shift(21) - 1

    out = MomentumFactor("mom_1m", lookback=21, skip=0).compute(quotes)
    got = out.loc[(slice(None), code), "mom_1m"].droplevel("code")

    aligned = pd.concat([manual.rename("manual"), got.rename("got")], axis=1).dropna()
    assert len(aligned) > 0
    assert np.allclose(aligned["manual"], aligned["got"], atol=1e-12)


def test_mom12_10_skips_recent_month():
    """Carhart MOM：12 个月回看，跳过最近 1 个月（21 个交易日）。"""
    quotes = _quotes()
    code = "000001.SZ"
    close = quotes[code]["close"]
    factor = Mom12_10()
    assert factor.lookback == 252
    assert factor.skip == 21
    manual = close.shift(factor.skip) / close.shift(factor.lookback + factor.skip) - 1

    out = Mom12_10().compute(quotes)
    got = out.loc[(slice(None), code), "mom_12_10"].droplevel("code")
    aligned = pd.concat([manual.rename("manual"), got.rename("got")], axis=1).dropna()
    assert len(aligned) > 0
    assert np.allclose(aligned["manual"], aligned["got"], atol=1e-12)


def test_momentum_skips_frames_without_close():
    out = Mom1M().compute({"X": pd.DataFrame({"volume": [1.0, 2.0]})})
    assert out.empty


def test_default_registry_has_expected_families():
    reg = default_factor_registry()
    assert len(reg) >= 15
    cats = {f.category for f in reg.values()}
    assert {"value", "quality", "momentum", "volatility", "liquidity"} <= cats
    for key, f in reg.items():
        assert f.name == key, f"注册表 key={key} 与因子 name={f.name} 不一致"


def _panel():
    dates = pd.date_range("2020-01-01", periods=10)
    codes = ["A", "B", "C", "D"]
    idx = pd.MultiIndex.from_product([dates, codes], names=["date", "code"])
    rng = np.random.default_rng(7)
    return pd.DataFrame({"f": rng.normal(size=len(idx)), "is_suspended": False}, index=idx)


def test_cross_section_zscore_is_zero_mean():
    out = cross_section_standardize(_panel(), ["f"], method="zscore")
    means = out["f"].groupby(level="date").mean()
    assert np.allclose(means.values, 0.0, atol=1e-9)


def test_cross_section_rank_is_bounded():
    out = cross_section_standardize(_panel(), ["f"], method="rank")
    assert out["f"].min() >= -0.5 - 1e-9 and out["f"].max() <= 0.5 + 1e-9


def test_standardize_unknown_method_raises():
    with pytest.raises(ValueError, match="unknown standardize"):
        cross_section_standardize(_panel(), ["f"], method="nonsense")


def test_winsorize_clips_extremes():
    panel = _panel()
    panel.loc[(panel.index[0][0], "A"), "f"] = 1000.0  # 极端值
    out = cross_section_winsorize(panel, ["f"], lower_q=0.01, upper_q=0.99)
    assert out["f"].max() < 1000.0


def test_filter_universe_nans_out_suspended():
    panel = _panel()
    idx = panel.index
    panel.loc[idx[:4], "is_suspended"] = True
    out = filter_universe(panel, factor_cols=["f"])
    assert out.loc[idx[:4], "f"].isna().all()
    assert out.loc[idx[4:], "f"].notna().all()
    # 元数据列不应被破坏
    assert out["is_suspended"].notna().all()


def test_industry_neutralize_centers_within_industry():
    panel = _panel()
    panel["industry"] = ["tech", "tech", "bank", "bank"] * 10
    out = industry_neutralize(panel, ["f"])
    means = out.groupby(["date", "industry"])["f"].mean()
    assert np.allclose(means.values, 0.0, atol=1e-9)


def test_industry_neutralize_noop_without_industry_column():
    panel = _panel()
    out = industry_neutralize(panel, ["f"])
    pd.testing.assert_frame_equal(out, panel)

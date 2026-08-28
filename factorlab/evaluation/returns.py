"""收益分析：净值、Sharpe、Calmar、年化、最大回撤。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def perf_stats(nav: pd.Series, rf_annual: float = 0.02, periods_per_year: int = 252) -> dict[str, float]:
    """年化收益 / 波动 / Sharpe / 最大回撤 / Calmar。

    Args:
        nav: 净值曲线（基准起点 1.0）。
        rf_annual: 无风险利率（年化）。
        periods_per_year: 一年交易日。
    """
    r = nav.pct_change().fillna(0)
    n = len(r)
    if n < 2:
        return {}
    total = nav.iloc[-1] / nav.iloc[0] - 1
    years = n / periods_per_year
    annual_ret = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    annual_vol = r.std(ddof=1) * np.sqrt(periods_per_year)
    sharpe = (annual_ret - rf_annual) / (annual_vol + 1e-12)
    mdd, peak, trough = max_drawdown(nav)
    calmar = annual_ret / abs(mdd) if mdd < 0 else np.nan
    return {
        "annual_return": float(annual_ret),
        "annual_vol": float(annual_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(mdd),
        "calmar": float(calmar),
        "total_return": float(total),
        "n_periods": int(n),
        "years": float(years),
    }


def max_drawdown(nav: pd.Series) -> tuple[float, pd.Timestamp, pd.Timestamp]:
    """返回最大回撤及对应峰/谷日期。"""
    hwm = nav.cummax()
    dd = nav / hwm - 1
    trough_idx = dd.idxmin()
    if pd.isna(trough_idx):
        return 0.0, pd.NaT, pd.NaT
    peak_idx = nav.loc[:trough_idx].idxmax()
    return float(dd.min()), peak_idx, trough_idx

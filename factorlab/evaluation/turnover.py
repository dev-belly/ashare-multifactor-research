"""换手率分析。"""

from __future__ import annotations

import pandas as pd


def turnover_stats(turnover: pd.Series) -> dict:
    """汇总实际成交权重。

    ``turnover`` 是每日 ``sum(abs(w_new - w_old))``，同时包含买入与卖出。
    年化值直接用样本内成交权重总和除以样本年数，不再假定固定 21 日调仓。
    """
    s = turnover.dropna()
    trades = s[s > 0]
    if trades.empty:
        return {
            "avg": 0.0,
            "median": 0.0,
            "max": 0.0,
            "n_rebalances": 0,
            "annualized": 0.0,
        }
    years = len(s) / 252
    return {
        "avg": float(trades.mean()),
        "median": float(trades.median()),
        "max": float(trades.max()),
        "n_rebalances": int(len(trades)),
        "annualized": float(trades.sum() / years) if years > 0 else 0.0,
    }

"""换手率分析。"""
from __future__ import annotations

import pandas as pd


def turnover_stats(turnover: pd.Series) -> dict:
    s = turnover.dropna()
    s = s[s > 0]
    if s.empty:
        return {"avg": 0.0, "median": 0.0, "max": 0.0, "n_rebalances": 0}
    return {
        "avg": float(s.mean()),
        "median": float(s.median()),
        "max": float(s.max()),
        "n_rebalances": int(len(s)),
        "annualized": float(s.mean() * (252 / 21)),  # 默认按月调仓
    }

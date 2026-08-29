"""交易成本模型：固定基点 + 涨跌停约束 + 停牌约束。"""

from __future__ import annotations

import pandas as pd


def apply_trading_cost(
    weights_old: pd.Series,
    weights_new: pd.Series,
    cost_bps: float = 20.0,
) -> float:
    """计算单次调仓的成本（单边基点）。

    ``cost_bps`` 是单边费率，而绝对权重变化之和已经同时包含买入和
    卖出金额。因此成本为 ``sum(abs(w_new - w_old)) * cost_bps``。

    例如，从 100% A 换到 100% B 的绝对权重变化之和为 2，会分别对
    卖出 A 和买入 B 收取一次单边成本。
    """
    assets = weights_old.index.union(weights_new.index)
    old_aligned = weights_old.reindex(assets).fillna(0.0)
    new_aligned = weights_new.reindex(assets).fillna(0.0)
    delta = (new_aligned - old_aligned).abs().sum()
    return float(delta * cost_bps * 1e-4)  # 转为小数


def is_tradable_today(
    code: str,
    today: pd.Timestamp,
    quotes: dict[str, pd.DataFrame],
    allow_suspended: bool = False,
) -> bool:
    """判断某日某股是否可交易（未停牌/未涨跌停/有成交）。"""
    if code not in quotes:
        return False
    df = quotes[code]
    if today not in df.index:
        return False
    row = df.loc[today]
    if not allow_suspended and bool(row.get("is_suspended", False)):
        return False
    return not bool(row.get("is_limit_up", False))  # 涨停无法买入

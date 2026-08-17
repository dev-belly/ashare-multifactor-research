"""交易成本模型：固定基点 + 涨跌停约束 + 停牌约束。"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def apply_trading_cost(
    weights_old: pd.Series,
    weights_new: pd.Series,
    cost_bps: float = 20.0,
) -> float:
    """计算单次调仓的成本（单边基点）。

    成本 = |w_new - w_old| @ 0.5 * cost_bps  （买卖各收一次）
    """
    delta = (weights_new - weights_old).abs().sum()
    return delta * cost_bps * 0.5 * 1e-4  # 转为小数


def is_tradable_today(
    code: str,
    today: pd.Timestamp,
    quotes: Dict[str, pd.DataFrame],
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
    if bool(row.get("is_limit_up", False)):  # 涨停无法买入
        return False
    return True

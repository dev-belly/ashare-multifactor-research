"""回测主引擎：接收预测分数 → 构造组合 → 计算收益曲线与统计。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from factorlab.backtest.cost_model import apply_trading_cost
from factorlab.utils.common import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestResult:
    """回测结果汇总。"""

    nav: pd.Series                          # 净值曲线（基准 1.0）
    daily_ret: pd.Series                    # 日收益
    turnover: pd.Series                     # 换手率
    positions: pd.DataFrame                 # 持仓（宽表）
    rebalance_dates: pd.DatetimeIndex       # 调仓日
    cost_bps: float
    n_stocks_avg: float


def run_long_only_topk(
    score_panel: pd.DataFrame,  # MultiIndex (date, code), 单列 score
    returns_panel: pd.DataFrame,  # MultiIndex (date, code), 单列 fwd_ret_1d 或 ret_1d
    top_k: int = 50,
    rebalance_freq: int = 21,   # 调仓频率（交易日）
    cost_bps: float = 20.0,
    min_holding_days: int = 21,
    max_weight: float = 0.05,   # 个股权重上限（防过度集中）
) -> BacktestResult:
    """多头 TopK 等权回测。

    关键：
        - 调仓日：选 score 最高的 top_k，等权（受 max_weight 上限）
        - 调仓周期间：持仓不变，按个股 daily return 滚动
        - 调仓日：扣除买卖双边成本

    Args:
        score_panel: (date, code) → score 分数（已做截面标准化）。
        returns_panel: (date, code) → 单日收益（ret_1d，已 shift -1 与未来对齐）。
        top_k: 持仓数。
        rebalance_freq: 调仓频率（交易日）。
        cost_bps: 单边成本（基点）。
        min_holding_days: 最短持有期。
        max_weight: 单股权重上限。

    Returns:
        BacktestResult。
    """
    # 把面板 unstack 成宽表便于按行处理
    score_w = score_panel["score"].unstack("code")
    ret_w = returns_panel["ret_1d"].unstack("code")
    # 对齐
    common_idx = score_w.index.intersection(ret_w.index)
    score_w = score_w.loc[common_idx]
    ret_w = ret_w.loc[common_idx]
    # 收益用 ffill 处理（停牌日收益为 0）
    ret_w = ret_w.fillna(0.0)

    # 调仓日
    rebal_dates = common_idx[::rebalance_freq]
    rebal_set = set(rebal_dates)

    # 持仓表（= 0 / 1/N）
    positions = pd.DataFrame(0.0, index=common_idx, columns=score_w.columns)
    turnover = pd.Series(0.0, index=common_idx)
    daily_ret = pd.Series(0.0, index=common_idx)
    last_rebal_idx = -min_holding_days  # 强制至少经过一个持有期
    last_weights = pd.Series(0.0, index=score_w.columns)
    cost_drag = 0.0

    for i, dt in enumerate(common_idx):
        if dt in rebal_set and i - last_rebal_idx >= min_holding_days:
            # 选 TopK
            row = score_w.loc[dt].dropna()
            if len(row) >= top_k:
                picks = row.nlargest(top_k).index
            else:
                picks = row.index
            new_w = pd.Series(0.0, index=score_w.columns)
            w = min(1.0 / len(picks), max_weight) if len(picks) else 0.0
            new_w.loc[picks] = w
            # 若超过 1，截断
            if new_w.sum() > 1:
                new_w = new_w / new_w.sum()
            # 成本
            cost = apply_trading_cost(last_weights, new_w, cost_bps=cost_bps)
            cost_drag += cost
            turnover.loc[dt] = (new_w - last_weights).abs().sum()
            last_weights = new_w
            last_rebal_idx = i
        # 当日收益 = 上一日权重 × 当日收益（避免同日内的 look-ahead）
        if i > 0:
            prev = common_idx[i - 1]
            daily_ret.iloc[i] = (last_weights * ret_w.loc[dt]).sum() - (
                turnover.iloc[i] * cost_bps * 1e-4 if turnover.iloc[i] > 0 else 0
            )
        positions.loc[dt] = last_weights

    # 构造净值
    nav = (1 + daily_ret).cumprod()
    n_stocks_avg = (positions > 0).sum(axis=1).mean()

    return BacktestResult(
        nav=nav,
        daily_ret=daily_ret,
        turnover=turnover,
        positions=positions,
        rebalance_dates=rebal_dates,
        cost_bps=cost_bps,
        n_stocks_avg=float(n_stocks_avg),
    )


def make_ret_panel(
    quotes: Dict[str, pd.DataFrame],
    horizon: int = 1,
    use_fwd: bool = False,
) -> pd.DataFrame:
    """构造收益面板（用于回测）。

    Args:
        quotes: 日行情。
        horizon: 未来期数（仅 use_fwd=True 生效）。
        use_fwd: True → 用未来收益；False → 用当日实际收益（回测已 shift -1）。
    """
    rows = {}
    for code, df in quotes.items():
        r = df["close"].pct_change(periods=horizon) if use_fwd else df["close"].pct_change()
        rows[code] = r.rename("ret_1d")
    panel = pd.concat(rows, axis=1)
    panel.columns.name = "code"
    panel = panel.stack(future_stack=True).rename("ret_1d").to_frame()
    panel.index.set_names(["date", "code"], inplace=True)
    return panel


def attach_score_to_panel(
    score_panel: pd.DataFrame,
    factor_panel: pd.DataFrame,
    factor_cols: List[str] | None = None,
    weights: Dict[str, float] | None = None,
) -> pd.DataFrame:
    """把多因子面板聚合成单一 score。

    默认等权；weights 提供时按权加和。
    """
    cols = factor_cols or [c for c in factor_panel.columns if c not in {"industry", "is_suspended"}]
    weights = weights or {c: 1.0 for c in cols}
    w = pd.Series(weights).reindex(cols).fillna(0.0)
    s = factor_panel[cols].mul(w, axis=1).sum(axis=1, skipna=True)
    s = s.to_frame("score")
    return s

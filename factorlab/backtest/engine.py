"""回测主引擎：接收预测分数 → 构造组合 → 计算收益曲线与统计。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from factorlab.backtest.cost_model import apply_trading_cost
from factorlab.utils.common import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_WEIGHT = 0.05


@dataclass
class BacktestResult:
    """回测结果汇总。"""

    nav: pd.Series  # 净值曲线（基准 1.0）
    daily_ret: pd.Series  # 日收益
    turnover: pd.Series  # 实际换仓日的双边总交易权重
    positions: pd.DataFrame  # 当日收益所使用的持仓（宽表）
    rebalance_dates: pd.DatetimeIndex  # 目标权重实际生效的日期
    cost_bps: float
    n_stocks_avg: float


def run_long_only_topk(
    score_panel: pd.DataFrame,  # MultiIndex (date, code), 单列 score
    returns_panel: pd.DataFrame,  # MultiIndex (date, code), 单列实际 ret_1d
    top_k: int = 50,
    rebalance_freq: int = 21,  # 调仓频率（交易日）
    cost_bps: float = 20.0,
    min_holding_days: int = 21,
    max_weight: float = DEFAULT_MAX_WEIGHT,  # 个股权重上限（防过度集中）
) -> BacktestResult:
    """多头 TopK 等权回测。

    关键：
        - 信号日：选 score 最高的 top_k，等权且保持满仓
        - 如果可选股票数不足以在 max_weight 约束下满仓，则明确失败
        - 信号生成后的下一交易日收盘执行换仓，随后才让目标权重承担收益
        - 调仓周期间：持仓不变，按个股 daily return 滚动
        - 实际换仓生效日：扣除买卖双边成本

    Args:
        score_panel: (date, code) → score 分数（已做截面标准化）。
        returns_panel: (date, code) → 当日实际单日收益（ret_1d，不能预先向未来 shift）。
        top_k: 持仓数。
        rebalance_freq: 调仓频率（交易日）。
        cost_bps: 单边成本（基点）。
        min_holding_days: 最短持有期。
        max_weight: 单股权重上限；不会通过保留未披露现金来满足约束。

    Returns:
        BacktestResult。
    """
    if top_k <= 0 or rebalance_freq <= 0 or min_holding_days < 0:
        raise ValueError("top_k/rebalance_freq 必须为正数，min_holding_days 不能为负")
    if not 0 < max_weight <= 1:
        raise ValueError("max_weight 必须在 (0, 1] 区间")
    if top_k * max_weight < 1.0 - 1e-12:
        min_top_k = int(1.0 / max_weight + 1.0 - 1e-12)
        raise ValueError(
            "top_k 与 max_weight 无法组成满仓组合："
            f"top_k={top_k}, max_weight={max_weight:.6g}；"
            f"至少需要 {min_top_k} 只股票"
        )

    # 把面板 unstack 成宽表便于按行处理
    score_w = score_panel["score"].unstack("code")
    ret_w = returns_panel["ret_1d"].unstack("code")
    if score_w.empty or ret_w.empty:
        raise ValueError("score_panel 和 returns_panel 都必须包含数据")
    # 回测日历以实际收益面板为准，并从首个可交易 score 日期延伸到收益
    # 面板末尾。若在最后一个 score 日期截断，会漏掉已经建立的持仓在
    # 随后交易日真实发生的收益。信号日历则只延伸到最后一个有效 score，
    # 避免在尾部收益期生成没有研究分数支持的伪信号。
    valid_score_dates = score_w.index[score_w.notna().any(axis=1)]
    overlapping_score_dates = valid_score_dates.intersection(ret_w.index)
    if overlapping_score_dates.empty:
        raise ValueError("score_panel 与 returns_panel 没有含有效分数的重叠日期")
    start = overlapping_score_dates.min()
    last_valid_score_date = overlapping_score_dates.max()
    common_idx = ret_w.index[ret_w.index >= start].sort_values()
    score_w = score_w.reindex(common_idx)
    ret_w = ret_w.reindex(index=common_idx, columns=score_w.columns)
    # 停牌或缺失行情按当日收益 0 处理
    ret_w = ret_w.fillna(0.0)

    # 这些日期只生成目标权重；真正换仓在各自的下一交易日收盘执行。
    signal_calendar = common_idx[common_idx <= last_valid_score_date]
    signal_dates = signal_calendar[::rebalance_freq]
    signal_set = set(signal_dates)

    # 持仓表（= 0 / 1/N）
    positions = pd.DataFrame(0.0, index=common_idx, columns=score_w.columns)
    turnover = pd.Series(0.0, index=common_idx)
    daily_ret = pd.Series(0.0, index=common_idx)
    active_weights = pd.Series(0.0, index=score_w.columns)
    pending_weights: pd.Series | None = None
    last_rebalance_idx: int | None = None
    executed_indices: list[int] = []

    for i, dt in enumerate(common_idx):
        # ret_1d 是“前一收盘 → 今日收盘”的收益。昨日收盘才得到的信号
        # 不能在今日整段 close-to-close 收益开始前成交，因此今日收益仍由
        # 昨日收盘时已存在的 active_weights 承担。
        positions.loc[dt] = active_weights
        asset_returns = ret_w.loc[dt]
        gross_return = float((active_weights * asset_returns).sum())

        # 先把旧持仓漂移到今日收盘，再在收盘执行昨日信号。这样换手是
        # 相对实际成交前权重计算的，也不会误吃 T close → T+1 close 收益。
        gross_value = 1.0 + gross_return
        if gross_value <= 0:
            raise RuntimeError("组合单日总价值非正，无法更新漂移权重")
        active_weights = active_weights.mul(1.0 + asset_returns).div(gross_value)

        trade_cost = 0.0
        if pending_weights is not None:
            turnover.loc[dt] = (pending_weights - active_weights).abs().sum()
            trade_cost = apply_trading_cost(
                active_weights,
                pending_weights,
                cost_bps=cost_bps,
            )
            active_weights = pending_weights
            pending_weights = None
            last_rebalance_idx = i
            executed_indices.append(i)
        daily_ret.loc[dt] = gross_return - trade_cost

        # 收盘后基于今日 score 生成明日目标权重。末日信号没有可执行的
        # 下一交易日，不能形成虚假的换手、成本或 rebalance date。
        effective_idx = i + 1
        holding_period_satisfied = (
            last_rebalance_idx is None
            or effective_idx - last_rebalance_idx >= min_holding_days
        )
        if (
            dt in signal_set
            and effective_idx < len(common_idx)
            and holding_period_satisfied
        ):
            # 选 TopK
            row = score_w.loc[dt].dropna()
            # 整个截面都没有分数通常意味着模型 fold 缺口或数据缺失，
            # 不是明确的清仓信号；保持现有持仓直到下一次有效信号。
            if row.empty:
                continue
            if len(row) >= top_k:
                picks = row.nlargest(top_k).index
            else:
                picks = row.index
            if len(picks) * max_weight < 1.0 - 1e-12:
                raise ValueError(
                    f"{dt:%Y-%m-%d} 仅有 {len(picks)} 只有效候选，"
                    f"在 max_weight={max_weight:.6g} 下无法满仓"
                )
            new_w = pd.Series(0.0, index=score_w.columns)
            w = 1.0 / len(picks)
            new_w.loc[picks] = w
            pending_weights = new_w

    # 构造净值
    nav = (1 + daily_ret).cumprod()
    n_stocks_avg = (positions > 0).sum(axis=1).mean()

    return BacktestResult(
        nav=nav,
        daily_ret=daily_ret,
        turnover=turnover,
        positions=positions,
        rebalance_dates=common_idx[executed_indices],
        cost_bps=cost_bps,
        n_stocks_avg=float(n_stocks_avg),
    )


def make_ret_panel(
    quotes: dict[str, pd.DataFrame],
    horizon: int = 1,
    use_fwd: bool = False,
) -> pd.DataFrame:
    """构造收益面板（用于回测）。

    ``use_fwd=True`` 时，日期 T 上的值严格定义为同一只股票从 T 日
    收盘到其第 T+h 个有效观测日收盘的累计收益：
    ``close[T+h] / close[T] - 1``。每只股票独立计算，末尾不足 h 个
    观测的日期保留为 NaN。输出列为兼容现有调用仍命名为 ``ret_1d``。

    Args:
        quotes: 日行情。
        horizon: 未来收益跨度（有效观测数，仅 use_fwd=True 生效）。
        use_fwd: True → T 到 T+h 的未来累计收益；False → T 日实际单日收益。
    """
    if horizon < 1:
        raise ValueError("horizon 必须是正整数")

    rows = {}
    for code, df in quotes.items():
        close = df["close"]
        r = close.shift(-horizon).div(close).sub(1.0) if use_fwd else close.pct_change()
        rows[code] = r.rename("ret_1d")
    panel = pd.concat(rows, axis=1)
    panel.columns.name = "code"
    panel = panel.stack(future_stack=True).rename("ret_1d").to_frame()
    panel.index.set_names(["date", "code"], inplace=True)
    return panel


def attach_score_to_panel(
    score_panel: pd.DataFrame,
    factor_panel: pd.DataFrame,
    factor_cols: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """把多因子面板聚合成单一 score。

    默认等权；weights 提供时按权加和。
    """
    cols = factor_cols or [
        c for c in factor_panel.columns if c not in {"industry", "is_suspended"}
    ]
    weights = weights or {c: 1.0 for c in cols}
    w = pd.Series(weights).reindex(cols).fillna(0.0)
    s = factor_panel[cols].mul(w, axis=1).sum(axis=1, skipna=True)
    s = s.to_frame("score")
    return s

"""稳健性分析：按市值 / 行业 / 市场阶段（牛/熊）分层。"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from factorlab.evaluation.returns import perf_stats


def assign_cap_bucket(market_cap: pd.Series, q: List[float] = [0.5, 0.9]) -> pd.Series:
    """根据市值分桶。

    Args:
        market_cap: 截面市值序列。
        q: 分位阈值。默认 [0.5, 0.9] → 小 / 中 / 大。
    """
    cap_bucket = pd.Series("unknown", index=market_cap.index)
    qs = market_cap.quantile(q)
    if isinstance(qs, pd.Series):
        qs = qs.tolist()
    cap_bucket[market_cap <= qs[0]] = "small"
    cap_bucket[(market_cap > qs[0]) & (market_cap <= qs[1])] = "mid"
    cap_bucket[market_cap > qs[1]] = "large"
    return cap_bucket


def group_perf_by(
    nav_by_group: Dict[str, pd.Series],
) -> pd.DataFrame:
    """计算各组收益指标。

    Args:
        nav_by_group: {group_key: nav_series}

    Returns:
        行为 group，列为指标。
    """
    rows = []
    for k, nav in nav_by_group.items():
        stats = perf_stats(nav)
        stats["group"] = k
        rows.append(stats)
    return pd.DataFrame(rows).set_index("group")


def market_regime_label(
    benchmark_nav: pd.Series,
    lookback_months: int = 12,
    bull_threshold: float = 0.20,
) -> pd.Series:
    """牛/熊/震荡 阶段标签。

    规则：
        - 过去 lookback_months 月累计涨幅 > bull_threshold → bull
        - 过去 lookback_months 月累计跌幅 < -bull_threshold → bear
        - 否则 neutral
    """
    rets = benchmark_nav.pct_change().fillna(0)
    rolling = (1 + rets).rolling(lookback_months * 21, min_periods=60).apply(np.prod, raw=True) - 1
    label = pd.Series("neutral", index=benchmark_nav.index)
    label[rolling > bull_threshold] = "bull"
    label[rolling < -bull_threshold] = "bear"
    return label


def robustness_by_cap(
    nav: pd.Series, panel_with_cap: pd.DataFrame, date_col: str = "date"
) -> pd.DataFrame:
    """按市值分桶，仅当回测器按 cap 切片时可用。这里给出框架。

    一般流程：
        1. 每个调仓日按市值分桶 → 得子组合 nav
        2. 分别算 perf_stats
        3. 输出对比表
    """
    # 简化版：返回空 df 与说明；具体实现依赖回测器传入"按 cap 切片"的 nav
    return pd.DataFrame({"note": ["需回测器按 cap 切片后填入"]})


def robustness_by_industry(
    nav_by_industry: Dict[str, pd.Series],
) -> pd.DataFrame:
    """按行业的子组合 NAV 字典 → 表现统计。"""
    return group_perf_by(nav_by_industry)


def robustness_by_regime(
    nav: pd.Series,
    regime_label: pd.Series,
) -> pd.DataFrame:
    """按市场阶段（Bear / Neutral / Bull）评估组合表现。"""
    if regime_label.isna().all():
        return pd.DataFrame()
    out = []
    for k in ["bull", "neutral", "bear"]:
        mask = regime_label.reindex(nav.index) == k
        sub = nav.loc[mask]
        if len(sub) < 30:
            continue
        stats = perf_stats(sub)
        stats["regime"] = k
        out.append(stats)
    return pd.DataFrame(out).set_index("regime")

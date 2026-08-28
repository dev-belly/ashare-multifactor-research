"""分组组合（Sort Portfolio）：按因子值分组构造等权/加权组合。"""
from __future__ import annotations

import pandas as pd

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


class SortPortfolio:
    """分组组合：每期按 factor 分 N 组 → 组内等权（默认）→ 跟踪各组收益。"""

    def __init__(self, n_groups: int = 5, weighting: str = "equal"):
        self.n_groups = n_groups
        self.weighting = weighting

    def assign(
        self, factor_panel: pd.DataFrame, factor_col: str
    ) -> pd.DataFrame:
        """每期按 factor_col 分组（1=最低, N=最高），返回 (date, code) → group 标签。"""
        f = factor_panel[factor_col]
        # 截面分位
        group = f.groupby(level="date").transform(
            lambda s: pd.qcut(s.rank(method="first"), self.n_groups, labels=False, duplicates="drop") + 1
        )
        return group.to_frame("group")

    def backtest(
        self,
        factor_panel: pd.DataFrame,
        returns_panel: pd.DataFrame,
        factor_col: str,
    ) -> pd.DataFrame:
        """返回 (date, group) → 收益。

        Args:
            factor_panel: 因子面板（长格式）。
            returns_panel: 收益面板（长格式，含 'ret_1d'）。
            factor_col: 因子列名。
        """
        groups = self.assign(factor_panel, factor_col)
        # 合并收益
        merged = groups.join(returns_panel[["ret_1d"]], how="inner")
        merged = merged.dropna(subset=["group", "ret_1d"])
        # 按 (date, group) 等权平均
        grouped_ret = (
            merged.groupby(["date", "group"])["ret_1d"].mean().unstack("group")
        )
        grouped_ret.columns = [f"G{int(c)}" for c in grouped_ret.columns]
        return grouped_ret.fillna(0.0)

    def long_short_spread(self, group_ret: pd.DataFrame) -> pd.Series:
        """长-短组差（多最高组，空最低组）。"""
        cols = sorted(group_ret.columns)
        if len(cols) < 2:
            return pd.Series(0.0, index=group_ret.index)
        return group_ret[cols[-1]] - group_ret[cols[0]]

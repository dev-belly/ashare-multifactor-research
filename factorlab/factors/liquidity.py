"""流动性因子：换手率、Amihud 非流动性。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from factorlab.factors.base import Factor


def _turnover(volume: pd.Series, shares: float) -> pd.Series:
    if shares is None or shares <= 0:
        return pd.Series(np.nan, index=volume.index)
    return volume / shares


class TurnoverFactor(Factor):
    """换手率 = 日成交量 / 流通股本（合成数据用总股本近似）。

    高换手率与高收益动量相关；这里按"绝对换手率"算，
    在 5 分组回测中再以"低 vs 高"对比。
    """

    def __init__(self, name: str = "turn_20d", window: int = 20, negative: bool = False):
        self.name = name
        self.window = window
        self.negative = negative
        self.category = "liquidity"

    def compute(
        self,
        quotes: dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        out: dict[str, pd.Series] = {}
        for code, df in quotes.items():
            if "volume" not in df.columns:
                continue
            v = df["volume"].rolling(self.window, min_periods=self.window // 2).mean()
            v.name = self.name
            if self.negative:
                v = -v
            out[code] = v
        return self.to_long(out, self.name)


class AmihudFactor(Factor):
    """Amihud 非流动性 = |日收益| / 日成交额（取 20 日均值）。值越大越不流动。"""

    name = "amihud_20d"
    category = "liquidity"

    def __init__(self, window: int = 20):
        self.window = window

    def compute(
        self,
        quotes: dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        out: dict[str, pd.Series] = {}
        for code, df in quotes.items():
            if "close" not in df.columns or "amount" not in df.columns:
                continue
            r = df["close"].pct_change().abs()
            amihud = r / (df["amount"] + 1e-12)
            amihud = amihud.rolling(self.window, min_periods=self.window // 2).mean()
            amihud = -amihud  # 低非流动 → 高分
            amihud.name = self.name
            out[code] = amihud
        return self.to_long(out, self.name)

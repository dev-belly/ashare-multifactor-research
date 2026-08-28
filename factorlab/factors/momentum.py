"""动量因子：1M、3M、12-10（去最近 10 日以避开反转）。"""
from __future__ import annotations

import pandas as pd

from factorlab.factors.base import Factor


def _past_return(close: pd.Series, lookback: int, skip: int = 0) -> pd.Series:
    """过去 lookback 日累计收益（可 skip 最近 skip 日）。"""
    return close.shift(skip) / close.shift(lookback + skip) - 1


class MomentumFactor(Factor):
    """动量因子：可配置窗口。

    Args:
        name: 因子名。
        lookback: 回看窗口。
        skip: 跳过最近几日（避免短期反转污染）。
    """

    def __init__(self, name: str, lookback: int, skip: int = 0):
        self.name = name
        self.lookback = lookback
        self.skip = skip
        self.category = "momentum"

    def compute(
        self,
        quotes: dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        out: dict[str, pd.Series] = {}
        for code, df in quotes.items():
            if "close" not in df.columns:
                continue
            s = _past_return(df["close"], self.lookback, self.skip)
            s.name = self.name
            out[code] = s
        return self.to_long(out, self.name)


# 预置常用动量
class Mom1M(MomentumFactor):
    def __init__(self):
        super().__init__("mom_1m", lookback=21)


class Mom3M(MomentumFactor):
    def __init__(self):
        super().__init__("mom_3m", lookback=63)


class Mom12_10(MomentumFactor):
    """12 个月动量，跳过最近 1 个月（21 个交易日）以规避短期反转。

    对应经典 Carhart (1997) MOM 定义：t-12 月至 t-1 月的累计收益。
    因子名沿用业内 `12_10` 惯例写法，实际跳过窗口为 21 个交易日。
    """

    def __init__(self):
        super().__init__("mom_12_10", lookback=252, skip=21)

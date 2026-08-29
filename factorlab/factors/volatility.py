"""波动率因子：20/60 日收益标准差、特质波动率。"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from factorlab.factors.base import Factor


def _realized_vol(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window, min_periods=max(5, window // 4)).std()


class VolatilityFactor(Factor):
    """已实现波动率（带负向：低波动 = 高分）。"""

    def __init__(self, name: str, window: int, negative: bool = True):
        self.name = name
        self.window = window
        self.negative = negative
        self.category = "volatility"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        out: Dict[str, pd.Series] = {}
        for code, df in quotes.items():
            if "close" not in df.columns:
                continue
            r = df["close"].pct_change()
            v = _realized_vol(r, self.window)
            if self.negative:
                v = -v  # 低波动 → 高分
            v.name = self.name
            out[code] = v
        return self.to_long(out, self.name)


class Vol20D(VolatilityFactor):
    def __init__(self):
        super().__init__("vol_20d", 20, negative=True)


class Vol60D(VolatilityFactor):
    def __init__(self):
        super().__init__("vol_60d", 60, negative=True)


class IdioVolFactor(Factor):
    """特质波动率 = 收益对市场收益回归后的残差标准差。

    简化为：以沪深 300 近似为市场基准，
    IdioVol = std(residuals(rolling)) over 60 日。
    """

    name = "idio_vol"
    category = "volatility"

    def __init__(self, window: int = 60):
        self.window = window

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        # 选取第一只 large 蓝筹作为市场代理（简化）
        # 实际应传入 benchmark 行情
        if not quotes:
            return pd.DataFrame()
        # 用"等权平均"作为市场代理
        rets = pd.DataFrame(
            {
                c: d.get("ret_1d", d["close"].pct_change())
                for c, d in quotes.items()
                if "close" in d.columns
            }
        )
        mkt = rets.mean(axis=1)

        out: Dict[str, pd.Series] = {}
        for code, df in quotes.items():
            r = df.get("ret_1d", df["close"].pct_change())
            df_ = pd.concat([r.rename("r"), mkt.rename("mkt")], axis=1).dropna()
            if len(df_) < self.window:
                continue
            # 滚动 beta 与残差
            roll = df_.rolling(self.window, min_periods=self.window // 2)
            cov = roll.cov().unstack(level=-1)
            var_mkt = cov.xs("mkt", level=1, axis=1)["mkt"]
            cov_rm = cov.xs("r", level=1, axis=1)["mkt"]
            beta = (cov_rm / (var_mkt + 1e-12)).fillna(0)
            resid = df_["r"] - beta * df_["mkt"]
            iv = resid.rolling(self.window, min_periods=self.window // 2).std()
            iv = -iv  # 低特质波动 → 高分
            iv.name = self.name
            out[code] = iv.reindex(df.index)
        return self.to_long(out, self.name)

"""价值因子：EP、BP、SP、E/P2Y。

均以"最新可得"季度财务披露（publish_date + lag）后的对应 TTM 计算。
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.factors.base import Factor

# 财务字段映射（不同数据源 key 不同，做兼容）
FIELDS = {
    "net_profit": ["net_profit", "np", "np_parent"],
    "revenue": ["revenue", "rev"],
    "equity": ["equity", "bv"],
    "total_assets": ["total_assets", "ta"],
    "shares": ["shares", "total_share"],
    "eps": ["eps"],
    "bvps": ["bvps"],
}


def _pick(df: pd.DataFrame, names: list[str], default: float = np.nan) -> pd.Series:
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series(default, index=df.index)


def _ttm(per_code: pd.DataFrame, value_col: str, periods: int = 4) -> pd.Series:
    """计算 TTM：以 period_end 排序的滚动 4 季求和。

    每只股票只算自己的 TTM，不跨股票。
    """
    per_code = per_code.sort_values("period_end")
    return per_code[value_col].rolling(periods, min_periods=2).sum()


class EPFactor(Factor):
    """EP（盈利收益率）= TTM 归母净利润 / 总市值。"""

    name = "ep"
    category = "value"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        return self._build(quotes, financials, _pick(financials, FIELDS["net_profit"]))

    def _build(
        self,
        quotes: Dict[str, pd.DataFrame],
        fin: pd.DataFrame,
        np_series: pd.Series,
    ) -> pd.DataFrame:
        # 每只股票：按 period_end 排序计算 TTM
        fin = fin.copy()
        fin["net_profit"] = np_series.values

        per_code = []
        for code, g in fin.groupby("code"):
            g = g.sort_values("period_end")
            g["ttm_np"] = g["net_profit"].rolling(4, min_periods=2).sum()
            per_code.append(g)
        fin_ttm = pd.concat(per_code, axis=0)

        out: Dict[str, pd.Series] = {}
        for code, qdf in quotes.items():
            sub = fin_ttm[fin_ttm["code"].astype(str) == code].copy()
            if sub.empty:
                continue
            # 财务发布日期之前不可用：取到最近可用 ttm
            cal = qdf.index
            mcap = qdf["close"] * _pick(sub, FIELDS["shares"]).iloc[-1]
            mcap.name = "mcap"
            # 对每个交易日找该日或之前最近披露的 ttm_np
            sub_idx = sub.set_index("available_date")["ttm_np"].sort_index()
            aligned = sub_idx.reindex(cal, method="ffill")
            ep = aligned.values / mcap.values
            out[code] = pd.Series(ep, index=cal, name=self.name)
        return self.to_long(out, self.name)


class BPFactor(Factor):
    """BP（账面市值比）= 归母权益 / 总市值。"""

    name = "bp"
    category = "value"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        return self._build(quotes, financials)

    def _build(self, quotes: Dict[str, pd.DataFrame], fin: pd.DataFrame) -> pd.DataFrame:
        fin = fin.copy()
        out: Dict[str, pd.Series] = {}
        eq_col = FIELDS["equity"][0] if FIELDS["equity"][0] in fin.columns else None
        sh_col = FIELDS["shares"][0] if FIELDS["shares"][0] in fin.columns else None
        if eq_col is None or sh_col is None:
            return pd.DataFrame()

        for code, qdf in quotes.items():
            sub = fin[fin["code"].astype(str) == code].sort_values("period_end")
            if sub.empty:
                continue
            cal = qdf.index
            mcap = qdf["close"] * sub[sh_col].iloc[-1]
            sub_idx = sub.set_index("available_date")[eq_col].sort_index()
            aligned = sub_idx.reindex(cal, method="ffill")
            bp = aligned.values / mcap.values
            out[code] = pd.Series(bp, index=cal, name=self.name)
        return self.to_long(out, self.name)


class SPFactor(Factor):
    """SP（销售市值比）= TTM 营业收入 / 总市值。"""

    name = "sp"
    category = "value"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        fin = financials.copy()
        out: Dict[str, pd.Series] = {}
        rev_col = "revenue"
        if rev_col not in fin.columns:
            return pd.DataFrame()
        for code, qdf in quotes.items():
            sub = fin[fin["code"].astype(str) == code].sort_values("period_end")
            if sub.empty:
                continue
            sub["ttm_rev"] = sub[rev_col].rolling(4, min_periods=2).sum()
            cal = qdf.index
            mcap = qdf["close"] * sub["shares"].iloc[-1]
            sub_idx = sub.set_index("available_date")["ttm_rev"].sort_index()
            aligned = sub_idx.reindex(cal, method="ffill")
            sp = aligned.values / mcap.values
            out[code] = pd.Series(sp, index=cal, name=self.name)
        return self.to_long(out, self.name)


class EP2YFactor(Factor):
    """E/P2Y：EP 同比改善（去趋势），捕捉盈利动量。

    在 EP 基础上取同比变化：EP_t - EP_{t-4Q}。
    直接用行情复权收盘价近似同比 EP（避免受父类 name 覆盖影响）。
    """

    name = "ep_chg_yoy"
    category = "value"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()

        # 直接调用父类逻辑，但强制把列名改为 'ep' 再做同比
        ep_long = EPFactor().compute(quotes, financials, industry_map)
        if ep_long.empty:
            return ep_long
        # 上层注册表可能改名；这里强制以 'ep' 为基准
        if "ep" not in ep_long.columns:
            # 兜底：把唯一的因子列视为 'ep'
            only = [c for c in ep_long.columns if c not in {"industry", "is_suspended"}]
            if not only:
                return pd.DataFrame()
            ep_long = ep_long.rename(columns={only[0]: "ep"})
        # 同比差分 = 当期 EP 与 252 个交易日（约一年）前的差
        ep_long = ep_long.sort_index()
        diff = ep_long.groupby(level="code")["ep"].shift(252)
        out = ep_long.copy()
        out[self.name] = ep_long["ep"] - diff
        return out.dropna(subset=[self.name])[[self.name]]

    @staticmethod
    def _ebase_name() -> str:
        return "ep"

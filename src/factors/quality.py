"""质量因子：ROE、ROA、毛利率、应计利润。

ROE / ROA 使用 TTM（4 季度滚动）；毛利率 = TTM 毛利 / TTM 营收；
应计利润 = (Δ流动资产 - 现金) - (Δ流动负债 - 短期借款) - 折旧。
此处用简化版：Accruals = (NetProfit - OCF) / TotalAssets。
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from src.factors.base import Factor


def _ttm(series: pd.Series, periods: int = 4) -> pd.Series:
    return series.rolling(periods, min_periods=2).sum()


def _align_to_calendar(series: pd.Series, cal: pd.DatetimeIndex) -> pd.Series:
    return series.reindex(cal, method="ffill")


class ROEFactor(Factor):
    name = "roe"
    category = "quality"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        fin = financials.copy()
        if "net_profit" not in fin.columns or "equity" not in fin.columns:
            return pd.DataFrame()
        out: Dict[str, pd.Series] = {}
        for code, qdf in quotes.items():
            sub = fin[fin["code"].astype(str) == code].sort_values("period_end")
            if sub.empty or sub["equity"].isna().all():
                continue
            sub["roe_q"] = sub["net_profit"] / sub["equity"]
            sub["roe_ttm"] = _ttm(sub["net_profit"]) / sub["equity"]
            cal = qdf.index
            aligned = _align_to_calendar(
                sub.set_index("available_date")["roe_ttm"].sort_index(), cal
            )
            out[code] = pd.Series(aligned.values, index=cal, name=self.name)
        return self.to_long(out, self.name)


class ROAFactor(Factor):
    name = "roa"
    category = "quality"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        fin = financials.copy()
        if "net_profit" not in fin.columns or "total_assets" not in fin.columns:
            return pd.DataFrame()
        out: Dict[str, pd.Series] = {}
        for code, qdf in quotes.items():
            sub = fin[fin["code"].astype(str) == code].sort_values("period_end")
            if sub.empty:
                continue
            sub["roa_ttm"] = _ttm(sub["net_profit"]) / sub["total_assets"]
            cal = qdf.index
            aligned = _align_to_calendar(
                sub.set_index("available_date")["roa_ttm"].sort_index(), cal
            )
            out[code] = pd.Series(aligned.values, index=cal, name=self.name)
        return self.to_long(out, self.name)


class GrossMarginFactor(Factor):
    """毛利率因子：TTM 毛利 / TTM 营收。"""

    name = "gp_a"
    category = "quality"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        fin = financials.copy()
        if not {"gross_profit", "revenue"}.issubset(fin.columns):
            return pd.DataFrame()
        out: Dict[str, pd.Series] = {}
        for code, qdf in quotes.items():
            sub = fin[fin["code"].astype(str) == code].sort_values("period_end")
            if sub.empty:
                continue
            sub["gp_margin"] = _ttm(sub["gross_profit"]) / _ttm(sub["revenue"])
            cal = qdf.index
            aligned = _align_to_calendar(
                sub.set_index("available_date")["gp_margin"].sort_index(), cal
            )
            out[code] = pd.Series(aligned.values, index=cal, name=self.name)
        return self.to_long(out, self.name)


class AccrualsFactor(Factor):
    """应计利润 = (TTM_NI - TTM_OCF) / TotalAssets。值越小（更负）质量越好。"""

    name = "accruals"
    category = "quality"

    def compute(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if financials is None or financials.empty:
            return pd.DataFrame()
        fin = financials.copy()
        if not {"net_profit", "operating_cf", "total_assets"}.issubset(fin.columns):
            return pd.DataFrame()
        out: Dict[str, pd.Series] = {}
        for code, qdf in quotes.items():
            sub = fin[fin["code"].astype(str) == code].sort_values("period_end")
            if sub.empty:
                continue
            sub["accruals"] = (
                _ttm(sub["net_profit"]) - _ttm(sub["operating_cf"])
            ) / sub["total_assets"]
            cal = qdf.index
            aligned = _align_to_calendar(
                sub.set_index("available_date")["accruals"].sort_index(), cal
            )
            out[code] = pd.Series(aligned.values, index=cal, name=self.name)
        return self.to_long(out, self.name)

"""因子基类 + 截面处理工具（缩尾、标准化、行业中性化、停牌过滤）。"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


# ========== 截面处理 ==========
def cross_section_winsorize(
    df: pd.DataFrame,
    factor_cols: list[str],
    lower_q: float = 0.01,
    upper_q: float = 0.99,
) -> pd.DataFrame:
    """按截面 1%/99% 分位缩尾。"""
    out = df.copy()
    for col in factor_cols:
        if col not in out.columns:
            continue
        g = out[col].groupby(level="date")
        lo = g.transform(lambda s: s.quantile(lower_q))
        hi = g.transform(lambda s: s.quantile(upper_q))
        out[col] = out[col].clip(lower=lo, upper=hi)
    return out


def cross_section_standardize(
    df: pd.DataFrame,
    factor_cols: list[str],
    method: str = "zscore",
) -> pd.DataFrame:
    """截面标准化：zscore（默认，去均值除 std） 或 rank（百分位 0-1）。

    标准化的目的是消除市值/量纲等极值主导。向量化。
    """
    out = df.copy()
    if method == "zscore":
        for col in factor_cols:
            if col not in out.columns:
                continue
            g = out[col].groupby(level="date")
            mean = g.transform("mean")
            std = g.transform("std").fillna(0.0)
            out[col] = (out[col] - mean) / (std + 1e-12)
    elif method == "rank":
        for col in factor_cols:
            if col not in out.columns:
                continue
            out[col] = (
                out[col].groupby(level="date").rank(pct=True) - 0.5
            )
    else:
        raise ValueError(f"unknown standardize method: {method}")
    return out


def industry_neutralize(
    df: pd.DataFrame,
    factor_cols: list[str],
    industry_col: str = "industry",
) -> pd.DataFrame:
    """行业内 zscore 中性化：每个行业内单独标准化。

    消除"同行业相似"导致的 IC 偏差。向量化实现：先按 (date, industry)
    计算 mean / std，再做减除；避免对每组调 lambda。
    """
    out = df.copy()
    if industry_col not in out.columns:
        return out
    keys = ["date", industry_col]
    for col in factor_cols:
        if col not in out.columns:
            continue
        g = out.groupby(keys)[col]
        mean = g.transform("mean")
        std = g.transform("std").fillna(0.0)
        out[col] = (out[col] - mean) / (std + 1e-12)
    return out


def filter_universe(
    df: pd.DataFrame,
    st_codes: list[str] | None = None,
    suspended_col: str = "is_suspended",
    factor_cols: list[str] | None = None,
) -> pd.DataFrame:
    """过滤 ST 与停牌样本。

    默认将 (suspended | ST) 的样本**因子值**置 NaN，不动元数据列。
    """
    out = df.copy()
    if factor_cols is None:
        factor_cols = [
            c for c in out.columns if c not in {suspended_col, "industry", "is_suspended"}
        ]
    mask = pd.Series(False, index=out.index)
    if suspended_col in out.columns:
        mask = mask | out[suspended_col].fillna(False).astype(bool)
    if st_codes:
        mask = mask | out.index.get_level_values("code").isin(st_codes)
    if mask.any():
        out.loc[mask, factor_cols] = np.nan
    return out


# ========== 因子基类 ==========
class Factor(ABC):
    """单因子接口：compute() 返回长格式 DataFrame（MultiIndex date×code）。"""

    name: str = "factor"
    category: str = "misc"

    @abstractmethod
    def compute(
        self,
        quotes: dict[str, pd.DataFrame],
        financials: pd.DataFrame | None = None,
        industry_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """返回长格式 DataFrame：index=(date,code), columns=[<name>]。"""

    @staticmethod
    def to_long(series_map: dict[str, pd.Series], name: str) -> pd.DataFrame:
        """把 {code: Series} 拼成长格式 (date, code, name)。

        Robust: 即便只有 1 只股票，也能正确产出 MultiIndex。
        """
        if not series_map:
            return pd.DataFrame(
                {name: []}, index=pd.MultiIndex.from_arrays([[], []], names=["date", "code"])
            )

        # 方案：逐个 Series 转成 (date, code) DataFrame，再 concat
        parts = []
        for code, s in series_map.items():
            df_i = s.to_frame(name)
            df_i = df_i.reset_index()
            df_i.columns = ["date", name]
            df_i["code"] = code
            parts.append(df_i)
        out = pd.concat(parts, axis=0, ignore_index=True)
        out = out.dropna(subset=[name])
        out = out[["date", "code", name]]
        out = out.set_index(["date", "code"]).sort_index()
        return out

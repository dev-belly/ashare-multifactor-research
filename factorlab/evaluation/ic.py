"""IC / RankIC 计算与统计。"""
from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


def calc_ic_series(
    factor_panel: pd.DataFrame,  # 含 factor_col 与 'ret_1d'
    factor_col: str,
    method: str = "pearson",
) -> pd.Series:
    """截面 IC 时间序列。

    Args:
        factor_panel: 长格式（date, code），至少含 factor_col 与 ret_1d。
        factor_col: 因子列。
        method: 'pearson' | 'spearman'。

    Returns:
        索引为交易日，值为当期 IC。
    """
    needed = [factor_col, "ret_1d"]
    df = factor_panel[needed].dropna()
    if df.empty:
        return pd.Series(dtype=float)

    def _corr(group: pd.DataFrame) -> float:
        x = group[factor_col].values
        y = group["ret_1d"].values
        if len(x) < 5:
            return np.nan
        if method == "pearson":
            r, _ = pearsonr(x, y)
        elif method == "spearman":
            r, _ = spearmanr(x, y)
        else:
            r = np.nan
        return r

    ic = df.groupby(level="date").apply(_corr)
    ic.name = factor_col
    return ic


def ic_summary(ic: pd.Series) -> dict:
    """返回 IC 的摘要统计：mean, std, IR, IC>0 比例。"""
    ic = ic.dropna()
    if ic.empty:
        return {
            "n_periods": 0,
            "ic_mean": np.nan,
            "ic_std": np.nan,
            "ir": np.nan,
            "ic_pos_ratio": np.nan,
            "abs_ic_mean": np.nan,
        }
    mean = ic.mean()
    std = ic.std(ddof=1)
    ir = mean / (std + 1e-12)
    pos_ratio = (ic > 0).mean()
    return {
        "n_periods": int(len(ic)),
        "ic_mean": float(mean),
        "ic_std": float(std),
        "ir": float(ir),
        "ic_pos_ratio": float(pos_ratio),
        "abs_ic_mean": float(ic.abs().mean()),
    }


def multi_factor_ic_table(
    factor_panel: pd.DataFrame, factor_cols: List[str], methods: List[str] = ("pearson", "spearman")
) -> pd.DataFrame:
    """输出多因子 × 多方法 IC 摘要表。"""
    rows = []
    for col in factor_cols:
        for m in methods:
            ic = calc_ic_series(factor_panel, col, method=m)
            stats = ic_summary(ic)
            stats["factor"] = col
            stats["method"] = m
            rows.append(stats)
    return pd.DataFrame(rows)


def factor_return_decay(factor_panel: pd.DataFrame, factor_col: str, max_lag: int = 60) -> pd.DataFrame:
    """因子收益衰减：lag=1..max_lag 各期 IC。"""
    rows = []
    for lag in range(1, max_lag + 1):
        tmp = factor_panel[[factor_col]].copy()
        # 未来 lag 日收益（calc_ic_series 需要 ret_1d 列名）
        tmp["ret_1d"] = factor_panel["ret_1d"].groupby(level="code").shift(-lag)
        ic = calc_ic_series(tmp.dropna(), factor_col, method="spearman")
        rows.append(
            {
                "lag": lag,
                "ic_mean": ic.mean(),
                "ir": ic.mean() / (ic.std() + 1e-12),
                "n_periods": len(ic),
            }
        )
    return pd.DataFrame(rows)

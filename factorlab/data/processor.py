"""数据清洗：复权对齐、停牌标记、缺失值填补、基础衍生字段。"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


def basic_clean(quotes: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """基础清洗：去空、排序、衍生 pct_change / 涨跌停标记位。

    Args:
        quotes: 每只股票日行情 DataFrame。

    Returns:
        清洗后的 quotes（同结构，外加字段）。
    """
    cleaned: Dict[str, pd.DataFrame] = {}
    for code, df in quotes.items():
        if df is None or df.empty:
            continue
        d = df.copy()
        d = d.sort_index()
        # 必要字段
        need = ["open", "high", "low", "close", "volume"]
        for c in need:
            if c not in d.columns:
                d[c] = np.nan
        # 衍生
        d["ret_1d"] = d["close"].pct_change()
        # 涨跌停：10% (20% for ChiNext / STAR)
        d["limit_threshold"] = 0.10
        d["is_limit_up"] = d["ret_1d"] >= d["limit_threshold"] - 1e-6
        d["is_limit_down"] = d["ret_1d"] <= -d["limit_threshold"] + 1e-6
        # 停牌：成交量为 0 或缺失标记
        d["is_suspended"] = (d["volume"].fillna(0) == 0) | d["close"].isna()
        cleaned[code] = d
    return cleaned


def align_to_calendar(
    quotes: Dict[str, pd.DataFrame],
    calendar: pd.DatetimeIndex,
    suspend_value: str = "ffill",
) -> Dict[str, pd.DataFrame]:
    """统一对齐到交易日历，停牌日用 ffill 复权收盘价。"""
    out: Dict[str, pd.DataFrame] = {}
    for code, df in quotes.items():
        d = df.copy()
        if not isinstance(d.index, pd.DatetimeIndex):
            d.index = pd.to_datetime(d.index)
        d = d.reindex(calendar)
        # price 类 ffill
        for c in ["open", "high", "low", "close"]:
            d[c] = d[c].ffill()
        # 量能补 0
        if "volume" in d.columns:
            d["volume"] = d["volume"].fillna(0.0)
        d["is_suspended"] = d["is_suspended"].fillna(True)  # 未交易日视为停牌
        out[code] = d
    return out


def build_universe_table(
    quotes: Dict[str, pd.DataFrame],
    financials: pd.DataFrame | None = None,
    industry_map: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """构建股票池主表（首次上市日、最近可得日）。"""
    rows = []
    for code, df in quotes.items():
        first = df.index.min() if len(df) else pd.NaT
        last = df.index.max() if len(df) else pd.NaT
        rows.append({"code": code, "first_date": first, "last_date": last})
    universe = pd.DataFrame(rows)

    if industry_map is not None and not industry_map.empty:
        universe = universe.merge(industry_map, on="code", how="left")
    else:
        universe["industry"] = "Unknown"

    return universe


def merge_financial_quarterly(
    fin: pd.DataFrame,
    quotes_panel: pd.DataFrame,
    lag_days: int = 90,
) -> pd.DataFrame:
    """将季度财务按 publish_date 与行情日期合并，财务只有在 publish 后才"可用"。

    Args:
        fin: 季度财务表（code, period_end, publish_date, ...）。
        quotes_panel: MultiIndex (date, code) 的行情表。
        lag_days: 安全冗余。

    Returns:
        合并后的面板（每行对应一个 (date, code, period_end) 三元组）。
    """
    if fin is None or fin.empty:
        return pd.DataFrame()

    f = fin.copy()
    # 强制 apply lag：实际可用日 = publish_date + lag_days
    f["available_date"] = f["publish_date"] + pd.Timedelta(days=lag_days)
    return f


def forward_returns(
    quotes: Dict[str, pd.DataFrame], horizon: int = 21
) -> Dict[str, pd.Series]:
    """对未来 horizon 天的累计收益（T+1 至 T+1+horizon）。"""
    out: Dict[str, pd.Series] = {}
    for code, df in quotes.items():
        c = df["close"]
        # 未来 horizon 日收益从 T+1 开始
        fwd = c.shift(-horizon) / c.shift(-1) - 1
        fwd.name = f"fwd_ret_{horizon}d"
        out[code] = fwd
    return out

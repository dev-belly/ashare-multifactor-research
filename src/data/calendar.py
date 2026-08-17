"""交易日历：统一 A 股交易日基准。"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.utils.common import get_logger

logger = get_logger(__name__)


def get_trading_calendar(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    source: str = "synthetic",
) -> pd.DatetimeIndex:
    """获取区间内 A 股交易日历。

    Args:
        start: 起始日（包含）。
        end: 截止日（包含）。
        source: 数据源；synthetic/akshare/tushare。

    Returns:
        排序的交易日 DatetimeIndex。
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)

    if source == "akshare":
        try:
            import akshare as ak

            df = ak.tool_trade_date_hist_sina()
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            mask = (df["trade_date"] >= start) & (df["trade_date"] <= end)
            cal = df.loc[mask, "trade_date"].sort_values().reset_index(drop=True)
            return pd.DatetimeIndex(cal)
        except Exception as e:  # 网络/接口失败时降级
            logger.warning("AkShare 获取交易日历失败：%s，使用 synthetic 兜底", e)

    # synthetic：每个工作日都视为交易日（不含周末）。
    return pd.bdate_range(start=start, end=end, freq="B")


def intersect_calendars(
    calendars: Iterable[pd.DatetimeIndex],
) -> pd.DatetimeIndex:
    """多个交易日历取交集。"""
    sets = [set(c) for c in calendars]
    if not sets:
        return pd.DatetimeIndex([])
    common = set.intersection(*sets)
    return pd.DatetimeIndex(sorted(common))


def reindex_to_calendar(
    df: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    method: str = "ffill",
) -> pd.DataFrame:
    """将 DataFrame 重索引到统一交易日历。"""
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index)
    return df.reindex(calendar, method=method)

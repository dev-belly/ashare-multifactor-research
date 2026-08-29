"""交易日历：统一 A 股交易日基准，不静默混用数据源。"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def get_trading_calendar(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    source: str = "synthetic",
) -> pd.DatetimeIndex:
    """获取区间内 A 股交易日历。

    Args:
        start: 起始日（包含）。
        end: 截止日（包含）。
        source: 数据源；仅支持 ``synthetic`` 或 ``akshare``。

    Returns:
        排序的交易日 DatetimeIndex。
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    source = str(source).lower().strip()
    if start > end:
        raise ValueError("start 不能晚于 end")

    if source == "akshare":
        try:
            import akshare as ak

            df = ak.tool_trade_date_hist_sina()
            if df is None or df.empty or "trade_date" not in df.columns:
                raise RuntimeError("AkShare 未返回有效交易日历")
            dates = pd.to_datetime(df["trade_date"], errors="coerce").dropna()
            mask = (dates >= start) & (dates <= end)
            cal = pd.DatetimeIndex(dates.loc[mask].sort_values().unique())
            if cal.empty:
                raise RuntimeError("请求区间内没有 AkShare 交易日")
            return cal
        except Exception as exc:
            raise RuntimeError("AkShare 交易日历加载失败，未切换到 synthetic") from exc

    if source == "synthetic":
        # synthetic：每个工作日都视为交易日（不含周末和法定节假日）。
        return pd.bdate_range(start=start, end=end, freq="B")
    raise ValueError(f"不支持的交易日历数据源: {source!r}")


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

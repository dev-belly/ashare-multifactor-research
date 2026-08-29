from __future__ import annotations

import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from factorlab.data.calendar import get_trading_calendar


def test_synthetic_calendar_validates_range_and_source() -> None:
    expected = pd.DatetimeIndex(["2024-01-01", "2024-01-02", "2024-01-03"])
    pd.testing.assert_index_equal(
        get_trading_calendar("2024-01-01", "2024-01-03", source="synthetic"),
        expected,
    )

    with pytest.raises(ValueError, match="start"):
        get_trading_calendar("2024-01-03", "2024-01-01")
    with pytest.raises(ValueError, match="不支持"):
        get_trading_calendar("2024-01-01", "2024-01-03", source="tushare")


def test_akshare_calendar_failure_does_not_silently_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken_akshare = SimpleNamespace(
        tool_trade_date_hist_sina=lambda: (_ for _ in ()).throw(
            ConnectionError("offline")
        )
    )
    monkeypatch.setitem(sys.modules, "akshare", broken_akshare)

    with pytest.raises(RuntimeError, match="未切换到 synthetic"):
        get_trading_calendar("2024-01-01", "2024-01-05", source="akshare")

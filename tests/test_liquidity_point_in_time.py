from __future__ import annotations

import pandas as pd

from factorlab.factors.liquidity import TurnoverFactor


def test_turnover_uses_only_disclosed_share_counts() -> None:
    dates = pd.date_range("2024-01-01", periods=5)
    quotes = {
        "000001.SZ": pd.DataFrame(
            {"volume": [100.0] * 5, "close": [10.0] * 5},
            index=dates,
        )
    }
    financials = pd.DataFrame(
        {
            "code": ["000001.SZ", "000001.SZ"],
            "period_end": pd.to_datetime(["2023-09-30", "2023-12-31"]),
            "available_date": pd.to_datetime(["2024-01-02", "2024-01-04"]),
            "shares": [10.0, 20.0],
        }
    )

    result = (
        TurnoverFactor(window=1)
        .compute(quotes, financials)["turn_20d"]
        .xs("000001.SZ", level="code")
    )

    assert pd.Timestamp("2024-01-01") not in result.index
    assert result.loc["2024-01-03"] == 10.0
    assert result.loc["2024-01-05"] == 5.0

from __future__ import annotations

import pandas as pd

from factorlab.factors.value import BPFactor, EPFactor, SPFactor


def _fixture() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    calendar = pd.date_range("2024-01-01", periods=8, freq="D")
    quotes = {
        "000001.SZ": pd.DataFrame(
            {"close": 10.0, "volume": 1_000.0, "amount": 10_000.0},
            index=calendar,
        )
    }
    financials = pd.DataFrame(
        {
            "code": ["000001.SZ"] * 3,
            "period_end": pd.to_datetime(["2023-06-30", "2023-09-30", "2023-12-31"]),
            "available_date": pd.to_datetime(
                ["2024-01-02", "2024-01-03", "2024-01-06"]
            ),
            "net_profit": [100.0, 100.0, 100.0],
            "revenue": [1_000.0, 1_000.0, 1_000.0],
            "equity": [500.0, 600.0, 800.0],
            "shares": [10.0, 10.0, 20.0],
        }
    )
    return quotes, financials


def test_value_factors_use_only_share_counts_available_on_each_date() -> None:
    quotes, financials = _fixture()

    ep = EPFactor().compute(quotes, financials)["ep"].xs("000001.SZ", level="code")
    bp = BPFactor().compute(quotes, financials)["bp"].xs("000001.SZ", level="code")
    sp = SPFactor().compute(quotes, financials)["sp"].xs("000001.SZ", level="code")

    # Nothing is knowable before the first disclosure.
    assert pd.Timestamp("2024-01-01") not in ep.index

    # The first disclosure uses 10 shares; the second uses 20.  A future share
    # count must not be backfilled into the earlier period.
    assert ep.loc["2024-01-04"] == 2.0
    assert ep.loc["2024-01-07"] == 1.5
    assert bp.loc["2024-01-04"] == 6.0
    assert bp.loc["2024-01-07"] == 4.0
    assert sp.loc["2024-01-04"] == 20.0
    assert sp.loc["2024-01-07"] == 15.0

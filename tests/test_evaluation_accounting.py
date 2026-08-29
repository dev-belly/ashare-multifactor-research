from __future__ import annotations

import pandas as pd
import pytest

from factorlab.evaluation.robustness import robustness_by_regime
from factorlab.evaluation.turnover import turnover_stats


def test_annualized_turnover_uses_actual_sample_length() -> None:
    dates = pd.bdate_range("2024-01-02", periods=126)
    turnover = pd.Series(0.0, index=dates)
    turnover.iloc[[1, 64]] = [1.0, 2.0]

    stats = turnover_stats(turnover)

    assert stats["n_rebalances"] == 2
    assert stats["annualized"] == pytest.approx(6.0)


def test_regime_stats_do_not_assign_intervening_returns_to_sparse_dates() -> None:
    dates = pd.bdate_range("2024-01-02", periods=81)
    # Alternate zero-return bull days with +10% neutral days. Directly taking
    # pct_change on the sparse bull NAV would incorrectly include neutral gains.
    daily = pd.Series([0.0] + [0.0, 0.10] * 40, index=dates)
    nav = (1.0 + daily).cumprod()
    regimes = pd.Series(
        ["neutral"] + ["bull", "neutral"] * 40,
        index=dates,
    )

    result = robustness_by_regime(nav, regimes)

    assert result.loc["bull", "total_return"] == pytest.approx(0.0)
    assert result.loc["neutral", "total_return"] > 1.0

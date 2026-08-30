from __future__ import annotations

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_index_equal, assert_series_equal

from factorlab.backtest.engine import make_ret_panel, run_long_only_topk


def _panel(values: pd.DataFrame, value_name: str) -> pd.DataFrame:
    values = values.copy()
    values.columns.name = "code"
    panel = values.stack(future_stack=True).rename(value_name).to_frame()
    panel.index.set_names(["date", "code"], inplace=True)
    return panel


def _deterministic_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
    dates = pd.bdate_range("2024-01-02", periods=4, name="date")
    scores = pd.DataFrame(
        {
            "A": [10.0, 10.0, 0.0, 0.0],
            "B": [0.0, 0.0, 10.0, 10.0],
        },
        index=dates,
    )
    returns = pd.DataFrame(
        {
            "A": [1.00, 0.10, 0.01, 0.00],
            "B": [0.00, 0.00, 1.00, 0.20],
        },
        index=dates,
    )
    return _panel(scores, "score"), _panel(returns, "ret_1d"), dates


def test_signal_weights_start_next_day_without_same_day_return() -> None:
    scores, returns, dates = _deterministic_inputs()

    result = run_long_only_topk(
        scores,
        returns,
        top_k=1,
        rebalance_freq=2,
        min_holding_days=1,
        max_weight=1.0,
        cost_bps=0.0,
    )

    expected_positions = pd.DataFrame(
        {
            "A": [0.0, 0.0, 1.0, 1.0],
            "B": [0.0, 0.0, 0.0, 0.0],
        },
        index=dates,
    )
    expected_positions.columns.name = "code"
    assert_frame_equal(result.positions, expected_positions)

    # The day-0 A signal trades at the day-1 close, so it cannot capture either
    # day 0 or day 1 close-to-close returns. The day-2 B signal trades at the
    # day-3 close and therefore cannot capture B's day-3 return either.
    expected_daily_ret = pd.Series([0.0, 0.0, 0.01, 0.0], index=dates)
    assert_series_equal(result.daily_ret, expected_daily_ret)

    expected_turnover = pd.Series([0.0, 1.0, 0.0, 2.0], index=dates)
    assert_series_equal(result.turnover, expected_turnover)
    assert_index_equal(result.rebalance_dates, dates[[1, 3]])

    expected_nav = pd.Series([1.0, 1.0, 1.01, 1.01], index=dates)
    assert_series_equal(result.nav, expected_nav)


def test_cost_is_charged_on_weight_effective_date() -> None:
    scores, _, dates = _deterministic_inputs()
    zero_returns = pd.DataFrame(0.0, index=dates, columns=["A", "B"])

    result = run_long_only_topk(
        scores,
        _panel(zero_returns, "ret_1d"),
        top_k=1,
        rebalance_freq=2,
        min_holding_days=1,
        max_weight=1.0,
        cost_bps=100.0,
    )

    # 100 bps per side: initial buy costs 1%, full A -> B rotation costs 2%.
    expected_daily_ret = pd.Series([0.0, -0.01, 0.0, -0.02], index=dates)
    assert_series_equal(result.daily_ret, expected_daily_ret)

    # Costs must compound in NAV on the execution dates, not the signal dates.
    expected_nav = pd.Series([1.0, 0.99, 0.99, 0.9702], index=dates)
    assert_series_equal(result.nav, expected_nav)
    assert_series_equal(
        result.turnover,
        pd.Series([0.0, 1.0, 0.0, 2.0], index=dates),
    )
    assert_index_equal(result.rebalance_dates, dates[[1, 3]])


def test_make_ret_panel_forward_horizon_stays_within_each_code() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4, name="date")
    quotes = {
        "A": pd.DataFrame({"close": [100.0, 110.0, 121.0, 133.1]}, index=dates),
        "B": pd.DataFrame({"close": [1000.0, 500.0, 250.0, 125.0]}, index=dates),
    }

    result = make_ret_panel(quotes, horizon=2, use_fwd=True)

    expected_a = pd.Series(
        [0.21, 0.21, float("nan"), float("nan")], index=dates, name="ret_1d"
    )
    expected_b = pd.Series(
        [-0.75, -0.75, float("nan"), float("nan")], index=dates, name="ret_1d"
    )
    assert_series_equal(result.xs("A", level="code")["ret_1d"], expected_a)
    assert_series_equal(result.xs("B", level="code")["ret_1d"], expected_b)


def test_weights_drift_between_rebalances_instead_of_free_daily_rebalancing() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4, name="date")
    scores = _panel(
        pd.DataFrame(
            {"A": [2.0, 2.0, 2.0, 2.0], "B": [1.0, 1.0, 1.0, 1.0]},
            index=dates,
        ),
        "score",
    )
    returns = _panel(
        pd.DataFrame(
            {"A": [0.0, 0.0, 1.0, 0.0], "B": [0.0, 0.0, 0.0, 0.0]},
            index=dates,
        ),
        "ret_1d",
    )

    result = run_long_only_topk(
        scores,
        returns,
        top_k=2,
        rebalance_freq=10,
        min_holding_days=1,
        max_weight=0.5,
        cost_bps=0.0,
    )

    # Day 1 close executes 50/50. After A doubles on day 2, the next day's weights
    # must be 2/3 and 1/3; keeping 50/50 would imply an uncharged rebalance.
    assert result.positions.loc[dates[2], "A"] == 0.5
    assert result.positions.loc[dates[3], "A"] == pytest.approx(2 / 3)
    assert result.positions.loc[dates[3], "B"] == pytest.approx(1 / 3)


def test_held_stock_return_is_kept_when_its_new_score_is_missing() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3, name="date")
    score_frame = pd.DataFrame(
        {"A": [10.0, float("nan"), 10.0], "B": [0.0, 0.0, 0.0]},
        index=dates,
    )
    scores = _panel(score_frame, "score").dropna()
    returns = _panel(
        pd.DataFrame({"A": [0.0, 0.0, 0.10], "B": [0.0, 0.0, 0.0]}, index=dates),
        "ret_1d",
    )

    result = run_long_only_topk(
        scores,
        returns,
        top_k=1,
        rebalance_freq=10,
        min_holding_days=1,
        max_weight=1.0,
        cost_bps=0.0,
    )

    assert result.daily_ret.loc[dates[2]] == pytest.approx(0.10)


def test_missing_score_cross_section_does_not_force_liquidation() -> None:
    dates = pd.bdate_range("2024-01-02", periods=4, name="date")
    score_frame = pd.DataFrame(
        {"A": [10.0, float("nan"), float("nan"), 10.0]},
        index=dates,
    )
    returns = _panel(
        pd.DataFrame({"A": [0.0, 0.0, 0.10, 0.0]}, index=dates),
        "ret_1d",
    )

    result = run_long_only_topk(
        _panel(score_frame, "score").dropna(),
        returns,
        top_k=1,
        rebalance_freq=1,
        min_holding_days=1,
        max_weight=1.0,
        cost_bps=0.0,
    )

    assert result.positions.loc[dates[2], "A"] == pytest.approx(1.0)
    assert result.daily_ret.loc[dates[2]] == pytest.approx(0.10)
    assert result.turnover.loc[dates[2]] == 0.0


def test_held_position_keeps_tail_returns_after_last_valid_score() -> None:
    dates = pd.bdate_range("2024-01-02", periods=6, name="date")
    score_dates = dates[:2]
    scores = _panel(
        pd.DataFrame(
            {"A": [10.0, 0.0], "B": [0.0, 10.0]},
            index=score_dates,
        ),
        "score",
    )
    returns = _panel(
        pd.DataFrame(
            {
                "A": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "B": [0.0, 0.0, 0.0, 0.10, 0.20, 0.30],
            },
            index=dates,
        ),
        "ret_1d",
    )

    result = run_long_only_topk(
        scores,
        returns,
        top_k=1,
        rebalance_freq=1,
        min_holding_days=1,
        max_weight=1.0,
        cost_bps=0.0,
    )

    # Both legitimate signals execute one close later. The return calendar then
    # continues through its own end, while no extra tail rebalance is invented.
    assert_index_equal(result.nav.index, dates)
    assert_index_equal(result.rebalance_dates, dates[[1, 2]])
    assert (result.turnover.loc[dates[3]:] == 0.0).all()
    assert (result.positions.loc[dates[3]:, "B"] == 1.0).all()
    assert_series_equal(
        result.daily_ret,
        pd.Series([0.0, 0.0, 0.0, 0.10, 0.20, 0.30], index=dates),
    )


def test_infeasible_weight_cap_fails_instead_of_hiding_cash() -> None:
    scores, returns, _ = _deterministic_inputs()

    with pytest.raises(ValueError, match="无法组成满仓组合"):
        run_long_only_topk(
            scores,
            returns,
            top_k=10,
            max_weight=0.05,
            cost_bps=0.0,
        )

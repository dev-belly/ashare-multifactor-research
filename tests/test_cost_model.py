"""交易成本模型测试。"""
from __future__ import annotations

import pandas as pd

from factorlab.backtest.cost_model import apply_trading_cost, is_tradable_today


def _w(**kwargs) -> pd.Series:
    return pd.Series(kwargs, dtype=float)


def test_no_trade_has_zero_cost():
    w = _w(A=0.5, B=0.5)
    assert apply_trading_cost(w, w, cost_bps=20.0) == 0.0


def test_full_turnover_cost_matches_formula():
    old = _w(A=1.0, B=0.0)
    new = _w(A=0.0, B=1.0)
    # |Δ| 合计 = 2.0；卖出与买入各收单边 20bps → 2.0 * 20 * 1e-4 = 4e-3
    assert abs(apply_trading_cost(old, new, cost_bps=20.0) - 4e-3) < 1e-12


def test_cost_scales_linearly_with_bps():
    old = _w(A=0.5, B=0.5)
    new = _w(A=0.7, B=0.3)
    c10 = apply_trading_cost(old, new, cost_bps=10.0)
    c30 = apply_trading_cost(old, new, cost_bps=30.0)
    assert abs(c30 - 3 * c10) < 1e-15


def test_cost_is_nonnegative_and_symmetric():
    old = _w(A=0.2, B=0.8)
    new = _w(A=0.6, B=0.4)
    assert apply_trading_cost(old, new) >= 0
    assert abs(apply_trading_cost(old, new) - apply_trading_cost(new, old)) < 1e-15


def test_new_positions_appear_in_cost():
    """权重索引不一致时按并集对齐，新进标的也要计成本。"""
    old = _w(A=1.0)
    new = _w(A=0.5, B=0.5)
    cost = apply_trading_cost(old, new, cost_bps=20.0)
    assert cost > 0


def _quotes():
    dates = pd.date_range("2020-01-01", periods=3)
    return {
        "A": pd.DataFrame(
            {
                "close": [10.0, 11.0, 11.5],
                "is_suspended": [False, False, False],
                "is_limit_up": [False, True, False],
            },
            index=dates,
        ),
        "B": pd.DataFrame(
            {
                "close": [5.0, 5.0, 5.0],
                "is_suspended": [False, True, True],
                "is_limit_up": [False, False, False],
            },
            index=dates,
        ),
    }


def test_tradable_on_normal_day():
    quotes = _quotes()
    assert is_tradable_today("A", pd.Timestamp("2020-01-01"), quotes) is True


def test_limit_up_blocks_buying():
    quotes = _quotes()
    assert is_tradable_today("A", pd.Timestamp("2020-01-02"), quotes) is False


def test_suspended_blocks_trading():
    quotes = _quotes()
    assert is_tradable_today("B", pd.Timestamp("2020-01-03"), quotes) is False
    # 显式允许停牌时可交易
    assert is_tradable_today("B", pd.Timestamp("2020-01-03"), quotes, allow_suspended=True) is True


def test_unknown_code_or_date_not_tradable():
    quotes = _quotes()
    assert is_tradable_today("ZZZ", pd.Timestamp("2020-01-01"), quotes) is False
    assert is_tradable_today("A", pd.Timestamp("1999-01-01"), quotes) is False

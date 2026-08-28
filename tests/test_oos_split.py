"""样本外切分测试：核心是"训练永远不晚于测试"，杜绝前视。"""
from __future__ import annotations

import pandas as pd
import pytest

from factorlab.backtest.oos_split import OOSFold, expanding_window_splits, filter_panel_by_fold


def test_expanding_window_basic_structure():
    folds = expanding_window_splits("2018-01-01", "2023-01-01", train_min_years=2, step_years=1, test_years=1)
    assert len(folds) >= 3, "至少应产生 3 个 fold"
    assert all(isinstance(f, OOSFold) for f in folds)

    ids = [f.fold_id for f in folds]
    assert ids == list(range(len(folds))), "fold_id 必须连续递增"


def test_no_train_test_overlap():
    """训练区间必须严格早于测试区间，且训练终点单调不减。"""
    folds = expanding_window_splits("2018-01-01", "2024-01-01", train_min_years=2, step_years=1, test_years=1)
    prev_train_end = pd.Timestamp("1970-01-01")
    for f in folds:
        assert f.train_end <= f.test_start, (
            f"fold {f.fold_id} 出现前视: train_end={f.train_end} > test_start={f.test_start}"
        )
        assert f.train_end >= prev_train_end, "expanding window 的训练终点必须单调不减"
        assert f.test_start < f.test_end, "每个 fold 的测试窗口必须非空"
        prev_train_end = f.train_end


def test_last_fold_respects_end_boundary():
    end = pd.Timestamp("2022-07-15")
    folds = expanding_window_splits("2018-01-01", end, train_min_years=2, step_years=1, test_years=1)
    assert all(f.test_end <= end for f in folds), "测试窗口不得越过总终点"


def test_unknown_step_freq_raises():
    with pytest.raises(ValueError):
        expanding_window_splits("2018-01-01", "2021-01-01", step_freq="weekly")


def _make_panel(dates, codes):
    idx = pd.MultiIndex.from_product([dates, codes], names=["date", "code"])
    return pd.DataFrame({"f": range(len(idx))}, index=idx)


def test_filter_panel_by_fold_splits_correctly():
    dates = pd.date_range("2020-01-01", periods=40, freq="D")
    panel = _make_panel(dates, ["A", "B"])
    fold = OOSFold(0, dates[0], dates[20], dates[20], dates[30])

    train, test = filter_panel_by_fold(panel, fold)
    train_dates = train.index.get_level_values("date")
    test_dates = test.index.get_level_values("date")

    assert train_dates.max() < fold.test_start
    assert test_dates.min() >= fold.test_start
    assert len(train) + len(test) == 60  # 前 30 天 * 2 只股票


def test_filter_panel_requires_multiindex():
    with pytest.raises(ValueError, match="MultiIndex"):
        filter_panel_by_fold(pd.DataFrame({"a": [1]}), OOSFold(0, pd.Timestamp("2020-01-01"),
                                                               pd.Timestamp("2021-01-01"),
                                                               pd.Timestamp("2021-01-01"),
                                                               pd.Timestamp("2022-01-01")))

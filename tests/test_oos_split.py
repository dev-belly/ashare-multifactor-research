from __future__ import annotations

import pandas as pd
import pytest

from factorlab.backtest.oos_split import OOSFold, expanding_window_splits, filter_panel_by_fold


def test_yearly_expanding_folds_are_non_overlapping() -> None:
    folds = expanding_window_splits(
        "2018-01-01",
        "2022-01-01",
        train_min_years=2,
        step_years=1,
        test_years=1,
        step_freq="yearly",
    )

    assert len(folds) == 2
    assert folds[0].train_end == pd.Timestamp("2020-01-01")
    assert folds[0].test_end == folds[1].test_start
    assert folds[1].train_end == pd.Timestamp("2021-01-01")
    assert folds[0].test_end_inclusive is False
    assert folds[1].test_end_inclusive is True


def test_only_final_fold_includes_configured_end_date() -> None:
    folds = expanding_window_splits("2018-01-01", "2022-01-01", train_min_years=2)
    dates = pd.date_range("2020-12-31", "2022-01-01", freq="D")
    index = pd.MultiIndex.from_product([dates, ["A"]], names=["date", "code"])
    panel = pd.DataFrame({"factor": 1.0}, index=index)

    _, first_test = filter_panel_by_fold(panel, folds[0])
    _, final_test = filter_panel_by_fold(panel, folds[-1])

    assert pd.Timestamp("2021-01-01") not in first_test.index.get_level_values("date")
    assert pd.Timestamp("2021-01-01") in final_test.index.get_level_values("date")
    assert pd.Timestamp("2022-01-01") in final_test.index.get_level_values("date")


def test_unsupported_or_overlapping_oos_windows_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="仅支持 yearly"):
        expanding_window_splits("2018", "2022", step_freq="quarterly")
    with pytest.raises(ValueError, match="不能小于"):
        expanding_window_splits(
            "2018", "2022", step_years=1, test_years=2, step_freq="yearly"
        )


def test_expanding_window_basic_structure() -> None:
    folds = expanding_window_splits(
        "2018-01-01", "2023-01-01", train_min_years=2, step_years=1, test_years=1
    )
    assert len(folds) >= 3
    assert all(isinstance(fold, OOSFold) for fold in folds)
    assert [fold.fold_id for fold in folds] == list(range(len(folds)))


def test_no_train_test_overlap() -> None:
    folds = expanding_window_splits(
        "2018-01-01", "2024-01-01", train_min_years=2, step_years=1, test_years=1
    )
    previous_train_end = pd.Timestamp("1970-01-01")
    for fold in folds:
        assert fold.train_end <= fold.test_start
        assert fold.train_end >= previous_train_end
        assert fold.test_start < fold.test_end
        previous_train_end = fold.train_end


def test_last_fold_respects_end_boundary() -> None:
    end = pd.Timestamp("2022-07-15")
    folds = expanding_window_splits(
        "2018-01-01", end, train_min_years=2, step_years=1, test_years=1
    )
    assert all(fold.test_end <= end for fold in folds)


def _make_panel(dates: pd.DatetimeIndex, codes: list[str]) -> pd.DataFrame:
    index = pd.MultiIndex.from_product([dates, codes], names=["date", "code"])
    return pd.DataFrame({"f": range(len(index))}, index=index)


def test_filter_panel_by_fold_splits_correctly() -> None:
    dates = pd.date_range("2020-01-01", periods=40, freq="D")
    panel = _make_panel(dates, ["A", "B"])
    fold = OOSFold(0, dates[0], dates[20], dates[20], dates[30])

    train, test = filter_panel_by_fold(panel, fold)
    train_dates = train.index.get_level_values("date")
    test_dates = test.index.get_level_values("date")

    assert train_dates.max() < fold.test_start
    assert test_dates.min() >= fold.test_start
    assert len(train) + len(test) == 60


def test_filter_panel_requires_multiindex() -> None:
    fold = OOSFold(
        0,
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2021-01-01"),
        pd.Timestamp("2021-01-01"),
        pd.Timestamp("2022-01-01"),
    )
    with pytest.raises(ValueError, match="MultiIndex"):
        filter_panel_by_fold(pd.DataFrame({"a": [1]}), fold)

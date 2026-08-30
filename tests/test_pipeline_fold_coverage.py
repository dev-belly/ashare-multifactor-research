from __future__ import annotations

import pandas as pd
import pytest

from factorlab.backtest.oos_split import OOSFold
from factorlab import pipeline


class _PassingModel:
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "_PassingModel":
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=X.index, name="score")


class _FailingModel:
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "_FailingModel":
        raise RuntimeError("deliberate fold failure")


def _fold_inputs() -> tuple[pd.DataFrame, pd.Series, list[OOSFold]]:
    dates = pd.bdate_range("2023-01-02", periods=100, name="date")
    codes = ["000001.SZ", "600000.SH"]
    index = pd.MultiIndex.from_product([dates, codes], names=["date", "code"])
    panel = pd.DataFrame({"factor": 1.0}, index=index)
    labels = pd.Series(0.01, index=index, name="y")
    folds = [
        OOSFold(0, dates[0], dates[50], dates[50], dates[60]),
        OOSFold(1, dates[0], dates[70], dates[70], dates[80]),
    ]
    return panel, labels, folds


def test_oos_scores_report_success_failure_and_date_coverage(monkeypatch) -> None:
    panel, labels, folds = _fold_inputs()
    models = iter([_PassingModel(), _FailingModel()])
    monkeypatch.setattr(pipeline, "_build_linear", lambda *_: next(models))

    scores = pipeline.run_oos_scores(
        panel,
        labels,
        folds,
        "elastic_net",
        cfg={},
    )

    coverage = scores.attrs["oos_coverage"]
    assert coverage["requested_fold_count"] == 2
    assert coverage["successful_fold_ids"] == [0]
    assert coverage["failed_fold_ids"] == [1]
    assert coverage["expected_oos_date_count"] == 20
    assert coverage["scored_oos_date_count"] == 10
    assert coverage["oos_date_coverage_ratio"] == 0.5
    assert [fold["status"] for fold in coverage["folds"]] == [
        "success",
        "failed",
    ]
    assert coverage["folds"][1]["reason"] == "model_exception"
    assert "deliberate fold failure" in coverage["folds"][1]["error"]


def test_zero_successful_oos_folds_fail_explicitly(monkeypatch) -> None:
    panel, labels, folds = _fold_inputs()
    monkeypatch.setattr(pipeline, "_build_linear", lambda *_: _FailingModel())

    with pytest.raises(pipeline.OOSScoringError, match="没有成功的 OOS fold") as exc:
        pipeline.run_oos_scores(
            panel,
            labels,
            folds,
            "elastic_net",
            cfg={},
        )

    assert exc.value.coverage["successful_fold_count"] == 0
    assert exc.value.coverage["failed_fold_count"] == 2
    assert exc.value.coverage["oos_date_coverage_ratio"] == 0.0


def test_pipeline_rejects_top_k_that_cannot_be_fully_invested() -> None:
    with pytest.raises(ValueError, match="不会静默保留现金"):
        pipeline.run_pipeline(models="eq_weight", top_k=19)

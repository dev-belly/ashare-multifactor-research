"""Elastic Net：线性正则化模型（结合 L1/L2）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


class ElasticNetModel:
    """截面 Elastic Net 训练 + 预测。"""

    def __init__(
        self,
        alpha_grid: list[float] | None = None,
        l1_ratio_grid: list[float] | None = None,
        max_iter: int = 5000,
    ):
        self.alpha_grid = alpha_grid or [0.001, 0.01, 0.05, 0.1]
        self.l1_ratio_grid = l1_ratio_grid or [0.1, 0.3, 0.5, 0.7]
        self.max_iter = max_iter
        self.model_: ElasticNetCV | None = None
        self.feature_names_: list[str] = []

    def fit(
        self, X: pd.DataFrame, y: pd.Series, min_obs: int = 60
    ) -> ElasticNetModel:
        df = X.join(y.rename("y"), how="inner").dropna()
        if len(df) < min_obs:
            logger.warning("样本不足（%d < %d）", len(df), min_obs)
            return self
        self.feature_names_ = list(X.columns)
        self.model_ = ElasticNetCV(
            l1_ratio=self.l1_ratio_grid,
            alphas=self.alpha_grid,
            cv=5,
            max_iter=self.max_iter,
            random_state=42,
            n_jobs=-1,
        )
        self.model_.fit(df[X.columns].values, df["y"].values)
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if self.model_ is None:
            return pd.Series(np.nan, index=X.index)
        cols = [c for c in self.feature_names_ if c in X.columns]
        Xv = X[cols].values
        return pd.Series(self.model_.predict(Xv), index=X.index, name="score")

    def feature_importance(self) -> pd.DataFrame:
        if self.model_ is None:
            return pd.DataFrame()
        return pd.DataFrame(
            {"coef": self.model_.coef_},
            index=self.feature_names_,
        ).sort_values("coef", key=lambda s: s.abs(), ascending=False)

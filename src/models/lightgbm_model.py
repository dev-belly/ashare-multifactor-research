"""LightGBM：梯度提升树模型用于收益排序。"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from src.utils.common import get_logger

logger = get_logger(__name__)

try:
    import lightgbm as lgb

    HAS_LGB = True
except ImportError:  # 沙盒中可能未装
    HAS_LGB = False
    logger.warning("lightgbm 未安装，将使用 sklearn HistGradientBoosting 兜底")


class LightGBMModel:
    """LightGBM 训练/预测。"""

    def __init__(
        self,
        n_estimators: int = 200,
        learning_rate: float = 0.05,
        num_leaves: int = 31,
        reg_alpha: float = 0.1,
        reg_lambda: float = 0.1,
        random_seed: int = 42,
    ):
        self.params = {
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "reg_alpha": reg_alpha,
            "reg_lambda": reg_lambda,
            "random_state": random_seed,
            "verbose": -1,
        }
        self.model_ = None
        self.feature_importance_: pd.DataFrame = pd.DataFrame()
        self.feature_names_: List[str] = []

    def fit(
        self, X: pd.DataFrame, y: pd.Series, min_obs: int = 60
    ) -> "LightGBMModel":
        df = X.join(y.rename("y"), how="inner").dropna()
        if len(df) < min_obs:
            logger.warning("LightGBM 训练样本不足（%d < %d）", len(df), min_obs)
            return self
        self.feature_names_ = list(X.columns)
        if HAS_LGB:
            self.model_ = lgb.LGBMRegressor(**self.params)
        else:
            from sklearn.ensemble import HistGradientBoostingRegressor

            self.model_ = HistGradientBoostingRegressor(
                max_iter=self.params["n_estimators"],
                learning_rate=self.params["learning_rate"],
                max_leaf_nodes=self.params["num_leaves"],
                l2_regularization=self.params["reg_lambda"],
                random_state=self.params["random_state"],
            )
        self.model_.fit(df[X.columns].values, df["y"].values)

        # feature importance
        if HAS_LGB:
            imp = self.model_.feature_importances_
        else:
            # sklearn 不直接给 permutation importance；用 0 填充
            imp = np.zeros(len(self.feature_names_))
        self.feature_importance_ = pd.DataFrame(
            {"importance": imp}, index=self.feature_names_
        ).sort_values("importance", ascending=False)
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if self.model_ is None:
            return pd.Series(np.nan, index=X.index)
        cols = [c for c in self.feature_names_ if c in X.columns]
        pred = self.model_.predict(X[cols].values)
        return pd.Series(pred, index=X.index, name="score")

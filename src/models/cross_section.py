"""横截面回归（Fama-MacBeth 风格）：每期回归得到因子暴露得分。"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.utils.common import get_logger

logger = get_logger(__name__)


class CrossSectionalRegression:
    """截面回归：每期 t 用 (X_t, y_t) 拟合 y = X @ beta + e。"""

    def __init__(self, method: str = "ols", add_intercept: bool = True):
        self.method = method
        self.add_intercept = add_intercept
        self.coefs_: List[pd.Series] = []
        self.tstats_: List[pd.Series] = []

    def fit(
        self,
        X: pd.DataFrame,  # (date, code) × factors
        y: pd.Series,     # (date, code) → future return
        min_obs: int = 30,
    ) -> "CrossSectionalRegression":
        """逐期回归。"""
        if not isinstance(X.index, pd.MultiIndex) or not isinstance(y.index, pd.MultiIndex):
            raise ValueError("X / y 必须是 (date, code) MultiIndex")
        common = X.index.intersection(y.index)
        X = X.loc[common]
        y = y.loc[common]

        coef_records: List[pd.Series] = []
        t_records: List[pd.Series] = []
        for dt, x_block in X.groupby(level="date"):
            y_block = y.xs(dt, level="date")
            df = x_block.join(y_block.rename("y"), how="inner").dropna()
            if len(df) < min_obs:
                continue
            xx = df[x_block.columns].values
            yy = df["y"].values
            try:
                if self.method == "ols":
                    beta, t = _ols(xx, yy, add_intercept=self.add_intercept)
                else:
                    raise ValueError(f"unsupported method {self.method}")
            except Exception as e:
                logger.debug("fold %s 回归失败: %s", dt, e)
                continue
            names = (
                ["intercept"] + list(x_block.columns) if self.add_intercept else list(x_block.columns)
            )
            coef_records.append(pd.Series(beta, index=names, name=dt))
            t_records.append(pd.Series(t, index=names, name=dt))

        if not coef_records:
            self.coef_df_ = pd.DataFrame()
            self.tstat_df_ = pd.DataFrame()
            return self
        self.coef_df_ = pd.DataFrame(coef_records)
        self.tstat_df_ = pd.DataFrame(t_records)
        return self

    def predict_score(
        self, X: pd.DataFrame, use_avg_coef: bool = True
    ) -> pd.Series:
        """用平均系数（or t 值加权）预测新样本的预期收益。"""
        if use_avg_coef and len(self.coef_df_):
            beta = self.coef_df_.mean(axis=0)
        else:
            beta = self.coef_df_.iloc[-1] if len(self.coef_df_) else None
        if beta is None:
            return pd.Series(np.nan, index=X.index)
        cols = [c for c in X.columns if c in beta.index]
        pred = X[cols].mul(beta[cols], axis=1).sum(axis=1, skipna=True)
        return pred

    def summary(self) -> pd.DataFrame:
        """返回 Fama-MacBeth 风格摘要：mean / std / t-stat of coefs."""
        if not hasattr(self, "coef_df_") or self.coef_df_.empty:
            return pd.DataFrame()
        mean = self.coef_df_.mean()
        std = self.coef_df_.std()
        t = mean / (std / np.sqrt(len(self.coef_df_)) + 1e-12)
        return pd.DataFrame({"mean": mean, "std": std, "t_stat": t})


def _ols(X: np.ndarray, y: np.ndarray, add_intercept: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    if add_intercept:
        X = np.hstack([np.ones((X.shape[0], 1)), X])
    # beta = (X'X)^-1 X'y
    xtx = X.T @ X
    try:
        inv = np.linalg.pinv(xtx)
    except np.linalg.LinAlgError:
        raise
    beta = inv @ X.T @ y
    resid = y - X @ beta
    dof = max(X.shape[0] - X.shape[1], 1)
    sigma2 = (resid @ resid) / dof
    var_beta = np.diag(inv) * sigma2
    se = np.sqrt(np.maximum(var_beta, 0.0))
    t = beta / (se + 1e-12)
    return beta, t

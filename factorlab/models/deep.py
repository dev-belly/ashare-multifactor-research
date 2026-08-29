"""深度学习因子模型（PyTorch MLP）+ Optuna 超参搜索。

设计要点：
    - 横截面监督学习：输入为标准化后的多因子向量，标签为未来持有期收益。
    - 与线性模型（OLS / ElasticNet）互补：可捕获因子间的非线性与交互。
    - 严格在 expanding-window OOS 框架内训练/预测，避免未来函数。
    - 提供 Optuna HPO 入口，可自动搜索网络结构与正则强度。
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from factorlab.utils.common import get_logger

logger = get_logger(__name__)

# 设备选择：默认 CUDA > CPU。MPS 在部分 macOS 环境存在稳定性问题（偶发 SIGSEGV），
# 故默认不启用 MPS；如需可显式设置环境变量 FACTORLAB_DEVICE=mps。
_dev = os.environ.get("FACTORLAB_DEVICE")
if _dev:
    DEVICE = torch.device(_dev)
elif torch.cuda.is_available():
    DEVICE = torch.device("cuda")
else:
    DEVICE = torch.device("cpu")


class _MLP(nn.Module):
    """简单的多层感知机回归器（含 BatchNorm + Dropout）。"""

    def __init__(self, input_dim: int, hidden_dims: List[int], dropout: float):
        super().__init__()
        dims = [input_dim] + list(hidden_dims) + [1]
        layers: List[nn.Module] = []
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2:
                layers.append(nn.BatchNorm1d(dims[i + 1]))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class DeepFactorModel:
    """PyTorch 横截面收益预测模型。

    接口与线性模型一致：fit(X, y) / predict(X) -> pd.Series("score")。
    """

    def __init__(
        self,
        hidden_dims: List[int] = (64, 32),
        dropout: float = 0.2,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        epochs: int = 60,
        batch_size: int = 512,
        patience: int = 10,
        seed: int = 42,
        input_dim: Optional[int] = None,
    ):
        self.hidden_dims = list(hidden_dims)
        self.dropout = dropout
        self.lr = lr
        self.weight_decay = weight_decay
        self.epochs = epochs
        self.batch_size = batch_size
        self.patience = patience
        self.seed = seed
        self.input_dim = input_dim
        self.feature_names_: List[str] = []
        self._net: Optional[_MLP] = None
        self._y_mean = 0.0
        self._y_std = 1.0

    # ---------- 工具 ----------
    @staticmethod
    def _to_tensor(df: pd.DataFrame) -> torch.Tensor:
        arr = df.fillna(0.0).to_numpy(dtype=np.float32)
        return torch.tensor(arr, device=DEVICE)

    def fit(
        self, X: pd.DataFrame, y: pd.Series, min_obs: int = 200
    ) -> "DeepFactorModel":
        df = X.join(y.rename("y"), how="inner").dropna()
        if len(df) < min_obs:
            logger.warning("DeepFactor 训练样本不足（%d < %d），跳过", len(df), min_obs)
            return self
        # The split/batch generators below are seeded, but layer
        # initialisation uses PyTorch's global generator. Seed that generator
        # as well so identical data/configuration produce identical scores.
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        self.feature_names_ = list(X.columns)
        feat = df[X.columns].fillna(0.0)
        target = df["y"].astype(np.float32).to_numpy()
        # 标准化标签，提升训练稳定性
        self._y_mean = float(target.mean())
        self._y_std = float(target.std() + 1e-8)

        rng = torch.Generator().manual_seed(self.seed)
        n = len(feat)
        n_val = max(1, int(0.15 * n))
        idx = torch.randperm(n, generator=rng)
        val_idx, tr_idx = idx[:n_val].to(DEVICE), idx[n_val:].to(DEVICE)

        Xtr = self._to_tensor(feat.iloc[tr_idx.cpu()])
        ytr = torch.tensor(
            (target[tr_idx.cpu()] - self._y_mean) / self._y_std, device=DEVICE
        )
        Xval = self._to_tensor(feat.iloc[val_idx.cpu()])
        yval = torch.tensor(
            (target[val_idx.cpu()] - self._y_mean) / self._y_std, device=DEVICE
        )

        self._net = _MLP(len(self.feature_names_), self.hidden_dims, self.dropout).to(
            DEVICE
        )
        opt = torch.optim.AdamW(
            self._net.parameters(), lr=self.lr, weight_decay=self.weight_decay
        )
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(
            opt, T_max=max(1, self.epochs)
        )
        loss_fn = nn.MSELoss()

        best_loss = float("inf")
        best_state = None
        patience_cnt = 0
        n_batch = max(1, self.batch_size)
        for epoch in range(self.epochs):
            self._net.train()
            perm = torch.randperm(len(Xtr), generator=rng).to(DEVICE)
            for i in range(0, len(Xtr), n_batch):
                b = perm[i : i + n_batch]
                opt.zero_grad()
                pred = self._net(Xtr[b])
                loss = loss_fn(pred, ytr[b])
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self._net.parameters(), 5.0)
                opt.step()
            sched.step()
            # 验证
            self._net.eval()
            with torch.no_grad():
                vpred = self._net(Xval)
                vloss = loss_fn(vpred, yval).item()
            if vloss < best_loss - 1e-6:
                best_loss = vloss
                best_state = {
                    k: v.detach().cpu().clone()
                    for k, v in self._net.state_dict().items()
                }
                patience_cnt = 0
            else:
                patience_cnt += 1
                if patience_cnt >= self.patience:
                    break
        if best_state is not None:
            self._net.load_state_dict(best_state)
        logger.info(
            "DeepFactor 训练完成：epoch=%d best_val_loss=%.6f", epoch + 1, best_loss
        )
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if self._net is None:
            return pd.Series(np.nan, index=X.index, name="score")
        cols = [c for c in self.feature_names_ if c in X.columns]
        self._net.eval()
        with torch.no_grad():
            Xt = self._to_tensor(X[cols])
            pred = self._net(Xt).cpu().numpy().astype(np.float64)
        pred = pred * self._y_std + self._y_mean
        return pd.Series(pred, index=X.index, name="score")


def optimize_deep_hyperparams(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 12,
    seed: int = 42,
) -> Dict[str, object]:
    """Optuna 超参搜索：返回最优超参 dict。

    目标为验证集 RankIC（越高越好），使用 Spearman 相关近似。
    """
    from scipy.stats import spearmanr

    import optuna

    def objective(trial: "optuna.trial.Trial") -> float:
        hidden = [
            trial.suggest_int("h1", 16, 128, step=16),
            trial.suggest_int("h2", 8, 64, step=8),
        ]
        dropout = trial.suggest_float("dropout", 0.0, 0.4)
        lr = trial.suggest_float("lr", 1e-4, 1e-2, log=True)
        weight_decay = trial.suggest_float("weight_decay", 1e-5, 1e-3, log=True)
        batch_size = trial.suggest_categorical("batch_size", [256, 512, 1024])
        model = DeepFactorModel(
            hidden_dims=hidden,
            dropout=dropout,
            lr=lr,
            weight_decay=weight_decay,
            batch_size=batch_size,
            epochs=40,
            seed=seed,
        )
        model.fit(X_train, y_train)
        pred = model.predict(X_val)
        merged = pd.concat([pred.rename("p"), y_val.rename("y")], axis=1).dropna()
        if len(merged) < 30:
            return 0.0
        rho, _ = spearmanr(merged["p"].values, merged["y"].values)
        return float(-rho) if np.isfinite(rho) else 0.0

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(sampler=sampler, direction="minimize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = study.best_params
    # 还原为模型构造参数
    return {
        "hidden_dims": [best["h1"], best["h2"]],
        "dropout": best["dropout"],
        "lr": best["lr"],
        "weight_decay": best["weight_decay"],
        "batch_size": best["batch_size"],
    }

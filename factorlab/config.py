"""类型化配置（pydantic-settings）。

读取 config/config.yaml 并映射为强类型对象，供 CLI / API / 流水线校验与消费。
保留对旧字典式配置的兼容（factorlab.utils.common.load_config）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field

from factorlab.utils.common import PROJECT_ROOT


class DataSettings(BaseModel):
    source: str = "synthetic"
    start_date: str = "2018-01-01"
    end_date: str = "2025-12-31"
    benchmark: str = "000300.SH"
    universe: str = "all"
    fallback_synthetic: bool = True
    cache_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    factor_dir: str = "data/factors"


class FactorSettings(BaseModel):
    standardize: str = "zscore"
    winsorize: float = 0.01
    industry_neutral: bool = True
    st_filter: bool = True
    suspended_filter: bool = True
    financial_lag_days: int = 90


class BacktestSettings(BaseModel):
    oos_window: str = "quarterly"
    train_min_years: int = 2
    step_years: int = 1
    test_years: int = 1


class ModelSettings(BaseModel):
    cross_section: Dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "method": "ols"})
    sort_portfolio: Dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "n_groups": 5, "weighting": "equal"})
    elastic_net: Dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "alpha_grid": [0.001, 0.01, 0.05, 0.1], "l1_ratio_grid": [0.1, 0.3, 0.5, 0.7]})
    lightgbm: Dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "n_estimators": 200, "learning_rate": 0.05, "num_leaves": 31, "reg_alpha": 0.1, "reg_lambda": 0.1})
    deep: Dict[str, Any] = Field(default_factory=lambda: {"enabled": True, "hidden_dims": [64, 32], "dropout": 0.2, "lr": 1e-3, "weight_decay": 1e-4, "epochs": 60, "batch_size": 512})


class EvalSettings(BaseModel):
    ic_methods: List[str] = Field(default_factory=lambda: ["pearson", "spearman"])
    deciles: int = 5
    cost_scenarios_bps: List[float] = Field(default_factory=lambda: [0, 10, 20, 30])
    robustness: Dict[str, Any] = Field(default_factory=lambda: {"by_cap": True, "by_industry": True, "by_regime": True})
    regime: Dict[str, Any] = Field(default_factory=lambda: {"bull_threshold": 0.20})


class OutputSettings(BaseModel):
    log_dir: str = "outputs/logs"
    result_dir: str = "outputs/results"
    figure_dir: str = "outputs/figures"
    save_format: List[str] = Field(default_factory=lambda: ["parquet", "csv"])


class VisualizationSettings(BaseModel):
    style: str = "seaborn-v0_8-whitegrid"
    palette: str = "Set2"
    fig_dir: str = "outputs/figures"


class Settings(BaseModel):
    data: DataSettings = Field(default_factory=DataSettings)
    factors: FactorSettings = Field(default_factory=FactorSettings)
    backtest: BacktestSettings = Field(default_factory=BacktestSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    evaluation: EvalSettings = Field(default_factory=EvalSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    visualization: VisualizationSettings = Field(default_factory=VisualizationSettings)
    random_seed: int = 42

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Settings":
        path = Path(path) if path else (PROJECT_ROOT / "config" / "config.yaml")
        path = Path(path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(**raw)

    def as_dict(self) -> Dict[str, Any]:
        return self.model_dump()

"""端到端流水线编排：数据 → 因子 → 模型(OOS) → 回测 → 评估 → JSON。

产出 outputs/results/results.json（供 FastAPI / 前端消费）。
严格保持 expanding-window 样本外框架与财报 lag 防泄漏逻辑。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from factorlab.backtest.engine import make_ret_panel, run_long_only_topk
from factorlab.backtest.oos_split import expanding_window_splits, filter_panel_by_fold
from factorlab.data.akshare_loader import AkShareLoader
from factorlab.data.processor import align_to_calendar, basic_clean
from factorlab.evaluation.ic import (
    factor_return_decay,
    multi_factor_ic_table,
)
from factorlab.evaluation.returns import perf_stats
from factorlab.evaluation.robustness import market_regime_label, robustness_by_regime
from factorlab.evaluation.turnover import turnover_stats
from factorlab.factors.engineering import build_factor_panel, default_factor_registry
from factorlab.models.cross_section import CrossSectionalRegression
from factorlab.models.deep import DeepFactorModel, optimize_deep_hyperparams
from factorlab.models.elastic_net import ElasticNetModel
from factorlab.models.lightgbm_model import LightGBMModel
from factorlab.models.sort_portfolio import SortPortfolio
from factorlab.utils.common import ensure_dir, get_logger, load_config
from factorlab.utils.serialization import json_safe

logger = get_logger("pipeline")

SUPPORTED_MODELS = {
    "eq_weight",
    "elastic_net",
    "lightgbm",
    "deep",
    "cross_section",
}
LABEL_HORIZON = 21


# ========== 通用序列化 ==========
def _series_to_json(s: pd.Series) -> Dict[str, list]:
    s = s.dropna()
    dates = [d.strftime("%Y-%m-%d") for d in s.index]
    return {"dates": dates, "values": [round(float(v), 6) for v in s.values]}


def _returns_to_nav(returns: pd.Series) -> pd.Series:
    """Compound a return series with an explicit initial capital point."""
    clean = returns.dropna().sort_index()
    if clean.empty:
        return pd.Series(dtype=float)
    base_date = pd.Timestamp(clean.index[0]) - pd.Timedelta(days=1)
    compounded = (1.0 + clean).cumprod()
    return pd.concat([pd.Series([1.0], index=[base_date]), compounded])


def _cols(panel: pd.DataFrame) -> List[str]:
    return [c for c in panel.columns if c not in {"industry", "is_suspended"}]


def _forward_return_panel(
    realized_returns: pd.DataFrame, periods: int = 1
) -> pd.DataFrame:
    """Align each symbol's future realised return to the factor-observation date.

    ``realized_returns.loc[(t, code)]`` is the close-to-close return ending at
    ``t``.  Research at ``t`` must therefore use the value from ``t + periods``.
    Sorting within symbol and shifting inside the group prevents values at one
    symbol's boundary from leaking into another symbol.
    """
    if periods <= 0:
        raise ValueError("periods must be positive")
    if not isinstance(realized_returns.index, pd.MultiIndex):
        raise TypeError("realized_returns must use a (date, code) MultiIndex")
    if "ret_1d" not in realized_returns.columns:
        raise KeyError("realized_returns must contain ret_1d")

    ordered = realized_returns["ret_1d"].sort_index(level=["code", "date"])
    forward = ordered.groupby(level="code", sort=False).shift(-periods)
    forward.name = "ret_1d"
    return forward.to_frame().sort_index()


def _forward_compound_return(
    realized_returns: pd.Series, horizon: int = 21
) -> pd.Series:
    """Compound returns from T+1 through T+horizon independently per symbol."""
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if not isinstance(realized_returns.index, pd.MultiIndex):
        raise TypeError("realized_returns must use a (date, code) MultiIndex")

    ordered = realized_returns.sort_index(level=["code", "date"])

    def _per_symbol(series: pd.Series) -> pd.Series:
        trailing = (1.0 + series).rolling(horizon, min_periods=horizon).apply(
            np.prod, raw=True
        ) - 1.0
        # The rolling value ending at T+horizon consists exactly of the daily
        # returns T+1, ..., T+horizon.
        return trailing.shift(-horizon)

    forward = ordered.groupby(level="code", sort=False).transform(_per_symbol)
    forward = forward.sort_index()
    forward.name = f"fwd_ret_{horizon}d"
    return forward


def _purge_training_label_overlap(
    train_index: pd.MultiIndex,
    all_dates: pd.DatetimeIndex,
    test_start: pd.Timestamp,
    horizon: int = LABEL_HORIZON,
) -> pd.MultiIndex:
    """Remove training observations whose forward label reaches the test fold.

    A label observed on trading date ``T`` compounds returns ``T+1 .. T+h``.
    The last ``h`` trading dates before a fold therefore cannot be used for
    training: their target contains returns from the nominal OOS interval.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if not isinstance(train_index, pd.MultiIndex):
        raise TypeError("train_index must be a (date, code) MultiIndex")

    calendar = pd.DatetimeIndex(all_dates).drop_duplicates().sort_values()
    test_pos = int(calendar.searchsorted(pd.Timestamp(test_start), side="left"))
    first_excluded_pos = test_pos - horizon
    if first_excluded_pos <= 0:
        return train_index[:0]
    first_excluded_date = calendar[first_excluded_pos]
    keep = train_index.get_level_values("date") < first_excluded_date
    return train_index[keep]


# ========== 数据准备 ==========
def prepare_data(cfg: dict, *, include_metadata: bool = False) -> tuple:
    data_cfg = cfg["data"]
    allow_fallback = data_cfg.get(
        "allow_fallback", data_cfg.get("fallback_synthetic", False)
    )
    loader = AkShareLoader(
        source=data_cfg["source"],
        cache_dir=data_cfg["cache_dir"],
        universe=data_cfg.get("universe", "all"),
        max_symbols=data_cfg.get("max_symbols", AkShareLoader.DEFAULT_MAX_SYMBOLS),
        allow_fallback=allow_fallback,
        allow_partial_real_data=data_cfg.get("allow_partial_real_data", False),
    )
    quotes, fins, ind, cal = loader.load_all(
        start_date=data_cfg["start_date"], end_date=data_cfg["end_date"]
    )
    quotes = basic_clean(quotes)
    quotes = align_to_calendar(quotes, cal)
    if include_metadata:
        return quotes, fins, ind, cal, loader.metadata
    return quotes, fins, ind, cal


# ========== 模型训练/预测 ==========
def _build_linear(name: str, cfg: dict):
    if name == "elastic_net":
        return ElasticNetModel()
    if name == "lightgbm":
        m = cfg["models"]["lightgbm"]
        return LightGBMModel(
            n_estimators=m.get("n_estimators", 200),
            learning_rate=m.get("learning_rate", 0.05),
            num_leaves=m.get("num_leaves", 31),
            reg_alpha=m.get("reg_alpha", 0.1),
            reg_lambda=m.get("reg_lambda", 0.1),
        )
    if name == "cross_section":
        return CrossSectionalRegression(
            method=cfg["models"]["cross_section"].get("method", "ols")
        )
    raise ValueError(name)


def _deep_params(cfg: dict) -> dict:
    d = cfg["models"]["deep"]
    return {
        "hidden_dims": d.get("hidden_dims", [64, 32]),
        "dropout": d.get("dropout", 0.2),
        "lr": d.get("lr", 1e-3),
        "weight_decay": d.get("weight_decay", 1e-4),
        "epochs": d.get("epochs", 60),
        "batch_size": d.get("batch_size", 512),
    }


def run_oos_scores(
    panel: pd.DataFrame,
    ret_21d: pd.Series,
    folds,
    model_name: str,
    cfg: dict,
    hpo_trials: int = 0,
) -> pd.Series:
    factor_cols = _cols(panel)
    all_dates = pd.DatetimeIndex(
        panel.index.get_level_values("date").unique()
    ).sort_values()
    scores: List[pd.Series] = []
    deep_params = None

    for fold in folds:
        train, test = filter_panel_by_fold(panel, fold)
        if train.empty or test.empty:
            continue
        train_X = train[factor_cols]
        train_y_full = ret_21d.reindex(train.index)
        common = train_X.index.intersection(train_y_full.dropna().index)
        common = common.intersection(
            _purge_training_label_overlap(
                common,
                all_dates,
                fold.test_start,
                horizon=LABEL_HORIZON,
            )
        )
        train_X = train_X.loc[common]
        train_y = train_y_full.loc[common]
        test_X = test[factor_cols]
        if len(train_y) < 30:
            continue

        try:
            if model_name == "eq_weight":
                score = test_X.mean(axis=1, skipna=True)
                score.name = "score"
            elif model_name == "deep":
                if deep_params is None and hpo_trials and hpo_trials > 0:
                    # 仅在首个 fold 做一次 HPO（用其训练集切出验证集）
                    n = len(train_X)
                    val_n = max(1, int(0.2 * n))
                    idx = np.random.RandomState(cfg.get("random_seed", 42)).permutation(
                        n
                    )
                    tr, va = idx[val_n:], idx[:val_n]
                    best = optimize_deep_hyperparams(
                        train_X.iloc[tr],
                        train_y.iloc[tr],
                        train_X.iloc[va],
                        train_y.iloc[va],
                        n_trials=hpo_trials,
                        seed=cfg.get("random_seed", 42),
                    )
                    deep_params = best
                    logger.info("Deep HPO 最佳超参: %s", best)
                params = deep_params or _deep_params(cfg)
                model = DeepFactorModel(**params, seed=cfg.get("random_seed", 42))
                model.fit(train_X, train_y)
                score = model.predict(test_X)
            else:
                model = _build_linear(model_name, cfg)
                model.fit(train_X, train_y)
                if model_name == "cross_section":
                    score = model.predict_score(test_X)
                else:
                    score = model.predict(test_X)
                score = score.rename("score")
        except Exception as e:
            logger.warning("fold %d / %s 失败: %s", fold.fold_id, model_name, e)
            continue

        if isinstance(score.index, pd.MultiIndex):
            score.index.set_names(["date", "code"], inplace=True)
        scores.append(score)

    if not scores:
        return pd.Series(dtype=float, name="score")
    out = pd.concat(scores)
    if isinstance(out.index, pd.MultiIndex):
        out.index.set_names(["date", "code"], inplace=True)
    return out


# ========== 主入口 ==========
def run_pipeline(
    config_path: Optional[str] = None,
    models: str = "eq_weight,elastic_net,lightgbm,deep",
    top_k: int = 20,
    rebal_freq: int = 21,
    cost_bps: float = 20.0,
    data_source: Optional[str] = None,
    hpo_trials: Optional[int] = None,
) -> Path:
    cfg = load_config(config_path)
    if data_source:
        cfg["data"]["source"] = data_source
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    unknown_models = sorted(set(model_list).difference(SUPPORTED_MODELS))
    if unknown_models:
        raise ValueError(f"不支持的模型: {', '.join(unknown_models)}")
    if not model_list:
        raise ValueError("至少选择一个模型")
    if top_k <= 0 or rebal_freq <= 0 or cost_bps < 0:
        raise ValueError("top_k/rebal_freq 必须为正数，cost_bps 不能为负")

    deep_cfg = cfg["models"].get("deep", {})
    if hpo_trials is None:
        hpo_trials = int(deep_cfg.get("hpo_trials", 0))
    if "deep" not in model_list and hpo_trials:
        hpo_trials = 0

    result_dir = ensure_dir(cfg["output"]["result_dir"])
    logger.info(
        "流水线启动：models=%s top_k=%d cost_bps=%.1f", model_list, top_k, cost_bps
    )

    # 1) 数据
    quotes, fins, ind, cal, data_meta = prepare_data(cfg, include_metadata=True)

    # 2) 因子面板
    registry = default_factor_registry()
    panel = build_factor_panel(
        quotes,
        fins,
        ind,
        registry,
        lag_days=cfg["factors"]["financial_lag_days"],
        winsorize_q=cfg["factors"]["winsorize"],
        standardize=cfg["factors"]["standardize"],
        do_industry_neutral=cfg["factors"]["industry_neutral"],
    )
    if panel.empty:
        raise RuntimeError("因子面板为空，请检查数据源")
    factor_cols = _cols(panel)
    logger.info("因子面板：%d 行 × %d 因子", len(panel), len(factor_cols))

    # 3) 收益面板 + 标签（未来 21 日累计收益）
    ret_panel = make_ret_panel(quotes, horizon=1, use_fwd=False)
    ret_panel.index.set_names(["date", "code"], inplace=True)
    ret_21d = _forward_compound_return(ret_panel["ret_1d"], horizon=LABEL_HORIZON)
    ret_21d.name = "y"

    # IC / 分组必须使用下一交易日收益；回测仍消费按发生日记录的收益。
    fwd_ret_panel = _forward_return_panel(ret_panel, periods=1)
    # 4) OOS 折
    folds = expanding_window_splits(
        start=cfg["data"]["start_date"],
        end=cfg["data"]["end_date"],
        train_min_years=cfg["backtest"]["train_min_years"],
        step_years=cfg["backtest"]["step_years"],
        test_years=cfg["backtest"]["test_years"],
        step_freq=cfg["backtest"]["oos_window"],
    )
    logger.info("OOS 折数：%d", len(folds))
    if not folds:
        raise RuntimeError("配置未产生任何样本外 fold")

    # IC、分组和衰减只在各 fold 的测试区间计算，避免训练期诊断被写成
    # 样本外证据。衰减用 outer join 保留完整收益日历，防止有间隔的 OOS
    # fold 被 shift(-lag) 错当成相邻交易日。
    panel_dates = panel.index.get_level_values("date")
    oos_mask = pd.Series(False, index=panel.index)
    for fold in folds:
        test_end_mask = (
            panel_dates <= fold.test_end
            if fold.test_end_inclusive
            else panel_dates < fold.test_end
        )
        oos_mask |= (panel_dates >= fold.test_start) & test_end_mask
    oos_factor_panel = panel.loc[oos_mask.to_numpy()]
    if oos_factor_panel.empty:
        raise RuntimeError("样本外测试区间没有因子观测")
    ic_panel = oos_factor_panel.join(fwd_ret_panel, how="left")
    decay_panel = oos_factor_panel.join(ret_panel[["ret_1d"]], how="outer").sort_index()

    # 5) 模型分数 + 回测
    final_scores: Dict[str, pd.Series] = {}
    for m in model_list:
        s = run_oos_scores(panel, ret_21d, folds, m, cfg, hpo_trials=hpo_trials)
        if s.empty:
            logger.warning("模型 %s 无可用分数", m)
            continue
        final_scores[m] = s.dropna()

    bt_results: Dict[str, dict] = {}
    reference_dates: pd.DatetimeIndex | None = None
    cost_scenarios = {float(c): {} for c in cfg["evaluation"]["cost_scenarios_bps"]}
    for m, score in final_scores.items():
        score_panel = score.to_frame("score")
        # 主成本曲线
        bt = run_long_only_topk(
            score_panel,
            ret_panel,
            top_k=top_k,
            rebalance_freq=rebal_freq,
            cost_bps=cost_bps,
        )
        if reference_dates is None:
            reference_dates = bt.nav.index
        perf = perf_stats(bt.nav)
        perf["model"] = m
        to = turnover_stats(bt.turnover)
        bt_results[m] = {"nav": _series_to_json(bt.nav), "perf": perf, "turnover": to}
        # 成本敏感性
        for c in cost_scenarios:
            btc = run_long_only_topk(
                score_panel,
                ret_panel,
                top_k=top_k,
                rebalance_freq=rebal_freq,
                cost_bps=c,
            )
            cost_scenarios[c][m] = perf_stats(btc.nav)
        logger.info(
            "模型 %s：年化=%.3f Sharpe=%.3f 回撤=%.3f",
            m,
            perf["annual_return"],
            perf["sharpe"],
            perf["max_drawdown"],
        )

    if not bt_results:
        raise RuntimeError("所有模型均未产生可用的样本外结果")

    successful_models = list(bt_results)
    # 同期全股票等权、无交易成本基准。合成数据本身可能具有较高市场漂移，
    # 不展示基准会把 beta 收益误写成因子 alpha。
    if reference_dates is None or reference_dates.empty:
        raise RuntimeError("样本外回测没有可用于基准对齐的日期")
    benchmark_nav = _benchmark_nav(quotes).reindex(reference_dates).dropna()
    if benchmark_nav.empty or benchmark_nav.iloc[0] == 0:
        raise RuntimeError("同期等权基准为空或初始净值无效")
    benchmark_nav = benchmark_nav / benchmark_nav.iloc[0]
    bt_results = {
        "benchmark": {
            "nav": _series_to_json(benchmark_nav),
            "perf": {**perf_stats(benchmark_nav), "model": "benchmark"},
            "turnover": {
                "avg": 0.0,
                "median": 0.0,
                "max": 0.0,
                "n_rebalances": 0,
                "annualized": 0.0,
            },
        },
        **bt_results,
    }

    # 6) IC 表
    ic_table = multi_factor_ic_table(
        ic_panel, factor_cols, methods=cfg["evaluation"]["ic_methods"]
    )
    ic_records = ic_table.to_dict(orient="records")

    # 7) 分组组合（取 Top 因子）
    top_factors = _top_factors_by_ir(ic_table, k=6)
    sp = SortPortfolio(n_groups=cfg["evaluation"]["deciles"], weighting="equal")
    group_data: Dict[str, dict] = {}
    for f in top_factors:
        try:
            gr = sp.backtest(oos_factor_panel, fwd_ret_panel, factor_col=f)
            ls = sp.long_short_spread(gr)
            ls_nav = _returns_to_nav(ls)
            ls_stats = perf_stats(ls_nav)
            ls_stats["factor"] = f
            grp_navs = {c: _series_to_json(_returns_to_nav(gr[c])) for c in gr.columns}
            group_data[f] = {
                "groups": grp_navs,
                "long_short": _series_to_json(ls_nav),
                "ls_stats": ls_stats,
            }
        except Exception as e:
            logger.warning("分组 %s 失败: %s", f, e)

    # 8) 因子衰减（Top 因子）
    decay_data: Dict[str, list] = {}
    for f in top_factors:
        try:
            decay_data[f] = factor_return_decay(decay_panel, f, max_lag=20).to_dict(
                orient="records"
            )
        except Exception as exc:
            logger.warning("因子衰减 %s 失败: %s", f, exc)

    # 9) 稳健性（市场阶段）—— 以等权基准构建 regime
    bench_nav = _benchmark_nav(quotes)
    regime = market_regime_label(
        bench_nav, bull_threshold=cfg["evaluation"]["regime"]["bull_threshold"]
    )
    robustness: Dict[str, dict] = {}
    for m, res in bt_results.items():
        nav = pd.Series(res["nav"]["values"], index=pd.to_datetime(res["nav"]["dates"]))
        rb = robustness_by_regime(nav, regime)
        if not rb.empty:
            robustness[m] = {r: rb.loc[r].to_dict() for r in rb.index}

    # 10) 特征重要性（LightGBM 若有）
    feature_importance: Dict[str, list] = {}
    if "lightgbm" in final_scores and final_scores["lightgbm"] is not None:
        try:
            train_all, _ = filter_panel_by_fold(panel, folds[0])
            importance_index = train_all.index.intersection(
                ret_21d.reindex(train_all.index).dropna().index
            )
            importance_index = importance_index.intersection(
                _purge_training_label_overlap(
                    importance_index,
                    pd.DatetimeIndex(
                        panel.index.get_level_values("date").unique()
                    ).sort_values(),
                    folds[0].test_start,
                    horizon=LABEL_HORIZON,
                )
            )
            lgb = LightGBMModel()
            lgb.fit(
                train_all.loc[importance_index, factor_cols],
                ret_21d.loc[importance_index],
            )
            if not lgb.feature_importance_.empty:
                feature_importance["lightgbm"] = (
                    lgb.feature_importance_.reset_index()
                    .rename(columns={"index": "factor"})
                    .to_dict(orient="records")
                )
        except Exception as e:
            logger.warning("特征重要性提取失败: %s", e)

    # 11) 汇总写出
    actual_data_source = data_meta.get("actual_data_source") or cfg["data"]["source"]
    meta = {
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        # data_source remains the UI-facing field, but now reflects reality.
        "data_source": actual_data_source,
        "requested_data_source": data_meta.get(
            "requested_data_source", cfg["data"]["source"]
        ),
        "actual_data_source": actual_data_source,
        "fallback_reason": data_meta.get("fallback_reason"),
        "data_load": data_meta,
        "start_date": cfg["data"]["start_date"],
        "end_date": cfg["data"]["end_date"],
        "universe_size": int(panel.index.get_level_values("code").nunique()),
        "n_factors": len(factor_cols),
        "factor_names": factor_cols,
        "models": successful_models,
        "requested_models": model_list,
        "top_k": top_k,
        "rebal_freq": rebal_freq,
        "cost_bps": cost_bps,
        "cost_scenarios_bps": [float(c) for c in cost_scenarios.keys()],
        "n_folds": len(folds),
        "label_horizon_days": LABEL_HORIZON,
        "execution_lag_days": 1,
        "diagnostic_scope": "oos_test_dates",
        "diagnostic_start": oos_factor_panel.index.get_level_values("date").min(),
        "diagnostic_end": oos_factor_panel.index.get_level_values("date").max(),
        "hpo_trials": hpo_trials,
        "deep_enabled": "deep" in successful_models,
    }
    results = json_safe(
        {
            "meta": meta,
            "model_nav": bt_results,
            "cost_scenarios": {str(k): v for k, v in cost_scenarios.items()},
            "ic_summary": ic_records,
            "group_returns": group_data,
            "factor_decay": decay_data,
            "robustness": robustness,
            "feature_importance": feature_importance,
        }
    )
    out_path = result_dir / "results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, allow_nan=False)
    logger.info("✔ 结果已写出：%s", out_path)
    return out_path


# ========== 辅助 ==========
def _top_factors_by_ir(ic_table: pd.DataFrame, k: int = 6) -> List[str]:
    if ic_table.empty or "ir" not in ic_table.columns:
        return []
    sub = ic_table[ic_table["method"] == "spearman"].dropna(subset=["ir"])
    if sub.empty:
        return []
    ordered = sub.reindex(sub["ir"].abs().sort_values(ascending=False).index)
    return ordered["factor"].head(k).tolist()


def _benchmark_nav(quotes: dict) -> pd.Series:
    all_close = pd.concat({c: d["close"] for c, d in quotes.items()}, axis=1)
    return (1 + all_close.pct_change().mean(axis=1).fillna(0)).cumprod()


if __name__ == "__main__":
    run_pipeline()

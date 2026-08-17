"""03_run_backtest.py：expanding-window OOS + 模型训练 + 回测。"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest.engine import (
    BacktestResult,
    make_ret_panel,
    run_long_only_topk,
)
from src.backtest.oos_split import expanding_window_splits, filter_panel_by_fold
from src.models.cross_section import CrossSectionalRegression
from src.models.elastic_net import ElasticNetModel
from src.models.lightgbm_model import LightGBMModel
from src.utils.common import ensure_dir, get_logger, load_config, PROJECT_ROOT

logger = get_logger("backtest")


def _build_model(name: str) -> object:
    if name == "elastic_net":
        return ElasticNetModel()
    if name == "lightgbm":
        return LightGBMModel()
    if name == "cross_section":
        return CrossSectionalRegression(method="ols")
    raise ValueError(f"unknown model: {name}")


def _train_eq_weight(test_X: pd.DataFrame) -> pd.Series:
    """等权因子 → score（无训练的基准）。"""
    cols = list(test_X.columns)
    s = test_X[cols].mean(axis=1, skipna=True)
    s.name = "score"
    return s


def _train_predict(
    name: str,
    train_X: pd.DataFrame,
    train_y: pd.Series,
    test_X: pd.DataFrame,
) -> pd.Series:
    model = _build_model(name)
    model.fit(train_X, train_y)
    if name == "cross_section":
        return model.predict_score(test_X).rename("score")
    return model.predict(test_X).rename("score")


def _ensure_multiindex(series: pd.Series, default_names=("date", "code")) -> pd.Series:
    """确保 Series 拥有命名的 MultiIndex。"""
    if series is None or len(series) == 0:
        return series
    if not isinstance(series.index, pd.MultiIndex):
        return series
    if any(n is None for n in series.index.names):
        series = series.copy()
        new_names = []
        for i, n in enumerate(series.index.names):
            new_names.append(default_names[i] if n is None else n)
        series.index.set_names(new_names, inplace=True)
    return series


def _concat_preserving_names(prev: pd.Series, new: pd.Series) -> pd.Series:
    """拼接两个 Series 后保持 MultiIndex 命名。"""
    prev = _ensure_multiindex(prev)
    new = _ensure_multiindex(new)
    out = pd.concat([prev, new])
    if isinstance(out.index, pd.MultiIndex):
        out.index.set_names(["date", "code"], inplace=True)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "config.yaml"))
    parser.add_argument("--panel", default=None)
    parser.add_argument(
        "--models", default="eq_weight,elastic_net,lightgbm",
        help="comma-separated: eq_weight | elastic_net | lightgbm | cross_section",
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--rebal-freq", type=int, default=21)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    factor_dir = ensure_dir(cfg["data"]["factor_dir"])
    result_dir = ensure_dir(cfg["output"]["result_dir"])
    panel_path = Path(args.panel) if args.panel else factor_dir / "factor_panel.parquet"

    # 加载因子面板
    if panel_path.suffix == ".parquet":
        panel = pd.read_parquet(panel_path)
    else:
        panel = pd.read_csv(panel_path, parse_dates=["date"])
    if "date" in panel.columns and "code" in panel.columns:
        panel = panel.set_index(["date", "code"])
    if not isinstance(panel.index, pd.MultiIndex):
        raise ValueError("panel 必须是 (date, code) MultiIndex")
    panel.index.set_names(["date", "code"], inplace=True)
    panel = panel.sort_index()
    factor_cols = [c for c in panel.columns if c not in {"industry", "is_suspended"}]

    # 加载行情
    with open(Path(cfg["data"]["processed_dir"]) / "processed.pkl", "rb") as f:
        proc = pickle.load(f)
    quotes = proc["quotes"]
    ret_panel = make_ret_panel(quotes, horizon=1, use_fwd=False)
    ret_panel.index.set_names(["date", "code"], inplace=True)

    # 未来 21 日累计收益作为训练标签（行业惯例）
    ret_21d = (
        ret_panel["ret_1d"]
        .groupby(level="code")
        .transform(lambda s: (1.0 + s).rolling(21, min_periods=5).apply(np.prod, raw=True) - 1.0)
        .shift(-21)
    )
    ret_21d.name = "y"

    # 切 OOS 折
    folds = expanding_window_splits(
        start=cfg["data"]["start_date"],
        end=cfg["data"]["end_date"],
        train_min_years=cfg["backtest"]["train_min_years"],
        step_years=cfg["backtest"]["step_years"],
        test_years=cfg["backtest"]["test_years"],
        step_freq=cfg["backtest"]["oos_window"],
    )

    scores: dict[str, list] = {m: [] for m in args.models.split(",")}

    for fold in folds:
        train, test = filter_panel_by_fold(panel, fold)
        if train.empty or test.empty:
            continue
        train_X = train[factor_cols]
        train_y_full = ret_21d.reindex(train.index)
        train_X = train_X.dropna(how="all")
        common = train_X.index.intersection(train_y_full.dropna().index)
        train_X = train_X.loc[common]
        train_y = train_y_full.loc[common]
        test_X = test[factor_cols]
        if len(train_y) < 30:
            logger.info("fold %d 训练样本不足（%d）", fold.fold_id, len(train_y))
            continue

        for m in args.models.split(","):
            try:
                if m == "eq_weight":
                    score = _train_eq_weight(test_X)
                elif m in {"elastic_net", "lightgbm", "cross_section"}:
                    score = _train_predict(m, train_X, train_y, test_X)
                else:
                    logger.warning("未知模型: %s", m)
                    continue
                score = _ensure_multiindex(score)
                scores[m].append(score)
            except Exception as e:
                logger.warning("fold %d, model %s 训练失败: %s", fold.fold_id, m, e)

    # 合并每模型的全部 fold 分数
    final_scores: dict[str, pd.Series] = {}
    for m, lst in scores.items():
        if not lst:
            continue
        s = pd.concat(lst)
        if isinstance(s.index, pd.MultiIndex):
            s.index.set_names(["date", "code"], inplace=True)
        final_scores[m] = s

    # 回测
    bt_results: dict[str, BacktestResult] = {}
    ret_panel.index.set_names(["date", "code"], inplace=True)

    for m, score in final_scores.items():
        if score.empty:
            continue
        score = _ensure_multiindex(score)
        score_panel = score.dropna().to_frame("score")
        common = score_panel.index.intersection(ret_panel.index)
        score_panel = score_panel.loc[common]
        rp = ret_panel.loc[common]
        try:
            bt = run_long_only_topk(
                score_panel=score_panel,
                returns_panel=rp,
                top_k=args.top_k,
                rebalance_freq=args.rebal_freq,
                cost_bps=args.cost_bps,
            )
            bt_results[m] = bt
            bt.nav.to_frame().to_csv(result_dir / f"nav_{m}.csv")
            logger.info(
                "model %s: final_nav=%.4f  rebal=%d  avg_n=%d",
                m,
                bt.nav.iloc[-1],
                int((bt.turnover > 0).sum()),
                int(bt.n_stocks_avg),
            )
        except Exception as e:
            logger.error("回测 %s 失败: %s", m, e)

    if bt_results:
        rows = []
        for m, bt in bt_results.items():
            rebal_n = int((bt.turnover > 0).sum())
            avg_to = (
                float(bt.turnover[bt.turnover > 0].mean())
                if (bt.turnover > 0).any()
                else 0.0
            )
            rows.append(
                {
                    "model": m,
                    "n_rebalances": rebal_n,
                    "avg_turnover": avg_to,
                    "final_nav": float(bt.nav.iloc[-1]),
                    "n_stocks_avg": float(bt.n_stocks_avg),
                }
            )
        comp = pd.DataFrame(rows)
        comp.to_csv(result_dir / "model_comparison.csv", index=False)
        print("\n✔ 模型对比：")
        print(comp.to_string(index=False))
    else:
        print("⚠️ 没有产生可对比的回测结果")


if __name__ == "__main__":
    main()

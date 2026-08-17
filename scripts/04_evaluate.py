"""04_evaluate.py：评估 IC、分组收益、换手、回撤、稳健性、出图。"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from src.evaluation.ic import calc_ic_series, ic_summary, multi_factor_ic_table
from src.evaluation.returns import perf_stats
from src.evaluation.robustness import (
    market_regime_label,
    robustness_by_industry,
    robustness_by_regime,
)
from src.evaluation.turnover import turnover_stats
from src.models.sort_portfolio import SortPortfolio
from src.utils.common import ensure_dir, get_logger, load_config, PROJECT_ROOT
from src.visualization import plots as plt_mod

logger = get_logger("evaluate")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "config.yaml"))
    parser.add_argument("--panel", default=None, help="因子面板 parquet")
    args = parser.parse_args()

    cfg = load_config(args.config)
    factor_dir = ensure_dir(cfg["data"]["factor_dir"])
    result_dir = ensure_dir(cfg["output"]["result_dir"])
    fig_dir = ensure_dir(cfg["output"]["figure_dir"])
    panel_path = Path(args.panel) if args.panel else factor_dir / "factor_panel.parquet"

    # 加载因子面板
    panel = pd.read_parquet(panel_path) if panel_path.suffix == ".parquet" else pd.read_csv(panel_path, parse_dates=["date"])
    if "date" in panel.columns and "code" in panel.columns:
        panel = panel.set_index(["date", "code"])
    panel = panel.sort_index()
    factor_cols = [c for c in panel.columns if c not in {"industry", "is_suspended"}]

    # 加载行情 / 收益
    with open(cfg["data"]["processed_dir"] + "/processed.pkl", "rb") as f:
        proc = pickle.load(f)
    quotes = proc["quotes"]
    rows = {}
    for code, df in quotes.items():
        rows[code] = df["close"].pct_change().rename("ret_1d")
    ret_panel = pd.concat(rows, axis=1)
    ret_panel.columns.name = "code"
    ret_panel = ret_panel.stack(future_stack=True).rename("ret_1d").to_frame()
    ret_panel.index.set_names(["date", "code"], inplace=True)

    # 合并 ret_1d
    full = panel.join(ret_panel[["ret_1d"]], how="left")

    # ========== 1) 多因子 IC 表 ==========
    print("=" * 60)
    print("1) 多因子 IC 摘要")
    print("=" * 60)
    ic_table = multi_factor_ic_table(full, factor_cols, methods=["pearson", "spearman"])
    ic_table.to_csv(result_dir / "factor_ic.csv", index=False)
    print(ic_table.round(4).to_string(index=False))

    # 关键因子 IC 序列出图（Top 5 by abs IR）
    if not ic_table.empty and "ir" in ic_table.columns:
        # 取 spearman 视角
        spearman = ic_table[ic_table["method"] == "spearman"].dropna(subset=["ir"])
        if not spearman.empty:
            top5 = spearman.reindex(spearman["ir"].abs().sort_values(ascending=False).index).head(5)
            for f in top5["factor"]:
                ic = calc_ic_series(full, f, method="spearman")
                plt_mod.plot_ic_series(ic, title=f"IC (Spearman): {f}", out_path=fig_dir / f"ic_{f}.png")

    # ========== 2) 分组组合（5 分组） ==========
    print("=" * 60)
    print("2) 分组组合 (Sort Portfolio)")
    print("=" * 60)
    sp = SortPortfolio(n_groups=cfg["evaluation"]["deciles"], weighting="equal")
    grp_stats = []
    grp_curves: Dict[str, pd.DataFrame] = {}
    for f in factor_cols:
        try:
            gr = sp.backtest(full, ret_panel, factor_col=f)
            gr.to_csv(result_dir / f"group_ret_{f}.csv")
            grp_curves[f] = gr
            ls = sp.long_short_spread(gr)
            stats = perf_stats((1 + ls).cumprod())
            stats["factor"] = f
            grp_stats.append(stats)
        except Exception as e:
            logger.warning("group %s 失败: %s", f, e)

    if grp_stats:
        grp_df = pd.DataFrame(grp_stats)
        grp_df.to_csv(result_dir / "group_perf_summary.csv", index=False)
        print(grp_df[["factor", "annual_return", "sharpe", "max_drawdown", "calmar"]].round(4).to_string(index=False))

        # 关键因子分组收益图
        if grp_curves:
            for f in list(grp_curves.keys())[:5]:
                plt_mod.plot_group_returns(grp_curves[f], title=f"Group NAV: {f}", out_path=fig_dir / f"group_ret_{f}.png")

    # ========== 3) 模型回测对比 ==========
    print("=" * 60)
    print("3) 模型回测对比")
    print("=" * 60)
    nav_files = sorted(result_dir.glob("nav_*.csv"))
    nav_dict = {}
    for f in nav_files:
        name = f.stem.replace("nav_", "")
        try:
            df = pd.read_csv(f, parse_dates=[0], index_col=0)
            col = df.columns[0]
            nav_dict[name] = df[col]
        except Exception:
            continue
    if nav_dict:
        plt_mod.plot_nav_curve(nav_dict, title="Model NAV (OOS)", out_path=fig_dir / "model_nav.png")
        rows = []
        for name, nav in nav_dict.items():
            stats = perf_stats(nav)
            stats["model"] = name
            rows.append(stats)
        comp = pd.DataFrame(rows)
        comp.to_csv(result_dir / "model_perf_summary.csv", index=False)
        print(comp[["model", "annual_return", "sharpe", "max_drawdown"]].round(4).to_string(index=False))

    # ========== 4) 换手 / 回撤 ==========
    print("=" * 60)
    print("4) 换手与回撤")
    print("=" * 60)
    if nav_dict:
        # 用排名第一的模型
        first_nav = list(nav_dict.values())[0]
        plt_mod.plot_drawdown(first_nav, title="Max Drawdown", out_path=fig_dir / "drawdown.png")
        # 读取换手
        to_files = sorted(result_dir.glob("turnover_*.csv"))
        for tf in to_files:
            df = pd.read_csv(tf, parse_dates=[0], index_col=0)
            to = df.iloc[:, 0]
            plt_mod.plot_turnover(to, title=f"Turnover: {tf.stem}", out_path=fig_dir / f"{tf.stem}.png")

    # ========== 5) 稳健性（市场阶段） ==========
    print("=" * 60)
    print("5) 稳健性：按市场阶段")
    print("=" * 60)
    # 构造 benchmark 代理（等权平均）
    if quotes:
        all_close = pd.concat({c: d["close"] for c, d in quotes.items()}, axis=1)
        bench_nav = (1 + all_close.pct_change().mean(axis=1).fillna(0)).cumprod()
        regime = market_regime_label(
            bench_nav,
            lookback_months=12,
            bull_threshold=cfg["evaluation"]["regime"]["bull_threshold"],
        )
        regime.to_csv(result_dir / "market_regime.csv")

        if nav_dict:
            for name, nav in nav_dict.items():
                rob = robustness_by_regime(nav, regime)
                if not rob.empty:
                    rob.to_csv(result_dir / f"robust_regime_{name}.csv")
                    print(f"\n[{name}] 牛/熊/震荡表现：")
                    print(rob.round(4).to_string())

    # ========== 6) 因子截面分布图 ==========
    plt_mod.plot_factor_distribution(panel, factor_cols, out_path=fig_dir / "factor_distribution.png")

    print("\n✔ 全部评估完成。结果 →", result_dir)
    print("  图表 →", fig_dir)


if __name__ == "__main__":
    main()

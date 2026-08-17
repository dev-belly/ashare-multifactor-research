"""可视化：净值曲线、IC 序列、分组收益、因子分布、稳健性热力图。"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


def setup_style(style: str = "seaborn-v0_8-whitegrid", palette: str = "Set2"):
    sns.set_style(style)
    sns.set_palette(palette)


def plot_nav_curve(
    nav_dict: Dict[str, pd.Series],
    title: str = "Strategy NAV",
    out_path: str | Path | None = None,
):
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, nav in nav_dict.items():
        ax.plot(nav.index, nav.values, label=name, linewidth=1.5)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("NAV")
    ax.legend()
    ax.grid(True, alpha=0.3)
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig


def plot_ic_series(ic: pd.Series, title: str = "IC Time Series", out_path=None):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax1.bar(ic.index, ic.values, width=5, color="steelblue", alpha=0.6)
    ax1.axhline(0, color="black", linewidth=0.5)
    ax1.set_title(title)
    ax1.set_ylabel("IC")

    cum = ic.cumsum()
    ax2.plot(cum.index, cum.values, color="darkred", linewidth=1.2)
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.set_ylabel("Cumulative IC")
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig


def plot_group_returns(group_ret: pd.DataFrame, title: str = "Group Returns", out_path=None):
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in group_ret.columns:
        nav = (1 + group_ret[col]).cumprod()
        ax.plot(nav.index, nav.values, label=col, linewidth=1.4)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("NAV")
    ax.legend()
    ax.grid(True, alpha=0.3)
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig


def plot_factor_distribution(factor_panel: pd.DataFrame, factor_cols: List[str], out_path=None):
    """最新一期截面分布。"""
    if factor_panel.empty:
        return None
    last_dt = factor_panel.index.get_level_values("date").max()
    snap = factor_panel.xs(last_dt, level="date")[factor_cols]
    n = len(factor_cols)
    cols = min(4, n)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows))
    axes = np.array(axes).reshape(-1)
    for i, c in enumerate(factor_cols):
        s = snap[c].dropna()
        axes[i].hist(s, bins=30, color="steelblue", alpha=0.7, edgecolor="white")
        axes[i].set_title(c)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    fig.suptitle(f"Cross-section factor distribution @ {last_dt.date()}")
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig


def plot_robustness_heatmap(
    metric_table: pd.DataFrame, value_col: str, title: str = "Robustness", out_path=None
):
    """metric_table: 行=group, 列=period or scenario；value_col 数值列。"""
    if metric_table.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, max(3, 0.5 * len(metric_table))))
    sns.heatmap(
        metric_table[[value_col]],
        annot=True,
        fmt=".3f",
        cmap="RdYlGn",
        center=0,
        ax=ax,
    )
    ax.set_title(title)
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig


def plot_drawdown(nav: pd.Series, title: str = "Drawdown", out_path=None):
    hwm = nav.cummax()
    dd = nav / hwm - 1
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.fill_between(dd.index, dd.values, 0, color="indianred", alpha=0.7)
    ax.set_title(title)
    ax.set_ylabel("Drawdown")
    ax.grid(True, alpha=0.3)
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig


def plot_turnover(turnover: pd.Series, title: str = "Turnover", out_path=None):
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.bar(turnover.index, turnover.values, color="seagreen", alpha=0.6)
    ax.set_title(title)
    ax.set_ylabel("Turnover")
    if out_path:
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
    return fig

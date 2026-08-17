"""Streamlit 仪表盘：A股多因子研究与样本外回测平台。

一个直观的 Web 界面，覆盖：
  - 数据概览
  - 因子分析（IC / 分布）
  - 分组回测（五分组 NAV）
  - 模型对比（样本外 NAV）
  - 稳健性（市场阶段）
  - 一键运行完整流水线

运行：
    PYTHONPATH=. streamlit run dashboard/app.py
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")  # 无头环境
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.engine import make_ret_panel, run_long_only_topk  # noqa: E402
from src.backtest.oos_split import (  # noqa: E402
    expanding_window_splits,
    filter_panel_by_fold,
)
from src.data.akshare_loader import AkShareLoader  # noqa: E402
from src.data.processor import (  # noqa: E402
    align_to_calendar,
    basic_clean,
    build_universe_table,
)
from src.evaluation.ic import calc_ic_series, multi_factor_ic_table  # noqa: E402
from src.evaluation.returns import perf_stats  # noqa: E402
from src.evaluation.robustness import (  # noqa: E402
    market_regime_label,
    robustness_by_regime,
)
from src.factors.engineering import build_factor_panel, load_factor_panel  # noqa: E402
from src.models.elastic_net import ElasticNetModel  # noqa: E402
from src.models.lightgbm_model import LightGBMModel  # noqa: E402
from src.utils.common import (  # noqa: E402
    PROJECT_ROOT,
    ensure_dir,
    load_config,
)

st.set_page_config(
    page_title="A股多因子研究平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_processed() -> Dict:
    p = PROJECT_ROOT / "data" / "processed" / "processed.pkl"
    if not p.exists():
        return {}
    with open(p, "rb") as f:
        return pickle.load(f)


@st.cache_data(show_spinner=False)
def load_panel() -> pd.DataFrame:
    f = PROJECT_ROOT / "data" / "factors" / "factor_panel.parquet"
    if not f.exists():
        return pd.DataFrame()
    return load_factor_panel(str(f))


def list_png(fig_dir: Path, prefix: str) -> List[Path]:
    if not fig_dir.exists():
        return []
    return sorted(fig_dir.glob(f"{prefix}*.png"))


# ---------------------------------------------------------------------------
# 侧边栏
# ---------------------------------------------------------------------------
st.sidebar.title("📈 A股多因子研究平台")
st.sidebar.caption("资产定价 · 机器学习 · 样本外回测")

cfg = load_config()
top_k = st.sidebar.slider("TopK 持仓数", 5, 50, 20, 1)
rebal_freq = st.sidebar.selectbox("调仓频率（交易日）", [5, 10, 21, 42, 63], index=2)
cost_bps = st.sidebar.slider("单边交易成本 (bps)", 0, 50, 20, 1)
models_sel = st.sidebar.multiselect(
    "模型", ["eq_weight", "elastic_net", "lightgbm"], default=["eq_weight", "elastic_net", "lightgbm"]
)
data_source = st.sidebar.radio("数据源", ["synthetic", "akshare"], index=0)

run_btn = st.sidebar.button("▶️ 运行完整流水线", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# 主区 Tab
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 数据概览", "🧪 因子分析", "📈 分组回测", "🤖 模型对比", "🛡️ 稳健性"]
)

# ============================ Tab 1: 数据概览 ============================
with tab1:
    st.header("数据概览")
    proc = load_processed()
    if not proc:
        st.warning("尚未生成数据，请点击左侧『运行完整流水线』或先执行 `scripts/01_fetch_data.py`。")
    else:
        quotes = proc.get("quotes", {})
        cal = proc.get("calendar")
        fins = proc.get("financials")
        ind = proc.get("industry")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("股票数", len(quotes))
        c2.metric("交易日", len(cal) if cal is not None else 0)
        c3.metric("财报条数", len(fins) if fins is not None else 0)
        c4.metric("行业数", ind["industry"].nunique() if ind is not None and not ind.empty else 0)

        if cal is not None:
            st.caption(f"区间：{cal.min().date()} → {cal.max().date()}")

        # 示例走势
        st.subheader("示例个股走势（前复权）")
        sample_codes = list(quotes.keys())[:6]
        fig, ax = plt.subplots(figsize=(10, 4))
        for code in sample_codes:
            df = quotes[code]
            ax.plot(df.index, df["close"], label=code, linewidth=1)
        ax.set_ylabel("价格")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)

        # 股票池行业分布
        if ind is not None and not ind.empty:
            st.subheader("股票池行业分布")
            cnt = ind["industry"].value_counts()
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            ax2.barh(cnt.index[::-1], cnt.values[::-1], color="steelblue")
            ax2.set_xlabel("股票数")
            st.pyplot(fig2)

# ============================ Tab 2: 因子分析 ============================
with tab2:
    st.header("因子分析")
    panel = load_panel()
    if panel is None or panel.empty:
        st.warning("尚未构建因子面板，请先运行流水线。")
    else:
        factor_cols = [c for c in panel.columns if c not in {"industry", "is_suspended"}]
        st.success(f"已构建 {len(factor_cols)} 个因子，样本数 {len(panel):,}")

        # 加载 ret_panel 用于 IC 计算
        proc = load_processed()
        if proc:
            ret_panel = make_ret_panel(proc["quotes"], horizon=1, use_fwd=False)
            ret_panel.index.set_names(["date", "code"], inplace=True)
            full = panel.join(ret_panel[["ret_1d"]], how="left")

            with st.spinner("计算多因子 IC ..."):
                ic_tbl = multi_factor_ic_table(full, factor_cols, methods=["pearson", "spearman"])

            st.subheader("多因子 IC / RankIC 摘要")
            show_cols = ["factor", "method", "ic_mean", "ic_std", "ir", "ic_pos_ratio", "abs_ic_mean"]
            st.dataframe(
                ic_tbl[show_cols].round(4).style.background_gradient(
                    subset=["ir"], cmap="RdYlGn"
                ),
                use_container_width=True,
                height=520,
            )

            st.subheader("因子截面分布（最新交易日）")
            figs = list_png(PROJECT_ROOT / "outputs" / "figures", "factor_distribution")
            if figs:
                st.image(str(figs[0]))
            else:
                st.info("运行流水线后生成 factor_distribution.png")

# ============================ Tab 3: 分组回测 ============================
with tab3:
    st.header("分组回测（五分组）")
    result_dir = PROJECT_ROOT / "outputs" / "results"
    grp_files = sorted(result_dir.glob("group_ret_*.csv")) if result_dir.exists() else []
    if not grp_files:
        st.warning("尚未生成分组回测结果。")
    else:
        factor_options = [f.stem.replace("group_ret_", "") for f in grp_files]
        sel = st.selectbox("选择因子", factor_options)
        csv = result_dir / f"group_ret_{sel}.csv"
        gr = pd.read_csv(csv, parse_dates=[0], index_col=0)
        st.line_chart(gr, use_container_width=True)
        st.caption("G1（最低）→ G5（最高），等权组合净值")

# ============================ Tab 4: 模型对比 ============================
with tab4:
    st.header("模型对比（样本外）")
    result_dir = PROJECT_ROOT / "outputs" / "results"
    nav_files = sorted(result_dir.glob("nav_*.csv")) if result_dir.exists() else []
    if not nav_files:
        st.warning("尚未生成模型回测结果。")
    else:
        navs = {}
        for f in nav_files:
            name = f.stem.replace("nav_", "")
            df = pd.read_csv(f, parse_dates=[0], index_col=0)
            navs[name] = df.iloc[:, 0]
        nav_df = pd.DataFrame(navs)
        st.line_chart(nav_df, use_container_width=True)
        st.caption("各模型样本外净值（基准 1.0）")

        # 性能表
        perf_file = result_dir / "model_perf_summary.csv"
        if perf_file.exists():
            perf = pd.read_csv(perf_file)
            st.subheader("性能汇总")
            st.dataframe(perf.round(4), use_container_width=True, height=200)

        # 模型 NAV 图
        figs = list_png(PROJECT_ROOT / "outputs" / "figures", "model_nav")
        if figs:
            st.image(str(figs[0]))

# ============================ Tab 5: 稳健性 ============================
with tab5:
    st.header("稳健性：按市场阶段")
    result_dir = PROJECT_ROOT / "outputs" / "results"
    rob_files = sorted(result_dir.glob("robust_regime_*.csv")) if result_dir.exists() else []
    if not rob_files:
        st.warning("尚未生成稳健性分析结果。")
    else:
        for f in rob_files:
            name = f.stem.replace("robust_regime_", "")
            df = pd.read_csv(f)
            st.subheader(f"模型：{name}")
            st.dataframe(df.round(4), use_container_width=True, height=160)
        figs = list_png(PROJECT_ROOT / "outputs" / "figures", "drawdown")
        if figs:
            st.subheader("最大回撤")
            st.image(str(figs[0]))

# ---------------------------------------------------------------------------
# 运行流水线
# ---------------------------------------------------------------------------
if run_btn:
    st.sidebar.success("流水线启动中 ...")
    import subprocess

    with st.spinner("正在运行完整流水线（合成数据）..."):
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "05_full_pipeline.py"),
            "--synthetic",
            "--models",
            ",".join(models_sel) if models_sel else "eq_weight",
            "--top-k",
            str(top_k),
            "--rebal-freq",
            str(rebal_freq),
            "--cost-bps",
            str(cost_bps),
        ]
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        if result.returncode == 0:
            st.sidebar.success("✔ 流水线完成！")
            st.rerun()
        else:
            st.sidebar.error("流水线失败，查看日志")
            st.error(result.stderr[-2000:])

# 页脚
st.sidebar.divider()
st.sidebar.caption("免责声明：仅供研究，不构成投资建议。")

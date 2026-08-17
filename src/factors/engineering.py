"""因子工程主入口：注册所有因子 → 拼接面板 → 截面处理 → 输出。"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.factors.base import (
    Factor,
    cross_section_standardize,
    cross_section_winsorize,
    filter_universe,
    industry_neutralize,
)
from src.factors.liquidity import AmihudFactor, TurnoverFactor
from src.factors.momentum import Mom1M, Mom3M, Mom12_10
from src.factors.quality import AccrualsFactor, GrossMarginFactor, ROAFactor, ROEFactor
from src.factors.value import BPFactor, EP2YFactor, EPFactor, SPFactor
from src.factors.volatility import IdioVolFactor, Vol20D, Vol60D
from src.utils.common import get_logger

logger = get_logger(__name__)


# ========== 注册表 ==========
def default_factor_registry() -> Dict[str, Factor]:
    """默认 5 类 13 因子。"""
    return {
        # Value
        "ep": EPFactor(),
        "bp": BPFactor(),
        "sp": SPFactor(),
        "ep_chg_yoy": EP2YFactor(),
        # Quality
        "roe": ROEFactor(),
        "roa": ROAFactor(),
        "gp_a": GrossMarginFactor(),
        "accruals": AccrualsFactor(),
        # Momentum
        "mom_1m": Mom1M(),
        "mom_3m": Mom3M(),
        "mom_12_10": Mom12_10(),
        # Volatility
        "vol_20d": Vol20D(),
        "vol_60d": Vol60D(),
        "idio_vol": IdioVolFactor(),
        # Liquidity
        "turn_20d": TurnoverFactor(),
        "amihud_20d": AmihudFactor(),
    }


# ========== 拼装流水线 ==========
def build_factor_panel(
    quotes: Dict[str, pd.DataFrame],
    financials: pd.DataFrame | None = None,
    industry_map: pd.DataFrame | None = None,
    registry: Dict[str, Factor] | None = None,
    lag_days: int = 90,
    winsorize_q: float = 0.01,
    standardize: str = "zscore",
    do_industry_neutral: bool = True,
    st_codes: List[str] | None = None,
) -> pd.DataFrame:
    """构造因子面板。

    步骤：
        1. 跑每个因子得到长格式
        2. join 到一张大表 (date, code, f1, f2, ...)
        3. 缩尾 → 标准化 → 行业中性化 → 停牌/ST 过滤
        4. 合并行业标签便于后续分层

    Args:
        quotes: 日行情。
        financials: 季度财务。
        industry_map: 行业映射。
        registry: 因子注册表。
        lag_days: 财务可得日 lag。
        winsorize_q: 缩尾分位。
        standardize: 标准化方法。
        do_industry_neutral: 是否做行业内 zscore。
        st_codes: ST 股票代码列表。

    Returns:
        截面处理后的长格式因子面板。
    """
    if registry is None:
        registry = default_factor_registry()

    # 1) 把 financials 加 available_date
    if financials is not None and not financials.empty:
        financials = financials.copy()
        financials["available_date"] = financials["publish_date"] + pd.Timedelta(
            days=lag_days
        )

    # 2) 跑每个因子
    panels: Dict[str, pd.DataFrame] = {}
    for fname, f in registry.items():
        try:
            df = f.compute(quotes, financials, industry_map)
            if not df.empty:
                panels[fname] = df
                logger.info("factor %s: %d 行", fname, len(df))
        except Exception as e:
            logger.warning("factor %s 计算失败: %s", fname, e)

    if not panels:
        return pd.DataFrame()

    # 3) 拼接
    base = panels[list(panels.keys())[0]].copy()
    for k, p in list(panels.items())[1:]:
        base = base.join(p, how="outer")

    # 4) 行业标签
    if industry_map is not None and not industry_map.empty:
        # 用 map 加速
        ind_map = industry_map.drop_duplicates(subset=["code"]).set_index("code")["industry"]
        base = base.reset_index()
        base["industry"] = base["code"].map(ind_map).fillna("Unknown")
        base = base.set_index(["date", "code"])
    else:
        base["industry"] = "Unknown"

    factor_cols = list(panels.keys())

    # 5) 停牌标记：每个 (code, date) 取对应行情的 is_suspended
    parts = []
    for code, df in quotes.items():
        s = df.get("is_suspended", pd.Series(False, index=df.index))
        s = s.astype(bool)
        s.index.name = "date"
        parts.append(
            pd.DataFrame({"code": code, "is_suspended": s.values}, index=s.index)
        )
    if parts:
        susp = pd.concat(parts).reset_index()
        susp = susp.set_index(["date", "code"])
        base = base.join(susp[["is_suspended"]], how="left")
        base["is_suspended"] = base["is_suspended"].fillna(False).astype(bool)
    else:
        base["is_suspended"] = False

    # 6) 过滤 ST 与停牌
    base = filter_universe(base, st_codes=st_codes, suspended_col="is_suspended")

    # 7) 缩尾
    base = cross_section_winsorize(base, factor_cols, lower_q=winsorize_q, upper_q=1 - winsorize_q)

    # 8) 行业内 zscore（先行业内标准化可显著降低行业 bias）
    if do_industry_neutral:
        base = industry_neutralize(base, factor_cols, industry_col="industry")

    # 9) 整体 zscore / rank
    base = cross_section_standardize(base, factor_cols, method=standardize)

    return base


def save_factor_panel(panel: pd.DataFrame, path: str) -> None:
    """保存因子面板（parquet 优先，CSV 备用）。"""
    try:
        panel.reset_index().to_parquet(path, engine="pyarrow", index=False)
    except Exception:
        panel.reset_index().to_csv(path, index=False)


def load_factor_panel(path: str) -> pd.DataFrame:
    """加载因子面板。"""
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, parse_dates=["date"])
    if "date" in df.columns and "code" in df.columns:
        df = df.set_index(["date", "code"])
    return df

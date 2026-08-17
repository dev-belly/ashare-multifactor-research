"""合成 A 股数据生成器。

不依赖外网时用 multivariate geometric Brownian motion + 因子驱动
合成可复现的"准真实"行情/财务/行业数据，用于流水线自检。
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.utils.common import get_logger

logger = get_logger(__name__)


# ========== 股票池（覆盖大中微盘与多行业） ==========
SYNTHETIC_UNIVERSE: List[Dict] = [
    # 主板大蓝筹
    {"code": "600519.SH", "name": "贵州茅台", "industry": "食品饮料", "cap_bucket": "large"},
    {"code": "601318.SH", "name": "中国平安", "industry": "非银金融", "cap_bucket": "large"},
    {"code": "600036.SH", "name": "招商银行", "industry": "银行", "cap_bucket": "large"},
    {"code": "601398.SH", "name": "工商银行", "industry": "银行", "cap_bucket": "large"},
    {"code": "600276.SH", "name": "恒瑞医药", "industry": "医药生物", "cap_bucket": "large"},
    {"code": "601166.SH", "name": "兴业银行", "industry": "银行", "cap_bucket": "large"},
    {"code": "600028.SH", "name": "中国石化", "industry": "石油石化", "cap_bucket": "large"},
    {"code": "601857.SH", "name": "中国石油", "industry": "石油石化", "cap_bucket": "large"},
    {"code": "600030.SH", "name": "中信证券", "industry": "非银金融", "cap_bucket": "large"},
    {"code": "601012.SH", "name": "隆基绿能", "industry": "电力设备", "cap_bucket": "large"},
    # 中盘
    {"code": "000858.SZ", "name": "五粮液", "industry": "食品饮料", "cap_bucket": "mid"},
    {"code": "000333.SZ", "name": "美的集团", "industry": "家用电器", "cap_bucket": "mid"},
    {"code": "000651.SZ", "name": "格力电器", "industry": "家用电器", "cap_bucket": "mid"},
    {"code": "002594.SZ", "name": "比亚迪", "industry": "汽车", "cap_bucket": "mid"},
    {"code": "002475.SZ", "name": "立讯精密", "industry": "电子", "cap_bucket": "mid"},
    {"code": "300750.SZ", "name": "宁德时代", "industry": "电力设备", "cap_bucket": "mid"},
    {"code": "300059.SZ", "name": "东方财富", "industry": "非银金融", "cap_bucket": "mid"},
    {"code": "002714.SZ", "name": "牧原股份", "industry": "农林牧渔", "cap_bucket": "mid"},
    {"code": "600887.SH", "name": "伊利股份", "industry": "食品饮料", "cap_bucket": "mid"},
    {"code": "601888.SH", "name": "中国中免", "industry": "社会服务", "cap_bucket": "mid"},
    # 小盘
    {"code": "002415.SZ", "name": "海康威视", "industry": "电子", "cap_bucket": "small"},
    {"code": "600196.SH", "name": "复星医药", "industry": "医药生物", "cap_bucket": "small"},
    {"code": "300015.SZ", "name": "爱尔眼科", "industry": "医药生物", "cap_bucket": "small"},
    {"code": "002230.SZ", "name": "科大讯飞", "industry": "计算机", "cap_bucket": "small"},
    {"code": "300760.SZ", "name": "迈瑞医疗", "industry": "医药生物", "cap_bucket": "small"},
    {"code": "600436.SH", "name": "片仔癀", "industry": "医药生物", "cap_bucket": "small"},
    {"code": "002466.SZ", "name": "天齐锂业", "industry": "有色金属", "cap_bucket": "small"},
    {"code": "600438.SH", "name": "通威股份", "industry": "电力设备", "cap_bucket": "small"},
    {"code": "300122.SZ", "name": "智飞生物", "industry": "医药生物", "cap_bucket": "small"},
    {"code": "601633.SH", "name": "长城汽车", "industry": "汽车", "cap_bucket": "small"},
]


def _seeded_rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def generate_synthetic_universe(seed: int = 42) -> pd.DataFrame:
    """生成合成股票池基础信息（代码/名称/行业/市值桶）。"""
    rng = _seeded_rng(seed)
    base = pd.DataFrame(SYNTHETIC_UNIVERSE)
    base["list_date"] = pd.to_datetime(
        rng.choice(pd.date_range("2002-01-01", "2020-12-31", freq="B"), size=len(base))
    )
    return base


def generate_synthetic_quotes(
    universe: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    seed: int = 42,
) -> Dict[str, pd.DataFrame]:
    """生成日行情：open/high/low/close/volume/amount。

    使用几何布朗运动 + 行业/市值风格因子。
    """
    rng = _seeded_rng(seed + 1)

    industry_mu = {
        ind: rng.normal(0.0004, 0.001) for ind in universe["industry"].unique()
    }
    cap_sigma = {"large": 0.014, "mid": 0.018, "small": 0.024}

    out: Dict[str, pd.DataFrame] = {}
    for _, row in universe.iterrows():
        ind = row["industry"]
        cap = row["cap_bucket"]
        n = len(calendar)
        sigma = cap_sigma[cap]
        mu = industry_mu[ind]
        # 隐含 beta/alpha
        alpha = mu
        # 引入时变：分段周期 + 噪声
        eps = rng.normal(0, sigma, n)
        # 给个别股票加"特质"漂移（使其有显著 alpha）
        if hash(row["code"]) % 5 == 0:
            eps += rng.normal(0.0008, 0.001, n)
        # 累积对数收益
        log_ret = alpha + eps
        log_ret[0] = 0.0
        log_price = np.cumsum(log_ret)
        # 起始价：基于市值桶
        p0 = {"large": 50.0, "mid": 30.0, "small": 20.0}[cap]
        close = p0 * np.exp(log_price)
        # OHLC 用 close 反推
        high = close * (1 + np.abs(rng.normal(0.005, 0.003, n)))
        low = close * (1 - np.abs(rng.normal(0.005, 0.003, n)))
        open_ = close * (1 + rng.normal(0, 0.003, n))
        # 量：基础量 * 涨跌缩放
        base_vol = {"large": 8e6, "mid": 4e6, "small": 2e6}[cap]
        volume = base_vol * (1 + 0.5 * np.abs(log_ret) / sigma) * np.exp(
            rng.normal(0, 0.2, n)
        )
        amount = close * volume

        df = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
                "adj_factor": 1.0,  # 复权因子；synthetic 不分红送股
            },
            index=calendar,
        )
        df.index.name = "date"
        out[row["code"]] = df

    return out


def generate_synthetic_financials(
    universe: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    seed: int = 42,
) -> pd.DataFrame:
    """生成季度财务数据：发布日 = 季末后 ~ lag_days。

    字段：code, period_end, publish_date, revenue, net_profit, equity,
          total_assets, total_liab, operating_cf, gross_profit, eps, bvps.
    """
    rng = _seeded_rng(seed + 2)
    rows = []
    # 每只股票每个季度一行
    quarters = pd.period_range("2017Q4", "2025Q4", freq="Q").tolist()

    for _, u in universe.iterrows():
        code = u["code"]
        cap = u["cap_bucket"]
        # 基础规模：大 > 中 > 小
        scale = {"large": 10.0, "mid": 3.0, "small": 1.0}[cap]
        # 公司基础盈利能力（带行业风格）
        base_profit_margin = rng.uniform(0.05, 0.25)
        growth = rng.normal(0.04, 0.02)  # 季度复合增长率

        equity = scale * 1e10 * rng.uniform(0.5, 1.5)
        for q in quarters:
            period_end = q.end_time.date()
            # 财务规模随时间演化
            t = (q.ordinal - pd.Period("2017Q4", freq="Q").ordinal)
            size_growth = (1 + growth) ** t
            rev = scale * 1e9 * rng.uniform(0.5, 1.5) * size_growth
            np_ = rev * base_profit_margin * (1 + rng.normal(0, 0.1))
            eq = equity * size_growth
            ta = eq * rng.uniform(1.2, 1.8)
            tl = ta - eq
            gp = rev * rng.uniform(0.2, 0.5)
            ocf = np_ * rng.uniform(0.8, 1.3)
            shares = scale * 1e9 * rng.uniform(0.8, 1.2)
            eps = np_ / shares
            bvps = eq / shares
            # 披露日 = 季末 + lag（含随机扰动）
            lag = int(rng.integers(45, 110))  # A 股 1 季报 60~90d，年报 ~120d
            publish = pd.Timestamp(period_end) + pd.Timedelta(days=lag)
            rows.append(
                dict(
                    code=code,
                    period_end=pd.Timestamp(period_end),
                    publish_date=publish,
                    revenue=rev,
                    net_profit=np_,
                    equity=eq,
                    total_assets=ta,
                    total_liab=tl,
                    operating_cf=ocf,
                    gross_profit=gp,
                    eps=eps,
                    bvps=bvps,
                    shares=shares,
                )
            )
    df = pd.DataFrame(rows)
    return df


def generate_synthetic_industry(universe: pd.DataFrame) -> pd.DataFrame:
    """生成申万一级行业分类映射（与股票池一致）。"""
    return universe[["code", "industry"]].copy()

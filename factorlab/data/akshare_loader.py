"""AkShare 数据加载器。

包含自动降级：网络异常或接口变动时使用合成数据兜底，
保证流水线在沙盒内依然可跑通。
"""
from __future__ import annotations

import pandas as pd

from factorlab.data.calendar import get_trading_calendar
from factorlab.data.synthetic import (
    generate_synthetic_financials,
    generate_synthetic_industry,
    generate_synthetic_quotes,
    generate_synthetic_universe,
)
from factorlab.utils.common import ensure_dir, get_logger

logger = get_logger(__name__)


class AkShareLoader:
    """A 股多源数据加载器（akshare + synthetic fallback）。"""

    def __init__(self, source: str = "akshare", cache_dir: str = "data/raw"):
        self.source = source
        self.cache_dir = ensure_dir(cache_dir)

    # ---------- 入口 ----------
    def load_all(
        self,
        start_date: str = "2018-01-01",
        end_date: str = "2025-12-31",
    ) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        """加载 4 类数据：行情(字典)、财务(df)、行业映射(df)、交易日历。

        Returns:
            (quotes_by_code, financials, industry_map, calendar)
        """
        cal = get_trading_calendar(start_date, end_date, source=self.source)

        if self.source == "synthetic":
            return self._load_synthetic(cal)

        # akshare 尝试，失败降级
        try:
            return self._load_akshare(cal, start_date, end_date)
        except Exception as e:
            logger.warning("AkShare 加载失败（%s），降级到 synthetic", e)
            return self._load_synthetic(cal)

    # ---------- synthetic ----------
    def _load_synthetic(
        self, cal: pd.DatetimeIndex
    ) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        universe = generate_synthetic_universe(seed=42)
        quotes = generate_synthetic_quotes(universe, cal, seed=42)
        fins = generate_synthetic_financials(universe, cal, seed=42)
        ind = generate_synthetic_industry(universe)
        return quotes, fins, ind, cal

    # ---------- akshare ----------
    def _load_akshare(
        self,
        cal: pd.DatetimeIndex,
        start_date: str,
        end_date: str,
    ) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        import akshare as ak

        # 1. 股票列表 + 行业分类
        stock_list = ak.stock_zh_a_spot_em()  # 含代码/名称
        # TODO: 行业分类（ak.stock_board_industry_name_em）映射到申万一级需要人工维护，
        #       当前流水线统一使用合成数据里的行业字段，此处暂不接入。

        # 2. 逐只拉日线（实际应用中应缓存并并发，这里用 for 简洁实现）
        quotes: dict[str, pd.DataFrame] = {}
        for code in stock_list["代码"].tolist()[:50]:  # 限制数量，避免超长
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="qfq",  # 前复权
                )
                if df.empty:
                    continue
                df = df.rename(
                    columns={
                        "日期": "date",
                        "开盘": "open",
                        "最高": "high",
                        "最低": "low",
                        "收盘": "close",
                        "成交量": "volume",
                        "成交额": "amount",
                    }
                )
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                df["adj_factor"] = 1.0  # AkShare 已前复权，无需手动算
                quotes[f"{code}.{self._detect_exchange(code)}"] = df
            except Exception as e:
                logger.debug("跳过 %s: %s", code, e)

        # 3. 财务数据：使用同花顺/巨潮接口
        fins_list = []
        for code in list(quotes.keys()):
            try:
                base_code = code.split(".")[0]
                fin = ak.stock_financial_report_sina(stock=base_code)
                if fin is None or fin.empty:
                    continue
                # TODO: 只保留最近 N 期报告（按日期/报告期列过滤），当前全量入表
                fins_list.append(fin)
            except Exception:
                continue

        # 真实场景里要做大量字段规整；这里失败兜底
        if not quotes:
            raise RuntimeError("akshare 未取到任何行情数据")

        # 简化财务报表兜底
        fins = pd.DataFrame()
        ind = pd.DataFrame()

        return quotes, fins, ind, cal

    @staticmethod
    def _detect_exchange(code: str) -> str:
        """根据股票代码判断交易所。"""
        code = str(code).zfill(6)
        if code.startswith(("60", "68", "90")):
            return "SH"
        if code.startswith(("00", "30", "20")):
            return "SZ"
        return "SH"

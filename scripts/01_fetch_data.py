"""01_fetch_data.py：拉取 / 合成基础数据。"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import pandas as pd

from src.data.akshare_loader import AkShareLoader
from src.data.processor import (
    align_to_calendar,
    basic_clean,
    build_universe_table,
    merge_financial_quarterly,
)
from src.utils.common import ensure_dir, get_logger, load_config, PROJECT_ROOT

logger = get_logger("fetch_data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "config.yaml"))
    parser.add_argument("--synthetic", action="store_true", help="强制使用合成数据")
    args = parser.parse_args()

    cfg = load_config(args.config)
    source = "synthetic" if args.synthetic else cfg["data"]["source"]
    cache = ensure_dir(cfg["data"]["cache_dir"])
    proc = ensure_dir(cfg["data"]["processed_dir"])

    logger.info("Step 1: 加载数据 (source=%s)", source)
    loader = AkShareLoader(source=source, cache_dir=str(cache))
    quotes, fins, ind, cal = loader.load_all(
        start_date=cfg["data"]["start_date"],
        end_date=cfg["data"]["end_date"],
    )

    # 基础清洗
    logger.info("Step 2: 基础清洗 + 交易日历对齐")
    quotes = basic_clean(quotes)
    quotes = align_to_calendar(quotes, cal)

    # 财务可用日期
    fins_avail = merge_financial_quarterly(
        fins, pd.DataFrame(), lag_days=cfg["factors"]["financial_lag_days"]
    )

    # 股票池
    universe = build_universe_table(quotes, fins, ind)
    universe["code"] = universe["code"].astype(str)

    # 保存
    out = proc / "processed.pkl"
    with open(out, "wb") as f:
        pickle.dump(
            {"quotes": quotes, "financials": fins_avail, "industry": ind, "calendar": cal, "universe": universe},
            f,
        )
    logger.info("Step 3: 写入 %s, %d 只股票, %d 个交易日", out, len(quotes), len(cal))
    print(f"✔ 数据已落地：{out}")
    print(f"  - 行情：{len(quotes)} 只")
    print(f"  - 交易日：{len(cal)} 个")
    print(f"  - 财报：{len(fins_avail)} 条")
    print(f"  - 行业映射：{len(ind)} 条")


if __name__ == "__main__":
    main()

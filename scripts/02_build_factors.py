"""02_build_factors.py：构造因子面板。"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import pandas as pd

from src.factors.engineering import build_factor_panel, save_factor_panel
from src.utils.common import ensure_dir, get_logger, load_config, PROJECT_ROOT

logger = get_logger("build_factors")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "config.yaml"))
    parser.add_argument("--input", default=None, help="processed.pkl 路径")
    parser.add_argument("--output", default=None, help="因子面板输出 parquet 路径")
    args = parser.parse_args()

    cfg = load_config(args.config)
    proc = ensure_dir(cfg["data"]["processed_dir"])
    factor_dir = ensure_dir(cfg["data"]["factor_dir"])
    in_path = Path(args.input) if args.input else proc / "processed.pkl"
    out_path = Path(args.output) if args.output else factor_dir / "factor_panel.parquet"

    logger.info("加载 processed data: %s", in_path)
    with open(in_path, "rb") as f:
        data = pickle.load(f)
    quotes = data["quotes"]
    fins = data["financials"]
    ind = data["industry"]

    logger.info("构造因子面板 (lag=%d, winsorize=%.2f, std=%s, industry_neutral=%s)",
                cfg["factors"]["financial_lag_days"],
                cfg["factors"]["winsorize"],
                cfg["factors"]["standardize"],
                cfg["factors"]["industry_neutral"],
                )
    panel = build_factor_panel(
        quotes,
        fins,
        ind,
        lag_days=cfg["factors"]["financial_lag_days"],
        winsorize_q=cfg["factors"]["winsorize"],
        standardize=cfg["factors"]["standardize"],
        do_industry_neutral=cfg["factors"]["industry_neutral"],
    )
    if panel.empty:
        logger.error("因子面板为空，请检查数据")
        return

    save_factor_panel(panel, out_path)
    n_factors = len([c for c in panel.columns if c not in {"industry", "is_suspended"}])
    print(f"✔ 因子面板已落盘：{out_path}")
    print(f"  - 因子数：{n_factors}")
    print(f"  - 样本数：{len(panel)}")


if __name__ == "__main__":
    main()

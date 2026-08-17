"""05_full_pipeline.py：端到端流水线（fetch → factors → backtest → evaluate）。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from src.utils.common import PROJECT_ROOT, get_logger, load_config

logger = get_logger("pipeline")


def run(cmd: list[str]):
    logger.info("$ %s", " ".join(cmd))
    r = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if r.returncode != 0:
        logger.error("命令失败: %s", " ".join(cmd))
        sys.exit(r.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "config.yaml"))
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--models", default="eq_weight,elastic_net,lightgbm")
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--rebal-freq", type=int, default=21)
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--skip-factors", action="store_true")
    parser.add_argument("--skip-backtest", action="store_true")
    parser.add_argument("--skip-evaluate", action="store_true")
    args = parser.parse_args()

    cfg = load_config(args.config)

    py = sys.executable
    scripts = PROJECT_ROOT / "scripts"

    if not args.skip_fetch:
        cmd = [py, str(scripts / "01_fetch_data.py"), "--config", args.config]
        if args.synthetic:
            cmd.append("--synthetic")
        run(cmd)

    if not args.skip_factors:
        run([py, str(scripts / "02_build_factors.py"), "--config", args.config])

    if not args.skip_backtest:
        run(
            [
                py,
                str(scripts / "03_run_backtest.py"),
                "--config",
                args.config,
                "--models",
                args.models,
                "--top-k",
                str(args.top_k),
                "--rebal-freq",
                str(args.rebal_freq),
                "--cost-bps",
                str(args.cost_bps),
            ]
        )

    if not args.skip_evaluate:
        run([py, str(scripts / "04_evaluate.py"), "--config", args.config])

    logger.info("✔ 全部步骤完成。")


if __name__ == "__main__":
    main()

"""项目级工具：日志、IO、配置加载。"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml


# ========== 路径常量 ==========
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ========== 配置加载 ==========
def load_config(config_path: str | Path | None = None) -> Dict[str, Any]:
    """加载 YAML 配置。

    Args:
        config_path: 配置文件路径；None 时使用默认 config/config.yaml。

    Returns:
        配置字典。
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


# ========== 日志 ==========
def get_logger(
    name: str = "factor_lab",
    log_dir: str | Path | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """构造统一格式的 logger，同时写控制台 + 时间戳文件。

    Args:
        name: logger 名称。
        log_dir: 日志目录；None 时使用 outputs/logs。
        level: 日志级别。

    Returns:
        已配置的 logger。
    """
    if log_dir is None:
        log_dir = PROJECT_ROOT / "outputs" / "logs"
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if getattr(logger, "_configured", False):
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 文件
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    fh = logging.FileHandler(log_dir / f"exp_{ts}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    logger._configured = True  # type: ignore[attr-defined]
    logger.propagate = False
    return logger


# ========== IO 工具 ==========
def ensure_dir(path: str | Path) -> Path:
    """确保目录存在，不存在则创建。"""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def timestamp() -> str:
    """当前 UTC 时间戳字符串。"""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

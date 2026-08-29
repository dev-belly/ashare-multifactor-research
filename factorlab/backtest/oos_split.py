"""样本外切分：expanding-window 训练/测试切片。

核心：永远只让"在切片开始日已发布"的财务因子进入训练/测试。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd

from factorlab.utils.common import get_logger

logger = get_logger(__name__)


@dataclass
class OOSFold:
    """单次 OOS 切分。"""

    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    test_end_inclusive: bool = False


def expanding_window_splits(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    train_min_years: int = 2,
    step_years: int = 1,
    test_years: int = 1,
    step_freq: str = "yearly",
) -> List[OOSFold]:
    """构造 expanding-window 切分。

    规则：
        - fold 0：训练 [start, start+train_min_years)；测试 [start+train_min_years, ...)
        - 后续 fold：训练扩展到上一个 test 末尾，测试再延伸 step_years
        - 直到 end 之前

    Args:
        start: 总起点。
        end: 总终点。
        train_min_years: 初始训练窗口（年）。
        step_years: 每次扩展步长。
        test_years: 测试窗口长度。
        step_freq: 当前仅支持 ``yearly``；窗口长度由 *_years 参数控制。

    Returns:
        OOSFold 列表。
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    folds: List[OOSFold] = []

    if step_freq != "yearly":
        raise ValueError(
            "step_freq 当前仅支持 yearly；train/step/test 窗口均以年为单位"
        )
    if start >= end:
        raise ValueError("start 必须早于 end")
    if min(train_min_years, step_years, test_years) <= 0:
        raise ValueError("train_min_years/step_years/test_years 必须为正数")
    if step_years < test_years:
        raise ValueError("step_years 不能小于 test_years，否则 OOS 区间会重叠")

    train_end = start + pd.DateOffset(years=train_min_years)
    fold_id = 0
    while train_end < end:
        test_start = train_end
        test_end = min(test_start + pd.DateOffset(years=test_years), end)
        folds.append(
            OOSFold(
                fold_id=fold_id,
                train_start=start,
                train_end=test_start,
                test_start=test_start,
                test_end=test_end,
                # Data loaders treat the configured global end date as
                # inclusive. Only the final fold may include its right edge;
                # intermediate folds stay half-open to avoid overlap.
                test_end_inclusive=test_end == end,
            )
        )
        logger.info(
            "fold %d: train [%s, %s) | test [%s, %s%s",
            fold_id,
            start.date(),
            test_start.date(),
            test_start.date(),
            test_end.date(),
            "]" if test_end == end else ")",
        )
        # 推进
        train_end = test_start + pd.DateOffset(years=step_years)
        fold_id += 1

    return folds


def filter_panel_by_fold(
    panel: pd.DataFrame,
    fold: OOSFold,
    fin_dates: pd.Series | None = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """按 fold 切分面板。返回 (train_df, test_df)。

    关键：财务因子只能用 publish_date + lag 之后的日期。
    这里默认 panel 已是按 available_date 对齐后的"已可用"面板，
    所以日期过滤即可。
    """
    if not isinstance(panel.index, pd.MultiIndex):
        raise ValueError("panel 必须是 (date, code) MultiIndex")

    train = panel.loc[
        (panel.index.get_level_values("date") >= fold.train_start)
        & (panel.index.get_level_values("date") < fold.train_end)
    ]
    test_dates = panel.index.get_level_values("date")
    test_end_mask = (
        test_dates <= fold.test_end
        if fold.test_end_inclusive
        else test_dates < fold.test_end
    )
    test = panel.loc[(test_dates >= fold.test_start) & test_end_mask]
    return train, test

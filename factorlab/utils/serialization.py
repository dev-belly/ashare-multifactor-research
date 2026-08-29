"""Helpers for emitting standards-compliant JSON research artifacts."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def json_safe(value: Any) -> Any:
    """Recursively convert pandas/numpy values and non-finite floats.

    Python's ``json`` module otherwise emits ``NaN``/``Infinity`` tokens that
    are not valid JSON and later break browser ``response.json()`` or strict
    API serializers.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if pd.isna(value):
        return None
    return value

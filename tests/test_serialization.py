from __future__ import annotations

import json

import numpy as np
import pandas as pd

from factorlab.utils.serialization import json_safe


def test_json_safe_replaces_non_finite_and_numpy_values() -> None:
    value = {
        "nan": float("nan"),
        "inf": np.float64("inf"),
        "count": np.int64(3),
        "when": pd.Timestamp("2024-01-02"),
        "values": np.array([1.0, np.nan]),
    }

    safe = json_safe(value)
    encoded = json.dumps(safe, allow_nan=False)

    assert safe["nan"] is None
    assert safe["inf"] is None
    assert safe["count"] == 3
    assert safe["values"] == [1.0, None]
    assert "NaN" not in encoded
    assert "Infinity" not in encoded

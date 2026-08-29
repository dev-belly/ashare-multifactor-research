from __future__ import annotations

import numpy as np
import pandas as pd

from factorlab.models.deep import DeepFactorModel


def test_deep_model_is_reproducible_for_same_seed() -> None:
    rng = np.random.default_rng(123)
    index = pd.RangeIndex(240)
    features = pd.DataFrame(rng.normal(size=(240, 4)), index=index)
    target = pd.Series(rng.normal(size=240), index=index)

    kwargs = {
        "hidden_dims": [8, 4],
        "dropout": 0.1,
        "epochs": 3,
        "batch_size": 64,
        "patience": 3,
        "seed": 7,
    }
    first = DeepFactorModel(**kwargs).fit(features, target).predict(features)
    second = DeepFactorModel(**kwargs).fit(features, target).predict(features)

    np.testing.assert_allclose(first.to_numpy(), second.to_numpy(), rtol=0, atol=0)

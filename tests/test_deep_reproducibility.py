from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

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


@pytest.mark.parametrize("epochs", [0, -1, 1.5, True])
def test_deep_model_rejects_invalid_epochs(epochs: object) -> None:
    with pytest.raises(ValueError, match="epochs must be a positive integer"):
        DeepFactorModel(epochs=epochs)  # type: ignore[arg-type]


@pytest.mark.parametrize("batch_size", [0, 1, 1.5, True])
def test_deep_model_rejects_batch_sizes_that_break_batchnorm(
    batch_size: object,
) -> None:
    with pytest.raises(ValueError, match="batch_size must be an integer"):
        DeepFactorModel(batch_size=batch_size)  # type: ignore[arg-type]


def test_deep_model_handles_singleton_final_batch() -> None:
    rng = np.random.default_rng(321)
    features = pd.DataFrame(rng.normal(size=(12, 3)))
    target = pd.Series(rng.normal(size=12))

    # The validation split leaves 11 training rows, so batch_size=5 would
    # ordinarily produce batches of 5, 5, and 1 and crash BatchNorm.
    prediction = (
        DeepFactorModel(
            hidden_dims=[4],
            dropout=0.0,
            epochs=1,
            batch_size=5,
            patience=1,
            seed=9,
        )
        .fit(features, target, min_obs=1)
        .predict(features)
    )

    assert prediction.notna().all()

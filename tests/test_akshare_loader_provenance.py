from types import SimpleNamespace
import sys

import pandas as pd
import pytest

from factorlab.data.akshare_loader import AkShareLoader, DataLoadError


def test_named_index_universe_is_resolved_before_explicit_limit(tmp_path) -> None:
    calls: list[str] = []

    def index_members(symbol: str) -> pd.DataFrame:
        calls.append(symbol)
        return pd.DataFrame({"成分券代码": ["600003", "000002", "600001", "000002"]})

    fake_ak = SimpleNamespace(index_stock_cons_csindex=index_members)
    loader = AkShareLoader(universe="hs300", max_symbols=2, cache_dir=tmp_path)

    assert loader._resolve_universe_codes(fake_ak) == ["000002", "600001"]
    assert calls == ["000300"]
    assert loader._universe_total == 3
    assert loader._universe_truncated is True


def test_akshare_failure_is_fail_fast_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace())
    loader = AkShareLoader(source="akshare", cache_dir=tmp_path)
    monkeypatch.setattr(
        loader,
        "_load_akshare_calendar",
        lambda *_: (_ for _ in ()).throw(OSError("calendar endpoint down")),
    )

    with pytest.raises(DataLoadError, match="fallback is disabled"):
        loader.load_all("2024-01-02", "2024-01-08")

    assert loader.metadata["actual_data_source"] is None
    assert "calendar endpoint down" in loader.metadata["fallback_reason"]


def test_explicit_fallback_records_actual_source_and_reason(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace())
    loader = AkShareLoader(source="akshare", cache_dir=tmp_path, allow_fallback=True)
    monkeypatch.setattr(
        loader,
        "_load_akshare_calendar",
        lambda *_: (_ for _ in ()).throw(ConnectionError("network unavailable")),
    )

    quotes, financials, industry, calendar = loader.load_all("2024-01-02", "2024-01-08")
    meta = loader.metadata

    assert quotes and not financials.empty and not industry.empty and len(calendar)
    assert meta["requested_data_source"] == "akshare"
    assert meta["actual_data_source"] == "synthetic"
    assert "network unavailable" in meta["fallback_reason"]
    assert meta["data_components"]["financials"]["complete"] is True


def test_incomplete_real_components_are_never_labelled_complete(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace())
    calendar = pd.bdate_range("2024-01-02", periods=2)
    quotes = {"000001.SZ": pd.DataFrame({"close": [10.0, 10.1]}, index=calendar)}
    partial = (quotes, pd.DataFrame(), pd.DataFrame(), calendar)

    strict = AkShareLoader(source="akshare", cache_dir=tmp_path)
    monkeypatch.setattr(strict, "_load_akshare_calendar", lambda *_: calendar)
    monkeypatch.setattr(strict, "_load_akshare", lambda *_, **__: partial)
    with pytest.raises(DataLoadError, match="financials, industry"):
        strict.load_all("2024-01-02", "2024-01-03")

    allowed = AkShareLoader(
        source="akshare",
        cache_dir=tmp_path,
        allow_partial_real_data=True,
    )
    monkeypatch.setattr(allowed, "_load_akshare_calendar", lambda *_: calendar)
    monkeypatch.setattr(allowed, "_load_akshare", lambda *_, **__: partial)
    allowed.load_all("2024-01-02", "2024-01-03")

    meta = allowed.metadata
    assert meta["actual_data_source"] == "akshare_partial"
    assert meta["fallback_reason"] is None
    assert meta["data_components"]["financials"]["complete"] is False
    assert meta["data_components"]["industry"]["complete"] is False

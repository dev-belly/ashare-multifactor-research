"""AkShare data loading with explicit provenance and completeness checks.

The synthetic dataset is useful for smoke tests, but it is not a substitute for
real market data. A failed or incomplete AkShare request is therefore either a
hard error (the default) or an *explicitly recorded* fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Dict, Tuple

import pandas as pd

from factorlab.data.calendar import get_trading_calendar
from factorlab.data.synthetic import (
    generate_synthetic_financials,
    generate_synthetic_industry,
    generate_synthetic_quotes,
    generate_synthetic_universe,
)
from factorlab.utils.common import ensure_dir, get_logger

logger = get_logger(__name__)


class DataLoadError(RuntimeError):
    """The requested data source could not be loaded faithfully."""


class IncompleteRealDataError(DataLoadError):
    """AkShare returned only some components required by the pipeline."""


class AkShareLoader:
    """A-share loader with auditable source selection.

    Args:
        source: ``"akshare"`` or ``"synthetic"``.
        cache_dir: Reserved for raw-data caching.
        universe: ``all``, ``hs300``, ``zz500``, ``zz1000`` or an explicit
            sequence of six-digit stock codes.
        max_symbols: Explicit cap on the selected universe. ``None`` disables
            the cap. The default is deliberately visible in load metadata.
        allow_fallback: Permit AkShare failures/incompleteness to use synthetic
            data. Defaults to fail-fast.
        allow_partial_real_data: Permit quote-only/partially covered AkShare
            data. Such runs are labelled ``akshare_partial``, never ``akshare``.
    """

    DEFAULT_MAX_SYMBOLS = 50
    INDEX_CODES = {"hs300": "000300", "zz500": "000905", "zz1000": "000852"}
    FINANCIAL_REQUIRED_COLUMNS = {
        "code",
        "period_end",
        "publish_date",
        "revenue",
        "net_profit",
        "equity",
        "total_assets",
        "operating_cf",
        "gross_profit",
        "shares",
    }

    def __init__(
        self,
        source: str = "akshare",
        cache_dir: str = "data/raw",
        universe: str | Sequence[str] = "all",
        max_symbols: int | None = DEFAULT_MAX_SYMBOLS,
        allow_fallback: bool = False,
        allow_partial_real_data: bool = False,
    ):
        source = str(source).lower().strip()
        if source not in {"akshare", "synthetic"}:
            raise ValueError(f"unsupported data source: {source!r}")
        if max_symbols is not None and int(max_symbols) <= 0:
            raise ValueError("max_symbols must be positive or None")

        self.source = source
        self.cache_dir = ensure_dir(cache_dir)
        self.universe = universe
        self.max_symbols = int(max_symbols) if max_symbols is not None else None
        self.allow_fallback = bool(allow_fallback)
        self.allow_partial_real_data = bool(allow_partial_real_data)
        self._universe_total = 0
        self._universe_truncated = False
        self._metadata: dict[str, Any] = {
            "requested_data_source": self.source,
            "actual_data_source": None,
            "fallback_reason": None,
            "requested_universe": self._universe_label(),
            "universe_limit": self.max_symbols,
            "universe_available": None,
            "universe_loaded": 0,
            "universe_truncated": False,
            "data_components": {},
        }

    @property
    def metadata(self) -> dict[str, Any]:
        """JSON-serialisable metadata describing what was actually loaded."""
        return deepcopy(self._metadata)

    def load_all(
        self,
        start_date: str = "2018-01-01",
        end_date: str = "2025-12-31",
    ) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        """Load quotes, financials, industry mapping, and trading calendar."""
        if self.source == "synthetic":
            cal = get_trading_calendar(start_date, end_date, source="synthetic")
            result = self._load_synthetic(cal)
            self._record_success("synthetic", result)
            return result

        attempted_components: dict[str, Any] = {}
        try:
            # calendar.get_trading_calendar(source="akshare") silently falls
            # back to weekdays, which would create an undisclosed mixed source.
            import akshare as ak

            cal = self._load_akshare_calendar(ak, start_date, end_date)
            result = self._load_akshare(cal, start_date, end_date, ak_module=ak)
            attempted_components = self._component_status(*result)
            incomplete = [
                name
                for name, status in attempted_components.items()
                if not status.get("complete", False)
            ]
            if incomplete and not self.allow_partial_real_data:
                raise IncompleteRealDataError(
                    "AkShare data incomplete: " + ", ".join(incomplete)
                )

            actual_source = "akshare_partial" if incomplete else "akshare"
            self._record_success(actual_source, result, attempted_components)
            return result
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            self._metadata["fallback_reason"] = reason
            if attempted_components:
                self._metadata["attempted_data_components"] = attempted_components
            if not self.allow_fallback:
                raise DataLoadError(
                    "AkShare load failed and synthetic fallback is disabled: " + reason
                ) from exc

            logger.warning(
                "AkShare load failed (%s); using explicitly allowed synthetic fallback",
                reason,
            )
            cal = get_trading_calendar(start_date, end_date, source="synthetic")
            result = self._load_synthetic(cal)
            self._record_success("synthetic", result, fallback_reason=reason)
            if attempted_components:
                self._metadata["attempted_data_components"] = attempted_components
            return result

    def _load_synthetic(
        self, cal: pd.DatetimeIndex
    ) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        universe = generate_synthetic_universe(seed=42)
        quotes = generate_synthetic_quotes(universe, cal, seed=42)
        fins = generate_synthetic_financials(universe, cal, seed=42)
        ind = generate_synthetic_industry(universe)
        return quotes, fins, ind, cal

    @staticmethod
    def _load_akshare_calendar(
        ak: Any, start_date: str, end_date: str
    ) -> pd.DatetimeIndex:
        raw = ak.tool_trade_date_hist_sina()
        if raw is None or raw.empty or "trade_date" not in raw.columns:
            raise DataLoadError("AkShare returned no valid trading calendar")
        dates = pd.to_datetime(raw["trade_date"], errors="coerce").dropna()
        mask = (dates >= pd.Timestamp(start_date)) & (dates <= pd.Timestamp(end_date))
        cal = pd.DatetimeIndex(dates.loc[mask].sort_values().unique())
        if cal.empty:
            raise DataLoadError(
                "AkShare trading calendar is empty for requested date range"
            )
        return cal

    def _load_akshare(
        self,
        cal: pd.DatetimeIndex,
        start_date: str,
        end_date: str,
        ak_module: Any | None = None,
    ) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        if ak_module is None:
            import akshare as ak_module

        codes = self._resolve_universe_codes(ak_module)
        if not codes:
            raise DataLoadError(
                f"AkShare returned an empty universe for {self._universe_label()}"
            )

        quotes: Dict[str, pd.DataFrame] = {}
        for base_code in codes:
            try:
                raw = ak_module.stock_zh_a_hist(
                    symbol=base_code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="qfq",
                )
                if raw is None or raw.empty:
                    continue
                df = raw.rename(
                    columns={
                        "日期": "date",
                        "开盘": "open",
                        "最高": "high",
                        "最低": "low",
                        "收盘": "close",
                        "成交量": "volume",
                        "成交额": "amount",
                    }
                )
                required = {"date", "open", "high", "low", "close", "volume"}
                missing = required.difference(df.columns)
                if missing:
                    logger.debug(
                        "skip %s: quote columns missing: %s", base_code, sorted(missing)
                    )
                    continue
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date"]).set_index("date").sort_index()
                df["adj_factor"] = 1.0
                code = f"{base_code}.{self._detect_exchange(base_code)}"
                quotes[code] = df
            except Exception as exc:
                logger.debug("skip %s quotes: %s", base_code, exc)

        if not quotes:
            raise DataLoadError("AkShare returned no usable quote history")

        # The industry-board list is not a stock-to-industry mapping. Query
        # per-stock metadata instead and report exact coverage.
        industry_rows = []
        for code in quotes:
            base_code = code.split(".")[0]
            try:
                info = ak_module.stock_individual_info_em(symbol=base_code)
                if (
                    info is None
                    or info.empty
                    or not {"item", "value"}.issubset(info.columns)
                ):
                    continue
                values = info.set_index("item")["value"]
                industry = values.get("行业")
                if pd.notna(industry) and str(industry).strip():
                    industry_rows.append(
                        {"code": code, "industry": str(industry).strip()}
                    )
            except Exception as exc:
                logger.debug("skip %s industry: %s", base_code, exc)
        industry_map = pd.DataFrame(industry_rows, columns=["code", "industry"])

        # Do not fabricate point-in-time fundamentals from unnormalised raw
        # statements. Until report/publish dates and fields are normalised,
        # this component is explicitly partial and strict mode rejects it.
        financials = pd.DataFrame(columns=sorted(self.FINANCIAL_REQUIRED_COLUMNS))
        return quotes, financials, industry_map, cal

    def _resolve_universe_codes(self, ak: Any) -> list[str]:
        """Resolve the configured universe before applying the explicit cap."""
        if isinstance(self.universe, str):
            label = self.universe.lower().strip()
            if label == "all":
                frame = ak.stock_zh_a_spot_em()
                code_col = self._find_column(frame, ("代码", "code", "symbol"))
            elif label in self.INDEX_CODES:
                index_code = self.INDEX_CODES[label]
                if hasattr(ak, "index_stock_cons_csindex"):
                    frame = ak.index_stock_cons_csindex(symbol=index_code)
                    code_col = self._find_column(
                        frame,
                        ("成分券代码", "品种代码", "代码", "code", "symbol"),
                    )
                else:
                    frame = ak.index_stock_cons(symbol=index_code)
                    code_col = self._find_column(
                        frame, ("品种代码", "代码", "code", "symbol")
                    )
            else:
                raise ValueError(
                    f"unsupported universe {self.universe!r}; "
                    "expected all/hs300/zz500/zz1000"
                )
            raw_codes = frame[code_col].tolist()
        elif isinstance(self.universe, Sequence):
            raw_codes = list(self.universe)
        else:
            raise TypeError(
                "universe must be a recognised name or a sequence of stock codes"
            )

        codes = sorted(
            code
            for code in {self._normalise_base_code(value) for value in raw_codes}
            if code is not None
        )
        self._universe_total = len(codes)
        if self.max_symbols is not None and len(codes) > self.max_symbols:
            self._universe_truncated = True
            logger.info(
                "AkShare universe %s explicitly capped at %d of %d symbols",
                self._universe_label(),
                self.max_symbols,
                len(codes),
            )
            codes = codes[: self.max_symbols]
        else:
            self._universe_truncated = False
        return codes

    def _component_status(
        self,
        quotes: Dict[str, pd.DataFrame],
        financials: pd.DataFrame,
        industry_map: pd.DataFrame,
        calendar: pd.DatetimeIndex,
    ) -> dict[str, dict[str, Any]]:
        quote_codes = set(quotes)
        fin_columns = set(financials.columns)
        fin_codes = (
            set(financials["code"].astype(str)) if "code" in financials else set()
        )
        ind_codes = (
            set(industry_map["code"].astype(str)) if "code" in industry_map else set()
        )
        quote_count = len(quote_codes)

        fin_missing = sorted(self.FINANCIAL_REQUIRED_COLUMNS.difference(fin_columns))
        fin_coverage = (
            len(quote_codes.intersection(fin_codes)) / quote_count
            if quote_count
            else 0.0
        )
        ind_coverage = (
            len(quote_codes.intersection(ind_codes)) / quote_count
            if quote_count
            else 0.0
        )
        financial_complete = (
            not financials.empty and not fin_missing and fin_coverage == 1.0
        )
        industry_complete = (
            not industry_map.empty
            and {"code", "industry"}.issubset(industry_map.columns)
            and ind_coverage == 1.0
        )
        return {
            "calendar": {"complete": bool(len(calendar)), "rows": int(len(calendar))},
            "quotes": {"complete": bool(quote_count), "symbols": quote_count},
            "financials": {
                "complete": financial_complete,
                "symbols": len(fin_codes),
                "coverage": round(float(fin_coverage), 6),
                "missing_columns": fin_missing,
            },
            "industry": {
                "complete": industry_complete,
                "symbols": len(ind_codes),
                "coverage": round(float(ind_coverage), 6),
            },
        }

    def _record_success(
        self,
        actual_source: str,
        result: Tuple[
            Dict[str, pd.DataFrame],
            pd.DataFrame,
            pd.DataFrame,
            pd.DatetimeIndex,
        ],
        components: dict[str, Any] | None = None,
        fallback_reason: str | None = None,
    ) -> None:
        quotes, financials, industry_map, calendar = result
        components = components or self._component_status(
            quotes, financials, industry_map, calendar
        )
        self._metadata.update(
            {
                "actual_data_source": actual_source,
                "fallback_reason": fallback_reason,
                "universe_available": self._universe_total or len(quotes),
                "universe_loaded": len(quotes),
                "universe_truncated": self._universe_truncated,
                "data_components": components,
            }
        )

    def _universe_label(self) -> str | list[str]:
        if isinstance(self.universe, str):
            return self.universe
        return [str(code) for code in self.universe]

    @staticmethod
    def _find_column(frame: pd.DataFrame, candidates: Sequence[str]) -> str:
        if frame is None or frame.empty:
            raise DataLoadError("AkShare returned an empty universe table")
        for column in candidates:
            if column in frame.columns:
                return column
        raise DataLoadError(
            "AkShare universe table has no recognised code column; "
            f"available={list(frame.columns)}"
        )

    @staticmethod
    def _normalise_base_code(value: Any) -> str | None:
        if pd.isna(value):
            return None
        text = str(value).strip().upper()
        for prefix in ("SH", "SZ", "BJ"):
            if text.startswith(prefix):
                text = text[len(prefix) :]
        if "." in text:
            text = text.split(".", 1)[0]
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return None
        return digits.zfill(6)[-6:]

    @staticmethod
    def _detect_exchange(code: str) -> str:
        """Infer exchange suffix for mainland equity codes."""
        code = str(code).zfill(6)
        if code.startswith(("60", "68", "90")):
            return "SH"
        if code.startswith(("00", "30", "20")):
            return "SZ"
        if code.startswith(("4", "8", "92")):
            return "BJ"
        raise ValueError(f"cannot infer exchange for A-share code {code!r}")

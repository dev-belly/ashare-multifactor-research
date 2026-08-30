"""FastAPI 服务：暴露预计算结果与触发流水线。

设计：
    - 主要读取 outputs/results/results.json（由 `factorlab run` 生成）。
    - 提供 /api/run 触发后台重算（接收回测参数）。
    - 若 frontend/dist 存在，则同时托管 SPA（便于单容器部署）。
"""

from __future__ import annotations

import json
import os
import secrets
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from factorlab.config import Settings
from factorlab.utils.common import PROJECT_ROOT

RESULTS_DIR = PROJECT_ROOT / "outputs" / "results"
RESULTS_PATH = RESULTS_DIR / "results.json"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_STATIC = PROJECT_ROOT / "frontend" / "static-build"
# 优先使用经 vite 构建的 dist；缺失时回退到免构建（CDN）的 static-build。
FRONTEND_DIR = (
    FRONTEND_DIST
    if FRONTEND_DIST.exists()
    else (FRONTEND_STATIC if FRONTEND_STATIC.exists() else None)
)

_app_lock = threading.Lock()
_run_state: Dict[str, Any] = {"running": False, "last_run": None}


class ResultsLoadError(RuntimeError):
    """A machine-readable failure while loading the persisted result artifact."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _ready_status() -> Dict[str, Any]:
    return {"status": "ready", "code": None, "message": None}


def _unavailable_status(error: ResultsLoadError) -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "code": error.code,
        "message": error.message,
    }


def _refresh_results(application: FastAPI) -> Dict[str, Any]:
    """Refresh the in-memory snapshot without hiding load failures."""
    try:
        results = _load_results()
    except ResultsLoadError as error:
        application.state.results = {}
        application.state.results_status = _unavailable_status(error)
    else:
        application.state.results = results
        application.state.results_status = _ready_status()
    return application.state.results_status


@asynccontextmanager
async def _lifespan(application: FastAPI):
    application.state.settings = Settings.load()
    _refresh_results(application)
    yield


app = FastAPI(title="FactorLab API", version="0.2.0", lifespan=_lifespan)


class RunRequest(BaseModel):
    """Validated parameters for an explicitly authenticated research run."""

    models: str = Field(
        default="eq_weight,elastic_net,lightgbm,deep",
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9_,]+$",
    )
    # The backtest has a fixed 5% per-name cap and does not hide residual cash.
    # At least 20 names are therefore required for a feasible fully invested book.
    top_k: int = Field(default=20, ge=20, le=500)
    rebal_freq: int = Field(default=21, ge=1, le=252)
    cost_bps: float = Field(default=20.0, ge=0.0, le=1_000.0)
    data_source: Optional[str] = Field(default=None, pattern=r"^(synthetic|akshare)$")
    hpo: int = Field(default=0, ge=0, le=100)

    @field_validator("models")
    @classmethod
    def _validate_models(cls, value: str) -> str:
        allowed = {
            "eq_weight",
            "elastic_net",
            "lightgbm",
            "deep",
            "cross_section",
        }
        selected = [name for name in value.split(",") if name]
        unknown = sorted(set(selected).difference(allowed))
        if not selected or unknown:
            detail = ", ".join(unknown) if unknown else "empty model list"
            raise ValueError(f"unsupported models: {detail}")
        return ",".join(dict.fromkeys(selected))


def _require_run_token(
    token: Optional[str] = Header(default=None, alias="X-FactorLab-Run-Token"),
) -> None:
    """Keep expensive mutation endpoints disabled unless a secret is set.

    The token is intentionally read only from the server environment.  It is
    never returned by the config endpoint or embedded into the browser bundle.
    """
    expected = os.environ.get("FACTORLAB_RUN_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Remote runs are disabled; use the factorlab CLI or configure FACTORLAB_RUN_TOKEN.",
        )
    if token is None or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid run token")


def _load_results() -> Dict[str, Any]:
    if not RESULTS_PATH.exists():
        raise ResultsLoadError(
            "results_missing",
            "Research results are not available. Run `factorlab run` to create results.json.",
        )
    try:
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            results = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as error:
        raise ResultsLoadError(
            "results_invalid",
            "results.json could not be read as valid JSON. Regenerate the result artifact.",
        ) from error
    if not isinstance(results, dict):
        raise ResultsLoadError(
            "results_invalid",
            "results.json must contain a JSON object. Regenerate the result artifact.",
        )
    return results


def _results() -> Dict[str, Any]:
    if not hasattr(app.state, "results"):
        _refresh_results(app)
    return app.state.results


def _results_status() -> Dict[str, Any]:
    if not hasattr(app.state, "results_status"):
        _refresh_results(app)
    return app.state.results_status


def _mapping_section(name: str) -> Dict[str, Any]:
    value = _results().get(name)
    return value if isinstance(value, dict) else {}


@app.get("/api/health")
def health() -> Dict[str, Any]:
    status = _results_status()
    return {
        "status": "ok" if status["status"] == "ready" else "degraded",
        "results": status,
        "has_results": status["status"] == "ready" and bool(_results()),
        "models": list(_mapping_section("model_nav")),
    }


@app.get("/api/config")
def get_config() -> Dict[str, Any]:
    return app.state.settings.as_dict()


@app.get("/api/meta")
def get_meta() -> Dict[str, Any]:
    return _mapping_section("meta")


@app.get("/api/results")
def get_results() -> Any:
    """返回全部预计算结果（前端一次性拉取）。"""
    status = _results_status()
    if status["status"] != "ready":
        return JSONResponse(status_code=503, content={"error": status})
    return _results()


@app.get("/api/models")
def get_models() -> Dict[str, Any]:
    out = {}
    for name, m in _mapping_section("model_nav").items():
        if not isinstance(m, dict):
            continue
        out[name] = {"perf": m.get("perf", {}), "turnover": m.get("turnover", {})}
    return out


@app.get("/api/nav/{model}")
def get_nav(model: str) -> Dict[str, Any]:
    m = _mapping_section("model_nav").get(model)
    if not isinstance(m, dict):
        raise HTTPException(status_code=404, detail=f"model {model} not found")
    return {"model": model, "nav": m.get("nav", {}), "perf": m.get("perf", {})}


@app.get("/api/ic")
def get_ic() -> Dict[str, Any]:
    ic_summary = _results().get("ic_summary")
    return {
        "ic_summary": ic_summary if isinstance(ic_summary, list) else [],
        "factor_decay": _mapping_section("factor_decay"),
    }


@app.get("/api/groups")
def get_groups() -> Dict[str, Any]:
    return {"group_returns": _mapping_section("group_returns")}


@app.get("/api/robustness")
def get_robustness() -> Dict[str, Any]:
    return {"robustness": _mapping_section("robustness")}


@app.get("/api/feature-importance")
def get_feature_importance() -> Dict[str, Any]:
    return {"feature_importance": _mapping_section("feature_importance")}


@app.get("/api/cost-scenarios")
def get_cost_scenarios() -> Dict[str, Any]:
    return {"cost_scenarios": _mapping_section("cost_scenarios")}


@app.get("/api/run/state")
def run_state(_: None = Depends(_require_run_token)) -> Dict[str, Any]:
    return _run_state


def _do_run(
    models: str,
    top_k: int,
    rebal_freq: int,
    cost_bps: float,
    data_source: Optional[str],
    hpo: int,
) -> None:
    from factorlab.pipeline import run_pipeline

    try:
        _do_run.path = run_pipeline(
            models=models,
            top_k=top_k,
            rebal_freq=rebal_freq,
            cost_bps=cost_bps,
            data_source=data_source,
            hpo_trials=hpo,
        )
        with _app_lock:
            status = _refresh_results(app)
            if status["status"] != "ready":
                raise RuntimeError(status["message"])
            _run_state["running"] = False
            _run_state["last_run"] = str(_do_run.path)
    except Exception as e:  # noqa: BLE001
        with _app_lock:
            _run_state["running"] = False
            _run_state["error"] = str(e)


@app.post("/api/run")
def trigger_run(
    background: BackgroundTasks,
    request: RunRequest,
    _: None = Depends(_require_run_token),
) -> Dict[str, Any]:
    with _app_lock:
        if _run_state["running"]:
            return {"status": "already_running", "state": _run_state}
        _run_state["running"] = True
        _run_state.pop("error", None)
    background.add_task(
        _do_run,
        request.models,
        request.top_k,
        request.rebal_freq,
        request.cost_bps,
        request.data_source,
        request.hpo,
    )
    return {"status": "started", "params": request.model_dump()}


@app.post("/api/reload")
def reload(_: None = Depends(_require_run_token)) -> Dict[str, Any]:
    with _app_lock:
        results_status = _refresh_results(app)
    return {
        "status": "reloaded" if results_status["status"] == "ready" else "unavailable",
        "results": results_status,
        "has_results": results_status["status"] == "ready" and bool(app.state.results),
    }


# ========== 托管前端（若存在） ==========
if FRONTEND_DIR is not None:
    _frontend_root = FRONTEND_DIR.resolve()
    _assets_dir = FRONTEND_DIR / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        target = (_frontend_root / full_path).resolve()
        if not target.is_relative_to(_frontend_root):
            raise HTTPException(status_code=404, detail="file not found")
        if target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(_frontend_root / "index.html")

else:

    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse(
            {
                "message": "FactorLab API",
                "docs": "/docs",
                "frontend": "not built (see frontend/)",
            }
        )

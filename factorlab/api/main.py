"""FastAPI 服务：暴露预计算结果与触发流水线。

设计：
    - 主要读取 outputs/results/results.json（由 `factorlab run` 生成）。
    - 提供 /api/run 触发后台重算（接收回测参数）。
    - 若 frontend/dist 存在，则同时托管 SPA（便于单容器部署）。
"""
from __future__ import annotations

import json
import threading
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from factorlab.config import Settings
from factorlab.utils.common import PROJECT_ROOT

app = FastAPI(title="FactorLab API", version="0.2.0")

RESULTS_DIR = PROJECT_ROOT / "outputs" / "results"
RESULTS_PATH = RESULTS_DIR / "results.json"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_STATIC = PROJECT_ROOT / "frontend" / "static-build"
# 优先使用经 vite 构建的 dist；缺失时回退到免构建（CDN）的 static-build。
FRONTEND_DIR = (
    FRONTEND_DIST if FRONTEND_DIST.exists()
    else (FRONTEND_STATIC if FRONTEND_STATIC.exists() else None)
)

_app_lock = threading.Lock()
_run_state: dict[str, Any] = {"running": False, "last_run": None}


def _load_results() -> dict[str, Any]:
    if not RESULTS_PATH.exists():
        return {}
    try:
        with open(RESULTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@app.on_event("startup")
def _startup() -> None:
    app.state.settings = Settings.load()
    app.state.results = _load_results()


def _results() -> dict[str, Any]:
    if not hasattr(app.state, "results"):
        app.state.results = _load_results()
    return app.state.results


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "has_results": bool(_results()), "models": list(_results().get("model_nav", {}).keys())}


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return app.state.settings.as_dict()


@app.get("/api/meta")
def get_meta() -> dict[str, Any]:
    return _results().get("meta", {})


@app.get("/api/results")
def get_results() -> dict[str, Any]:
    """返回全部预计算结果（前端一次性拉取）。"""
    return _results()


@app.get("/api/models")
def get_models() -> dict[str, Any]:
    res = _results()
    out = {}
    for name, m in res.get("model_nav", {}).items():
        out[name] = {"perf": m.get("perf", {}), "turnover": m.get("turnover", {})}
    return out


@app.get("/api/nav/{model}")
def get_nav(model: str) -> dict[str, Any]:
    m = _results().get("model_nav", {}).get(model)
    if not m:
        raise HTTPException(status_code=404, detail=f"model {model} not found")
    return {"model": model, "nav": m["nav"], "perf": m["perf"]}


@app.get("/api/ic")
def get_ic() -> dict[str, Any]:
    return {"ic_summary": _results().get("ic_summary", []), "factor_decay": _results().get("factor_decay", {})}


@app.get("/api/groups")
def get_groups() -> dict[str, Any]:
    return {"group_returns": _results().get("group_returns", {})}


@app.get("/api/robustness")
def get_robustness() -> dict[str, Any]:
    return {"robustness": _results().get("robustness", {})}


@app.get("/api/feature-importance")
def get_feature_importance() -> dict[str, Any]:
    return {"feature_importance": _results().get("feature_importance", {})}


@app.get("/api/cost-scenarios")
def get_cost_scenarios() -> dict[str, Any]:
    return {"cost_scenarios": _results().get("cost_scenarios", {})}


@app.get("/api/run/state")
def run_state() -> dict[str, Any]:
    return _run_state


def _do_run(models: str, top_k: int, rebal_freq: int, cost_bps: float, data_source: str | None, hpo: int) -> None:
    from factorlab.pipeline import run_pipeline

    try:
        _do_run.path = run_pipeline(
            models=models, top_k=top_k, rebal_freq=rebal_freq, cost_bps=cost_bps,
            data_source=data_source, hpo_trials=hpo,
        )
        with _app_lock:
            app.state.results = _load_results()
            _run_state["running"] = False
            _run_state["last_run"] = str(_do_run.path)
    except Exception as e:  # noqa: BLE001
        with _app_lock:
            _run_state["running"] = False
            _run_state["error"] = str(e)


@app.post("/api/run")
def trigger_run(
    background: BackgroundTasks,
    models: str = "eq_weight,elastic_net,lightgbm,deep",
    top_k: int = 20,
    rebal_freq: int = 21,
    cost_bps: float = 20.0,
    data_source: str | None = None,
    hpo: int = 0,
) -> dict[str, Any]:
    with _app_lock:
        if _run_state["running"]:
            return {"status": "already_running", "state": _run_state}
        _run_state["running"] = True
        _run_state.pop("error", None)
    background.add_task(_do_run, models, top_k, rebal_freq, cost_bps, data_source, hpo)
    return {"status": "started", "params": {"models": models, "top_k": top_k, "cost_bps": cost_bps, "hpo": hpo}}


@app.post("/api/reload")
def reload() -> dict[str, Any]:
    with _app_lock:
        app.state.results = _load_results()
    return {"status": "reloaded", "has_results": bool(app.state.results)}


# ========== 托管前端（若存在） ==========
if FRONTEND_DIR is not None:
    _assets_dir = FRONTEND_DIR / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        target = FRONTEND_DIR / full_path
        if target.exists() and target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIR / "index.html")

else:
    @app.get("/")
    def root() -> JSONResponse:
        return JSONResponse({"message": "FactorLab API", "docs": "/docs", "frontend": "not built (see frontend/)"})

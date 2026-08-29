from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from factorlab.api import main


def test_results_endpoint_reports_a_missing_artifact(
    monkeypatch, tmp_path: Path
) -> None:
    missing_path = tmp_path / "missing" / "results.json"
    monkeypatch.setattr(main, "RESULTS_PATH", missing_path)

    with TestClient(main.app) as client:
        response = client.get("/api/results")
        health = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["error"] == {
        "status": "unavailable",
        "code": "results_missing",
        "message": "Research results are not available. Run `factorlab run` to create results.json.",
    }
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["results"]["code"] == "results_missing"
    assert health.json()["has_results"] is False


def test_results_endpoint_reports_invalid_json(monkeypatch, tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text('{"meta":', encoding="utf-8")
    monkeypatch.setattr(main, "RESULTS_PATH", results_path)

    with TestClient(main.app) as client:
        response = client.get("/api/results")

    assert response.status_code == 503
    assert response.json()["error"]["status"] == "unavailable"
    assert response.json()["error"]["code"] == "results_invalid"


def test_results_endpoint_rejects_a_non_object_root(
    monkeypatch, tmp_path: Path
) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(main, "RESULTS_PATH", results_path)

    with TestClient(main.app) as client:
        response = client.get("/api/results")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "results_invalid"


def test_empty_results_object_is_valid_and_consumable(
    monkeypatch, tmp_path: Path
) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(main, "RESULTS_PATH", results_path)

    with TestClient(main.app) as client:
        response = client.get("/api/results")
        health = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {}
    assert health.json()["status"] == "ok"
    assert health.json()["results"]["status"] == "ready"
    assert health.json()["has_results"] is False


def test_reload_exposes_results_load_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FACTORLAB_RUN_TOKEN", "server-secret")
    monkeypatch.setattr(main, "RESULTS_PATH", tmp_path / "missing.json")

    with TestClient(main.app) as client:
        response = client.post(
            "/api/reload",
            headers={"X-FactorLab-Run-Token": "server-secret"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["results"]["code"] == "results_missing"
    assert response.json()["has_results"] is False

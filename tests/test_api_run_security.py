from __future__ import annotations

from fastapi.testclient import TestClient

from factorlab.api import main


def test_remote_run_is_disabled_without_a_server_token(monkeypatch) -> None:
    monkeypatch.delenv("FACTORLAB_RUN_TOKEN", raising=False)
    main._run_state["running"] = False

    with TestClient(main.app) as client:
        response = client.post("/api/run", json={"models": "eq_weight"})

    assert response.status_code == 503

    with TestClient(main.app) as client:
        state_response = client.get("/api/run/state")
    assert state_response.status_code == 503


def test_remote_run_rejects_an_invalid_token(monkeypatch) -> None:
    monkeypatch.setenv("FACTORLAB_RUN_TOKEN", "server-secret")
    main._run_state["running"] = False

    with TestClient(main.app) as client:
        response = client.post(
            "/api/run",
            headers={"X-FactorLab-Run-Token": "wrong"},
            json={"models": "eq_weight"},
        )

    assert response.status_code == 401


def test_remote_run_accepts_validated_json_with_the_server_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(
        models: str,
        top_k: int,
        rebal_freq: int,
        cost_bps: float,
        data_source: str | None,
        hpo: int,
    ) -> None:
        captured.update(
            models=models,
            top_k=top_k,
            rebal_freq=rebal_freq,
            cost_bps=cost_bps,
            data_source=data_source,
            hpo=hpo,
        )
        main._run_state["running"] = False

    monkeypatch.setenv("FACTORLAB_RUN_TOKEN", "server-secret")
    monkeypatch.setattr(main, "_do_run", fake_run)
    main._run_state["running"] = False

    with TestClient(main.app) as client:
        response = client.post(
            "/api/run",
            headers={"X-FactorLab-Run-Token": "server-secret"},
            json={
                "models": "eq_weight",
                "top_k": 7,
                "rebal_freq": 5,
                "cost_bps": 12.5,
                "data_source": "synthetic",
                "hpo": 0,
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert captured == {
        "models": "eq_weight",
        "top_k": 7,
        "rebal_freq": 5,
        "cost_bps": 12.5,
        "data_source": "synthetic",
        "hpo": 0,
    }


def test_remote_run_rejects_unknown_models_before_starting(monkeypatch) -> None:
    monkeypatch.setenv("FACTORLAB_RUN_TOKEN", "server-secret")
    main._run_state["running"] = False

    with TestClient(main.app) as client:
        response = client.post(
            "/api/run",
            headers={"X-FactorLab-Run-Token": "server-secret"},
            json={"models": "eq_weight,not_a_model"},
        )

    assert response.status_code == 422
    assert main._run_state["running"] is False


def test_spa_fallback_cannot_read_files_outside_frontend() -> None:
    with TestClient(main.app) as client:
        response = client.get("/%2e%2e/%2e%2e/pyproject.toml")

    assert response.status_code == 404
    assert "factorlab" not in response.text.lower()


def test_unknown_api_route_is_not_rewritten_to_the_spa() -> None:
    with TestClient(main.app) as client:
        response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")

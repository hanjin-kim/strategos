"""Tests for /api/batches endpoints."""
from __future__ import annotations
import json
import time
import pytest
from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---- helpers ----

def _valid_body(max_turns: int = 3, num_runs: int = 2) -> dict:
    return {
        "scenario_name": "korean_peninsula",
        "parameter_sets": [
            {"name": f"run_{i}", "rng_seed": 42 + i, "max_turns": max_turns, "use_llm": False}
            for i in range(num_runs)
        ],
    }


def _wait_for_completion(client, batch_id: str, timeout: float = 60.0) -> dict:
    """Poll status until batch is no longer RUNNING."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/batches/{batch_id}/status")
        data = resp.get_json()
        if data.get("status") != "RUNNING":
            return data
        time.sleep(0.2)
    return client.get(f"/api/batches/{batch_id}/status").get_json()


# ---- tests ----

def test_create_batch_valid(client):
    """POST /api/batches with valid scenario returns 201 and batch_id."""
    resp = client.post("/api/batches", json=_valid_body())
    assert resp.status_code == 201
    data = resp.get_json()
    assert "batch_id" in data
    assert data["status"] == "RUNNING"
    assert data["total_runs"] == 2


def test_create_batch_missing_scenario_name(client):
    """POST /api/batches without scenario_name returns 400."""
    resp = client.post("/api/batches", json={"parameter_sets": []})
    assert resp.status_code == 400
    assert "scenario_name" in resp.get_json()["error"]


def test_create_batch_invalid_scenario(client):
    """POST /api/batches with non-existent scenario returns 404."""
    resp = client.post("/api/batches", json={
        "scenario_name": "nonexistent_scenario_xyz",
        "parameter_sets": [{"name": "run_0", "rng_seed": 1, "max_turns": 3}],
    })
    assert resp.status_code == 404
    assert "not found" in resp.get_json()["error"].lower()


def test_create_batch_no_body(client):
    """POST /api/batches with no JSON body returns 400."""
    resp = client.post("/api/batches", content_type="application/json", data="{}")
    assert resp.status_code == 400


def test_get_batch_status_running(client):
    """GET /api/batches/:id/status for a running batch returns status."""
    resp = client.post("/api/batches", json=_valid_body(max_turns=3))
    batch_id = resp.get_json()["batch_id"]
    status_resp = client.get(f"/api/batches/{batch_id}/status")
    assert status_resp.status_code == 200
    data = status_resp.get_json()
    assert data["batch_id"] == batch_id
    assert "status" in data
    assert "total_runs" in data
    assert "completed_runs" in data


def test_get_batch_status_not_found(client):
    """GET /api/batches/:id/status for non-existent batch returns 404."""
    resp = client.get("/api/batches/doesnotexist99/status")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_list_batches(client):
    """GET /api/batches returns a list."""
    resp = client.get("/api/batches")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)


def test_list_batches_includes_running(client):
    """GET /api/batches includes in-memory running batches."""
    create_resp = client.post("/api/batches", json=_valid_body(max_turns=3))
    batch_id = create_resp.get_json()["batch_id"]
    list_resp = client.get("/api/batches")
    batch_ids = [b["batch_id"] for b in list_resp.get_json()]
    assert batch_id in batch_ids


def test_get_batch_runs_after_completion(client):
    """GET /api/batches/:id/runs returns run records after batch completes."""
    resp = client.post("/api/batches", json=_valid_body(max_turns=3, num_runs=2))
    batch_id = resp.get_json()["batch_id"]
    _wait_for_completion(client, batch_id)
    runs_resp = client.get(f"/api/batches/{batch_id}/runs")
    assert runs_resp.status_code == 200
    runs = runs_resp.get_json()
    assert isinstance(runs, list)
    assert len(runs) == 2


def test_get_batch_report_after_completion(client):
    """GET /api/batches/:id/report returns report after batch completes."""
    resp = client.post("/api/batches", json=_valid_body(max_turns=3, num_runs=2))
    batch_id = resp.get_json()["batch_id"]
    _wait_for_completion(client, batch_id)
    report_resp = client.get(f"/api/batches/{batch_id}/report")
    assert report_resp.status_code == 200
    data = report_resp.get_json()
    assert "report" in data
    assert "executive_summary" in data["report"]


def test_get_batch_report_not_found(client):
    """GET /api/batches/:id/report for non-existent batch returns 404."""
    resp = client.get("/api/batches/nosuchbatch999/report")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_stop_batch(client):
    """POST /api/batches/:id/stop marks batch as STOPPED."""
    resp = client.post("/api/batches", json=_valid_body(max_turns=3))
    batch_id = resp.get_json()["batch_id"]
    stop_resp = client.post(f"/api/batches/{batch_id}/stop")
    assert stop_resp.status_code == 200
    assert stop_resp.get_json()["status"] == "STOPPED"


def test_stop_nonexistent_batch(client):
    """POST /api/batches/:id/stop for non-existent batch returns 404."""
    resp = client.post("/api/batches/nosuchbatch000/stop")
    assert resp.status_code == 404


def test_batch_report_markdown(client):
    """GET /api/batches/:id/report/markdown returns text/markdown after completion."""
    resp = client.post("/api/batches", json=_valid_body(max_turns=3, num_runs=2))
    batch_id = resp.get_json()["batch_id"]
    _wait_for_completion(client, batch_id)
    md_resp = client.get(f"/api/batches/{batch_id}/report/markdown")
    assert md_resp.status_code == 200
    assert "text/markdown" in md_resp.content_type
    assert "# Simulation Analysis Report" in md_resp.data.decode()

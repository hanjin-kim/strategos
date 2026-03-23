from __future__ import annotations

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sim_id(client):
    resp = client.post("/api/simulations/", json={"scenario_name": "korean_peninsula"})
    return resp.get_json()["simulation_id"]


# --- GET /state?side= ---

def test_get_state_no_side_returns_full_state(client, sim_id):
    """Without ?side= returns full state (backward compat)."""
    resp = client.get(f"/api/simulations/{sim_id}/state")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "units" in data
    assert "turn" in data
    assert "view_side" not in data


def test_get_state_with_side_blue_returns_filtered(client, sim_id):
    """GET /state?side=BLUE returns filtered state with view_side."""
    resp = client.get(f"/api/simulations/{sim_id}/state?side=BLUE")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["view_side"] == "BLUE"
    assert "filtered_enemy" in data
    assert isinstance(data["filtered_enemy"], list)


def test_get_state_with_side_red_returns_filtered(client, sim_id):
    """GET /state?side=RED returns filtered state."""
    resp = client.get(f"/api/simulations/{sim_id}/state?side=RED")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["view_side"] == "RED"
    assert "filtered_enemy" in data


def test_get_state_invalid_side_returns_400(client, sim_id):
    """Invalid side value returns 400."""
    resp = client.get(f"/api/simulations/{sim_id}/state?side=INVALID")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# --- GET /narrative ---

def test_get_narrative_missing_sim_returns_404(client):
    resp = client.get("/api/simulations/nonexistent/narrative?turn=1")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_get_narrative_missing_turn_returns_empty(client, sim_id):
    """No turn param → empty narrative."""
    resp = client.get(f"/api/simulations/{sim_id}/narrative")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["summary"] == ""
    assert data["combat_reports"] == []
    assert data["key_events"] == []


def test_get_narrative_nonexistent_turn_returns_empty(client, sim_id):
    """Turn that doesn't exist → empty narrative."""
    resp = client.get(f"/api/simulations/{sim_id}/narrative?turn=999")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["summary"] == ""
    assert data["combat_reports"] == []
    assert data["key_events"] == []

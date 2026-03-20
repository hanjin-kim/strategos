from __future__ import annotations

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


# --- Scenario endpoints ---

def test_list_scenarios_returns_200(client):
    response = client.get("/api/scenarios/")
    assert response.status_code == 200


def test_list_scenarios_contains_korean_peninsula(client):
    response = client.get("/api/scenarios/")
    data = response.get_json()
    assert isinstance(data, list)
    names = [s["name"] for s in data]
    assert "korean_peninsula" in names


def test_get_scenario_korean_peninsula(client):
    response = client.get("/api/scenarios/korean_peninsula")
    assert response.status_code == 200
    data = response.get_json()
    assert "forces" in data
    assert "map" in data


def test_get_scenario_nonexistent_returns_404(client):
    response = client.get("/api/scenarios/nonexistent")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_validate_scenario_korean_peninsula(client):
    response = client.post("/api/scenarios/korean_peninsula/validate")
    assert response.status_code == 200
    data = response.get_json()
    assert data["valid"] is True
    assert data["units"] > 0
    assert data["terrain_hexes"] > 0
    assert data["commanders"] > 0


def test_validate_scenario_nonexistent_returns_404(client):
    response = client.post("/api/scenarios/nonexistent/validate")
    assert response.status_code == 404


# --- Simulation endpoints ---

def test_create_simulation_returns_201(client):
    response = client.post(
        "/api/simulations/",
        json={"scenario_name": "korean_peninsula"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert "simulation_id" in data
    assert data["status"] == "created"


def test_create_simulation_default_scenario(client):
    """POST with no body uses default scenario."""
    response = client.post("/api/simulations/", json={})
    assert response.status_code == 201
    data = response.get_json()
    assert "simulation_id" in data


def test_create_simulation_nonexistent_scenario_returns_404(client):
    response = client.post(
        "/api/simulations/",
        json={"scenario_name": "nonexistent_scenario"},
    )
    assert response.status_code == 404


def test_get_status_after_create(client):
    create_resp = client.post(
        "/api/simulations/",
        json={"scenario_name": "korean_peninsula"},
    )
    sim_id = create_resp.get_json()["simulation_id"]

    response = client.get(f"/api/simulations/{sim_id}/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["simulation_id"] == sim_id
    assert data["status"] == "created"
    assert data["current_turn"] == 0


def test_get_status_nonexistent_returns_404(client):
    response = client.get("/api/simulations/nonexistent/status")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data


def test_get_state_after_create(client):
    create_resp = client.post(
        "/api/simulations/",
        json={"scenario_name": "korean_peninsula"},
    )
    sim_id = create_resp.get_json()["simulation_id"]

    response = client.get(f"/api/simulations/{sim_id}/state")
    assert response.status_code == 200
    data = response.get_json()
    assert "units" in data
    assert "turn" in data


def test_get_state_nonexistent_returns_404(client):
    response = client.get("/api/simulations/nonexistent/state")
    assert response.status_code == 404


def test_get_log_after_create(client):
    create_resp = client.post(
        "/api/simulations/",
        json={"scenario_name": "korean_peninsula"},
    )
    sim_id = create_resp.get_json()["simulation_id"]

    response = client.get(f"/api/simulations/{sim_id}/log")
    assert response.status_code == 200
    data = response.get_json()
    assert "turns" in data
    assert data["turns"] == []


def test_stop_simulation(client):
    create_resp = client.post(
        "/api/simulations/",
        json={"scenario_name": "korean_peninsula"},
    )
    sim_id = create_resp.get_json()["simulation_id"]

    response = client.post(f"/api/simulations/{sim_id}/stop")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "stopped"


def test_stop_nonexistent_returns_404(client):
    response = client.post("/api/simulations/nonexistent/stop")
    assert response.status_code == 404


# --- Health ---

def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"status": "ok"}

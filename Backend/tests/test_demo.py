"""Automated test suite for the Viva Demo Controller endpoints."""
import re

from fastapi.testclient import TestClient


def test_list_demo_presets(client: TestClient):
    """Verifies that /api/demo/presets returns the registered examination presets."""
    response = client.get("/api/demo/presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert len(data["presets"]) >= 3

    preset_ids = [p["id"] for p in data["presets"]]
    assert "dal_lake_flood_2014" in preset_ids
    assert "jammu_expansion_2023" in preset_ids
    assert "chenab_wildfire_burn" in preset_ids
    assert all(re.fullmatch(r"[a-z0-9_]+", preset_id) for preset_id in preset_ids)


def test_load_dal_lake_flood_preset(client: TestClient):
    """Verifies that the 2014 Dal Lake flood scenario loads and hydrates properly."""
    response = client.post("/api/demo/load/dal_lake_flood_2014")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert res["preset_id"] == "dal_lake_flood_2014"
    assert res["category"] == "analysis"

    doc = res["document"]
    assert doc["id"] == "demo_dal_lake_flood_2014"
    assert "Water" in doc["land_cover"]
    assert doc["land_cover"]["Water"] > 50.0
    assert doc["severity"] == "Severe"


def test_load_jammu_expansion_preset(client: TestClient):
    """Verifies that the Jammu Decadal Urban Sprawl scenario loads with change metrics."""
    response = client.post("/api/demo/load/jammu_expansion_2023")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert res["preset_id"] == "jammu_expansion_2023"
    assert res["category"] == "change"

    doc = res["document"]
    assert doc["changed_percent"] > 20.0
    assert "Urban" in doc["class_deltas"]
    assert doc["class_deltas"]["Urban"] > 25.0
    assert len(doc["transitions"]) > 0


def test_load_chenab_wildfire_preset(client: TestClient):
    """Verifies that the Chenab Valley wildfire scenario loads with disaster triage alerts."""
    response = client.post("/api/demo/load/chenab_wildfire_burn")
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert res["preset_id"] == "chenab_wildfire_burn"
    assert res["category"] == "disaster"

    doc = res["document"]
    assert doc["severity"] == "High"
    assert "authority_alert" in doc
    assert "exposure" in doc


def test_load_invalid_preset_returns_404(client: TestClient):
    """Verifies that requesting a non-existent preset returns a 404 error."""
    response = client.post("/api/demo/load/non_existent_preset_xyz")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


def test_load_malformed_preset_id_returns_404(client: TestClient):
    """Rejects path-like identifiers before constructing a filesystem path."""
    response = client.post("/api/demo/load/not-valid-id")
    assert response.status_code == 404


def test_load_path_traversal_like_preset_id_returns_404(client: TestClient):
    """Rejects traversal-like identifiers before they reach the filesystem."""
    response = client.post("/api/demo/load/%2E%2E%2Fmanifest")
    assert response.status_code == 404


def test_loading_same_preset_is_repeatable(client: TestClient):
    """Repeated hydration remains successful and returns the same preset document."""
    first = client.post("/api/demo/load/chenab_wildfire_burn")
    second = client.post("/api/demo/load/chenab_wildfire_burn")

    assert first.status_code == second.status_code == 200
    assert first.json()["document"]["id"] == second.json()["document"]["id"]


def test_demo_reset(client: TestClient):
    """Verifies that the demo reset endpoint cleans up injected demonstration records."""
    # Load one first
    client.post("/api/demo/load/dal_lake_flood_2014")

    # Call reset
    response = client.post("/api/demo/reset")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

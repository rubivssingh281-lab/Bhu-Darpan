"""Health check endpoint verification."""


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    data = response.json()
    assert data.get("status") == "ok"
    assert data["service"] == "bhu-darpan-backend"
    assert "version" in data
    assert data["database"]["backend"] == "sqlite"
    assert data["classes"] == ["Forest", "Water", "Agriculture", "Urban", "Others"]

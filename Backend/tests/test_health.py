"""Health check endpoint verification."""


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert "version" in data
    assert data["database"]["backend"] == "sqlite"
    assert data["classes"] == ["Forest", "Water", "Agriculture", "Urban", "Others"]

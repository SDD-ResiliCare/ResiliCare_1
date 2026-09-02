from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_and_openapi_expose_versioned_production_routes():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    paths = app.openapi()["paths"]
    assert "/api/v1/encounters/{encounter_id}/vitals" in paths
    assert "/api/v1/encounters/{encounter_id}/symptom-interviews" in paths
    assert "/api/v1/encounters/{encounter_id}/prescriptions" in paths
    assert "/api/v1/feedback/reviews" in paths
    assert all("{token}" not in path for path in paths)
    assert not any("/surge/run" in path or "/surge/reset" in path for path in paths)


def test_clinical_routes_require_authentication():
    response = client.get("/api/v1/patients/00000000-0000-0000-0000-000000000000")
    assert response.status_code in {401, 403}

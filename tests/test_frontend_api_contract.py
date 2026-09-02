from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from src.main import app
from src.schemas.encounter import QueuePriorityUpdate


def test_frontend_discovery_and_workspace_routes_are_exposed():
    paths = app.openapi()["paths"]
    required = {
        "/api/v1/app-context",
        "/api/v1/hospitals/current",
        "/api/v1/hospitals/{hospital_id}/wards",
        "/api/v1/staff",
        "/api/v1/staff/doctors/workloads",
        "/api/v1/staff/doctors/{doctor_id}/workload",
        "/api/v1/patients",
        "/api/v1/encounters",
        "/api/v1/encounters/{encounter_id}/workspace",
        "/api/v1/encounters/{encounter_id}/allocation",
        "/api/v1/queues/current",
        "/api/v1/queues/current/entries",
        "/api/v1/questionnaires",
        "/api/v1/encounters/{encounter_id}/assessments",
        "/api/v1/encounters/{encounter_id}/prescriptions",
        "/api/v1/encounters/{encounter_id}/invoices",
        "/api/v1/audit-events",
        "/api/v1/kiosk/status",
        "/api/v1/kiosk/process-text",
        "/api/v1/kiosk/process-audio",
        "/api/v1/kiosk/submit-followups",
        "/api/v1/kiosk/trauma-intake",
        "/api/v1/kiosk/reconcile-identity",
    }
    assert required <= paths.keys()



def test_master_resources_expose_safe_crud_methods():
    paths = app.openapi()["paths"]
    assert {"get", "post"} <= paths["/api/v1/hospitals"].keys()
    assert {"get", "patch", "delete"} <= paths["/api/v1/hospitals/{hospital_id}"].keys()
    assert {"get", "post"} <= paths["/api/v1/staff"].keys()
    assert {"get", "patch", "delete"} <= paths["/api/v1/staff/{staff_id}"].keys()
    assert {"get", "post"} <= paths["/api/v1/patients"].keys()
    assert {"get", "patch", "delete"} <= paths["/api/v1/patients/{patient_id}"].keys()


def test_queue_actions_are_explicit_and_audit_is_read_only():
    paths = app.openapi()["paths"]
    for action in ("call", "start-care", "exit", "cancel"):
        assert "post" in paths[f"/api/v1/queues/entries/{{entry_id}}/{action}"]
    assert set(paths["/api/v1/audit-events/{event_id}"]) == {"get"}


def test_positive_queue_boost_requires_reason_and_expiry():
    with pytest.raises(ValidationError):
        QueuePriorityUpdate(priority_boost=2)
    payload = QueuePriorityUpdate(
        priority_boost=2,
        reason="Reassessment overdue",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    assert payload.priority_boost == 2

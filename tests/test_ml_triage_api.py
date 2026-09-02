"""Tests for ML Triage Inference, Explainability, and Supabase Triage API Endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import RequestContext, get_request_context
from src.main import app
from src.ml import ESITriagePipeline
from src.services.triage_service import TriageService


def test_src_ml_pipeline_direct_inference():
    pipeline = ESITriagePipeline()
    assert len(pipeline.feature_names) == 187

    # Test high-acuity case
    case_shock = {
        "encounter_id": "TEST-SHOCK-01",
        "age": 68.0,
        "sex": "Female",
        "arrival_mode": "Ambulance",
        "chief_complaint": "Severe retrosternal chest pain with profuse sweating",
        "presenting_details": "Pale, cool, clammy, hypotensive and tachycardic.",
        "heart_rate_bpm": 135.0,
        "respiratory_rate_bpm": 28.0,
        "spo2_percent": 88.0,
        "systolic_bp_mmhg": 75.0,
        "diastolic_bp_mmhg": 45.0,
        "temperature_c": 36.2,
        "avpu": "V",
        "gcs_total": 12,
        "pain_score": 9,
    }

    res = pipeline.predict_encounter(case_shock, safety_ceiling=2)
    assert res["proposed_esi"] in (1, 2)
    assert res["final_esi"] <= 2
    assert "class_probabilities" in res
    assert len(res["class_probabilities"]) == 5
    assert len(res["top_contributing_factors"]) > 0
    assert "Shock Index" in [f["feature"] for f in res["top_contributing_factors"]] or "SpO₂ Saturation" in [
        f["feature"] for f in res["top_contributing_factors"]
    ]
    assert len(res["clinical_rationale"]) > 0


def test_safety_ceiling_clamping_invariant():
    pipeline = ESITriagePipeline()

    # Mild case with benign vitals
    case_mild = {
        "encounter_id": "TEST-MILD-01",
        "age": 28.0,
        "sex": "Male",
        "arrival_mode": "Walk-in",
        "chief_complaint": "Medication refill for hypertension",
        "presenting_details": "Asymptomatic, needs 30-day supply of amlodipine.",
        "heart_rate_bpm": 72.0,
        "respiratory_rate_bpm": 14.0,
        "spo2_percent": 99.0,
        "systolic_bp_mmhg": 122.0,
        "diastolic_bp_mmhg": 78.0,
        "temperature_c": 36.6,
        "avpu": "A",
        "gcs_total": 15,
        "pain_score": 0,
    }

    # If safety ceiling is forced to 2 by a clinician or rule, final_esi must clamp to 2
    res = pipeline.predict_encounter(case_mild, safety_ceiling=2)
    assert res["proposed_esi"] in (4, 5)
    assert res["final_esi"] == 2
    assert res["safety_override_applied"] is True
    assert "Safety guardrail activated" in res["clinical_rationale"]


def test_triage_predict_simulation_api_endpoint():
    client = TestClient(app)

    # Auth mock dependency
    mock_context = RequestContext(
        auth_user_id=uuid4(),
        platform_role="doctor",
        staff_id=uuid4(),
        hospital_id=uuid4(),
        staff_type="doctor",
        patient_ids=(),
    )
    app.dependency_overrides[get_request_context] = lambda: mock_context

    try:
        payload = {
            "encounter_id": "SIM-999",
            "age": 62.0,
            "sex": "Male",
            "arrival_mode": "Ambulance",
            "chief_complaint": "Crushing chest pain radiating to left arm",
            "presenting_details": "Onset 30 mins ago with diaphoresis and nausea.",
            "heart_rate_bpm": 118.0,
            "respiratory_rate_bpm": 24.0,
            "spo2_percent": 94.0,
            "systolic_bp_mmhg": 105.0,
            "diastolic_bp_mmhg": 68.0,
            "temperature_c": 37.1,
            "avpu": "A",
            "gcs_total": 15,
            "pain_score": 9,
        }

        response = client.post("/api/v1/triage/predict", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["encounter_id"] == "SIM-999"
        assert data["proposed_esi"] in (1, 2)
        assert data["final_esi"] in (1, 2)
        assert data["confidence_score"] > 0.0
        assert len(data["prediction_set"]) >= 1
        assert "ESI_1" in data["class_probabilities"]
        assert len(data["top_contributing_factors"]) > 0
        assert len(data["clinical_rationale"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_receptionist_can_access_ml_prediction_endpoints():
    client = TestClient(app)

    mock_receptionist_context = RequestContext(
        auth_user_id=uuid4(),
        platform_role="receptionist",
        staff_id=uuid4(),
        hospital_id=uuid4(),
        staff_type="receptionist",
        patient_ids=(),
    )
    app.dependency_overrides[get_request_context] = lambda: mock_receptionist_context

    try:
        payload = {
            "encounter_id": "SIM-RECEPTIONIST-01",
            "age": 42.0,
            "sex": "Female",
            "arrival_mode": "Walk-in",
            "chief_complaint": "Mild headache and sore throat",
            "heart_rate_bpm": 76.0,
            "respiratory_rate_bpm": 16.0,
            "spo2_percent": 99.0,
            "systolic_bp_mmhg": 120.0,
            "diastolic_bp_mmhg": 80.0,
            "temperature_c": 37.0,
        }
        response = client.post("/api/v1/triage/predict", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["proposed_esi"] in (4, 5)
    finally:
        app.dependency_overrides.clear()



@pytest.mark.asyncio
async def test_triage_service_predict_ml_persisted_flow():
    mock_session = AsyncMock()

    # Mock DB objects
    mock_patient = MagicMock()
    mock_patient.id = uuid4()
    mock_patient.date_of_birth = None
    mock_patient.estimated_age_years = 50.0
    mock_patient.sex_at_birth = "female"

    mock_encounter = MagicMock()
    mock_encounter.id = uuid4()
    mock_encounter.encounter_code = "ENC-TEST-100"
    mock_encounter.arrival_mode = "Ambulance"
    mock_encounter.chief_complaint = "Severe abdominal pain and vomiting blood"
    mock_encounter.presenting_details = "Hematemesis x2, dizzy on standing"
    mock_encounter.hospital_id = uuid4()

    mock_vital = MagicMock()
    mock_vital.id = uuid4()
    mock_vital.heart_rate_bpm = 125.0
    mock_vital.respiratory_rate_bpm = 26.0
    mock_vital.spo2_percent = 95.0
    mock_vital.systolic_bp_mmhg = 88.0
    mock_vital.diastolic_bp_mmhg = 55.0
    mock_vital.temperature_c = 37.0
    mock_vital.avpu = "A"
    mock_vital.gcs_total = 15
    mock_vital.pain_score = 8

    # Setup execute return
    mock_result = MagicMock()
    mock_result.first.return_value = (mock_patient, mock_encounter, mock_vital)
    mock_session.execute.return_value = mock_result

    service = TriageService(mock_session)
    pred_res = await service.predict_ml(mock_encounter.id, mock_encounter.hospital_id)

    assert pred_res.encounter_id == str(mock_encounter.id)
    assert pred_res.proposed_esi in (1, 2, 3)
    assert pred_res.final_esi <= 3
    assert len(pred_res.top_contributing_factors) > 0
    assert len(pred_res.clinical_rationale) > 0


def test_supabase_sql_query_structure():
    """Verify that the SQL query compiles to exact PostgreSQL JOIN across encounters, patients, and vitals."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy import select
    from src.db.models.encounter import Encounter
    from src.db.models.patient import Patient
    from src.db.models.triage import VitalObservation

    test_encounter_id = uuid4()
    test_hospital_id = uuid4()

    latest_vital_subquery = (
        select(VitalObservation.id)
        .where(VitalObservation.encounter_id == test_encounter_id)
        .order_by(VitalObservation.observed_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        select(Patient, Encounter, VitalObservation)
        .join_from(Patient, Encounter, Encounter.patient_id == Patient.id)
        .outerjoin(VitalObservation, VitalObservation.id == latest_vital_subquery)
        .where(Encounter.id == test_encounter_id, Encounter.hospital_id == test_hospital_id)
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "FROM patients JOIN encounters ON encounters.patient_id = patients.id" in compiled
    assert "LEFT OUTER JOIN vital_observations ON vital_observations.id =" in compiled
    assert "encounters.id =" in compiled
    assert "encounters.hospital_id =" in compiled


@pytest.mark.asyncio
async def test_create_assessment_populates_supabase_ml_output():
    """Verify that create_assessment persists class probabilities, TreeSHAP attributions, and rationale in ml_output."""
    from src.schemas.triage import AssessmentCreate

    mock_session = AsyncMock()

    mock_patient = MagicMock()
    mock_patient.id = uuid4()
    mock_patient.date_of_birth = None
    mock_patient.estimated_age_years = 55.0
    mock_patient.sex_at_birth = "male"

    mock_encounter = MagicMock()
    mock_encounter.id = uuid4()
    mock_encounter.encounter_code = "ENC-ML-PERSIST"
    mock_encounter.arrival_mode = "Ambulance"
    mock_encounter.chief_complaint = "Crushing chest pain radiating to left jaw"
    mock_encounter.presenting_details = "Diaphoretic, pale, acute onset 20 min ago"
    mock_encounter.hospital_id = uuid4()

    mock_vital = MagicMock()
    mock_vital.id = uuid4()
    mock_vital.encounter_id = mock_encounter.id
    mock_vital.heart_rate_bpm = 115.0
    mock_vital.respiratory_rate_bpm = 24.0
    mock_vital.spo2_percent = 93.0
    mock_vital.systolic_bp_mmhg = 100.0
    mock_vital.diastolic_bp_mmhg = 65.0
    mock_vital.temperature_c = 36.8
    mock_vital.avpu = "A"
    mock_vital.gcs_total = 15
    mock_vital.pain_score = 9

    mock_config = MagicMock()
    mock_config.id = uuid4()
    mock_config.hospital_id = mock_encounter.hospital_id

    # Mock execute results
    query_count = 0
    def execute_side_effect(stmt, *args, **kwargs):
        nonlocal query_count
        res = MagicMock()
        if query_count == 0:
            res.first.return_value = (mock_patient, mock_encounter, mock_vital)
        else:
            res.first.return_value = None
        query_count += 1
        return res

    mock_session.execute = AsyncMock(side_effect=execute_side_effect)
    mock_session.scalar = AsyncMock(return_value=mock_config)


    service = TriageService(mock_session)
    service.assessments = MagicMock()
    
    saved_assessment = None
    async def capture_add(assessment):
        nonlocal saved_assessment
        saved_assessment = assessment
        return assessment

    service.assessments.add = AsyncMock(side_effect=capture_add)

    payload = AssessmentCreate(
        operational_config_id=mock_config.id,
        latest_vital_observation_id=mock_vital.id,
        proposed_esi=2,
        score_source="ml_lgbm_v1",
        engine_version="1.0.0",
    )

    assessment = await service.create_assessment(
        encounter_id=mock_encounter.id,
        payload=payload,
        created_by=uuid4(),
        hospital_id=mock_encounter.hospital_id,
    )

    assert assessment is not None
    assert assessment.ml_output is not None
    assert "class_probabilities" in assessment.ml_output
    assert "treeshap_attributions" in assessment.ml_output
    assert "clinical_rationale" in assessment.ml_output
    assert assessment.ml_output["proposed_esi"] in (1, 2)


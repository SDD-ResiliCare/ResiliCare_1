from uuid import uuid4

from src.services.clinical_overview_service import build_allocation_overview, build_triage_overview


def test_triage_overview_explains_esi_ward_and_required_human_confirmation():
    ward_id = uuid4()
    overview, factors = build_triage_overview(
        {
            "point_estimate": 2,
            "esi_set": [1, 2],
            "confidence_label": "Moderate",
            "defer_to_senior_nurse": True,
            "explanation_text": "ESI 1-2 — the presentation is marked high-risk.",
            "explanation_lines": ["ESI 1-2 — the presentation is marked high-risk."],
            "explanation_rule_ids": ["HIGH_RISK.TIME_SENSITIVE_PRESENTATION"],
            "matched_safety_rules": ["HIGH_RISK.TIME_SENSITIVE_PRESENTATION"],
            "uncertainty_reasons": ["ZERO_HISTORY"],
        },
        ward_id=ward_id,
        ward_name="Acute Care",
    )

    assert "Acute Care" in overview
    assert "Senior nurse review is required" in overview
    assert factors["recommended_ward_id"] == str(ward_id)
    assert factors["explanation_rule_ids"] == ["HIGH_RISK.TIME_SENSITIVE_PRESENTATION"]


def test_allocation_overview_separates_configured_ward_reason_from_doctor_workload():
    ward_id, doctor_id = uuid4(), uuid4()
    overview, factors = build_allocation_overview(
        final_esi=3,
        ward_id=ward_id,
        ward_name="Observation",
        suggested_ward_id=ward_id,
        suggested_ward_name="Observation",
        doctor_id=doctor_id,
        doctor_name="Dr Synthetic",
        doctor_was_busy=True,
        doctor_queue_position=2,
        allocator_reason="Confirmed after review",
    )

    assert "matches the hospital routing rule" in overview
    assert "position 2" in overview
    assert factors["doctor_staff_id"] == str(doctor_id)
    assert factors["doctor_was_busy"] is True

"""Tests for Pillar 1 Kiosk Service, Spoken Conjunction Negation, Follow-ups, and Trauma Merging."""

import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app
from src.nlp.text_pipeline import detect_acuity_with_negation
from src.schemas.kiosk import (
    FollowUpAnswer,
    KioskFollowUpSubmitRequest,
    KioskTextIntakeRequest,
)
from src.services.kiosk_service import KioskService


class SpokenConjunctionNegationTests(unittest.TestCase):
    def test_spoken_english_conjunction_breaks_negation(self):
        # "no chest pain but breathing is impossible" -> 'cannot_breathe' should trigger
        flags = detect_acuity_with_negation("no chest pain but cannot breathe")
        self.assertIn("cannot_breathe", flags)

    def test_spoken_hindi_conjunction_lekin_breaks_negation(self):
        # "dard nahi tha lekin saans nahi aa rahi" -> 'cannot_breathe' should trigger
        flags = detect_acuity_with_negation("dard nahi tha lekin saans nahi aa rahi")
        self.assertIn("cannot_breathe", flags)

    def test_spoken_hindi_conjunction_magar_breaks_negation(self):
        flags = detect_acuity_with_negation("khoon nahi beh raha magar behosh ho gaya")
        self.assertIn("unconscious", flags)

    def test_negation_without_conjunction_suppresses_flag(self):
        flags = detect_acuity_with_negation("patient is not unconscious today")
        self.assertEqual(flags, [])


class KioskFollowUpQuestionTests(unittest.TestCase):
    def setUp(self):
        # KioskService without a live DB session can still evaluate pure question logic
        self.service = KioskService(session=None)  # type: ignore

    def test_chest_pain_resolves_acs_questions(self):
        questions = self.service.get_follow_up_questions("chest pain")
        codes = [q.question_code for q in questions]
        self.assertIn("chest_radiation", codes)
        self.assertIn("chest_dyspnea_sweat", codes)

    def test_abdominal_pain_resolves_gi_bleed_questions(self):
        questions = self.service.get_follow_up_questions("lower abdominal pain")
        codes = [q.question_code for q in questions]
        self.assertIn("abdo_gi_bleed", codes)
        self.assertIn("abdo_fever_guarding", codes)

    def test_pelvic_pain_resolves_ectopic_risk(self):
        questions = self.service.get_follow_up_questions("pelvic pain")
        codes = [q.question_code for q in questions]
        self.assertIn("pelvic_pregnancy_risk", codes)

    def test_followup_yes_to_gi_bleed_escalates_to_esi_2(self):
        payload = KioskFollowUpSubmitRequest(
            extracted_complaint="lower abdominal pain",
            answers=[
                FollowUpAnswer(question_code="abdo_gi_bleed", answer_yes=True),
                FollowUpAnswer(question_code="abdo_fever_guarding", answer_yes=False),
            ],
        )
        result = self.service.evaluate_follow_up_answers(payload)
        self.assertTrue(result.acuity_escalated)
        self.assertEqual(result.effective_esi_ceiling, 2)
        self.assertIn("Gastrointestinal Hemorrhage", result.summary_for_nurse)
        self.assertTrue(len(result.safety_actions) > 0)

    def test_followup_no_to_all_preserves_baseline_ceiling(self):
        payload = KioskFollowUpSubmitRequest(
            extracted_complaint="lower abdominal pain",
            answers=[
                FollowUpAnswer(question_code="abdo_gi_bleed", answer_yes=False),
                FollowUpAnswer(question_code="abdo_fever_guarding", answer_yes=False),
            ],
        )
        result = self.service.evaluate_follow_up_answers(payload)
        self.assertFalse(result.acuity_escalated)
        self.assertEqual(result.effective_esi_ceiling, 3)

    def test_text_intake_with_clear_complaint_prompts_follow_ups(self):
        req = KioskTextIntakeRequest(transcript="pet mein dard ho raha hai")
        res = self.service.process_text_intake(req)
        self.assertTrue(res.confidence_gate_passed)
        self.assertEqual(res.extracted_complaint, "lower abdominal pain")
        self.assertEqual(res.layout_directive, "PROMPT_FOLLOW_UPS")
        self.assertFalse(res.fallback_to_touch)
        self.assertTrue(len(res.suggested_follow_up_questions) >= 2)


    def test_text_intake_with_critical_red_flag_triggers_lock(self):
        req = KioskTextIntakeRequest(transcript="patient cannot breathe and is unconscious")
        res = self.service.process_text_intake(req)
        self.assertTrue(res.confidence_gate_passed)
        self.assertEqual(res.layout_directive, "CRITICAL_RED_FLAG_LOCK")
        self.assertIn("cannot_breathe", res.clinical_acuity_red_flags)

    def test_text_intake_with_unrecognized_text_triggers_touch_fallback(self):
        req = KioskTextIntakeRequest(transcript="just feeling slightly weird today")
        res = self.service.process_text_intake(req)
        self.assertEqual(res.layout_directive, "SWITCH_TO_TOUCH_GRID")
        self.assertTrue(res.fallback_to_touch)


class KioskApiEndpointsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_kiosk_status_endpoint(self):
        response = self.client.get("/api/v1/kiosk/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("audio_pipeline_available", data)
        self.assertIn("supported_languages", data)

    def test_kiosk_process_text_endpoint(self):
        response = self.client.post(
            "/api/v1/kiosk/process-text",
            json={"transcript": "pet mein dard ho raha hai severe", "language_code": "hi-Latn"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["extracted_complaint"], "lower abdominal pain")
        self.assertEqual(data["layout_directive"], "PROMPT_FOLLOW_UPS")
        self.assertTrue(len(data["suggested_follow_up_questions"]) >= 2)

    def test_kiosk_submit_followups_endpoint(self):
        response = self.client.post(
            "/api/v1/kiosk/submit-followups",
            json={
                "extracted_complaint": "chest pain",
                "answers": [{"question_code": "chest_radiation", "answer_yes": True}],
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["acuity_escalated"])
        self.assertEqual(data["effective_esi_ceiling"], 2)


class TraumaIntakeAndMergeTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_trauma_intake_creates_shadow_record(self):
        from unittest.mock import AsyncMock, MagicMock

        from src.schemas.kiosk import TraumaIntakeRequest

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        service = KioskService(session=mock_session)
        req = TraumaIntakeRequest(
            hospital_id=uuid4(),
            estimated_age=40,
            gender_presentation="male",
            observed_trauma_cues=["active bleeding", "unresponsive"],
        )
        res = await service.create_trauma_intake(req)
        self.assertTrue(res.is_unidentified)
        self.assertTrue(res.alias.startswith("Trauma-Male-40-"))
        self.assertEqual(mock_session.add.call_count, 2)  # Patient + Encounter
        mock_session.commit.assert_awaited_once()

    async def test_reconcile_identity_fails_if_same_patient(self):
        from unittest.mock import AsyncMock, MagicMock

        from fastapi import HTTPException

        from src.db.models.patient import Patient
        from src.schemas.kiosk import ReconcileIdentityRequest

        p_id = uuid4()
        same_patient = Patient(first_name="Trauma-Male", status="active")
        same_patient.id = p_id

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=same_patient)

        service = KioskService(session=mock_session)
        req = ReconcileIdentityRequest(
            trauma_patient_id=p_id,
            target_master_patient_id=p_id,
            reason="Identity confirmed via family",
        )
        with self.assertRaises(HTTPException) as ctx:
            await service.reconcile_identity(req)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()


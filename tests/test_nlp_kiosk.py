"""Task 12 text-pipeline tests. Deliberately avoid torch/librosa/transformers/spaCy: these
exercise only the dependency-free stages (negation, complaint mapping, identity fallback,
confidence gate), so they run regardless of whether the optional NLP extras are installed.
"""

import unittest

from resilicare import match_ambiguous_presentations
from resilicare.nlp_kiosk import (
    detect_acuity_with_negation,
    extract_chief_complaint,
    patient_identity_binding,
    process_kiosk_text,
    resolve_kiosk_chief_complaint,
)


class NegationAndRedFlagTests(unittest.TestCase):
    def test_negation_window_suppresses_the_flag(self):
        self.assertEqual(detect_acuity_with_negation("I am not bleeding profusely, just tired"), [])

    def test_negation_window_does_not_suppress_a_separate_flag(self):
        flags = detect_acuity_with_negation("I am not bleeding profusely, but I have chest pain")
        self.assertEqual(flags, ["chest_pain"])

    def test_unnegated_flag_is_detected(self):
        self.assertEqual(detect_acuity_with_negation("patient is unconscious"), ["unconscious"])

    def test_hindi_phrase_variant_is_detected(self):
        self.assertEqual(detect_acuity_with_negation("saans nahi aa rahi hai"), ["cannot_breathe"])


class ComplaintExtractionTests(unittest.TestCase):
    def test_english_phrase_returns_canonical_trigger_phrase(self):
        self.assertEqual(extract_chief_complaint("severe chest pain since morning"), "chest pain")

    def test_hindi_phrase_returns_canonical_trigger_phrase(self):
        self.assertEqual(extract_chief_complaint("bahut chakkar aa raha hai, behosh ho gaya"), "syncope")

    def test_no_match_returns_none(self):
        self.assertIsNone(extract_chief_complaint("mild headache since yesterday"))

    def test_extracted_complaint_feeds_the_existing_differential_table_unchanged(self):
        kiosk_result = process_kiosk_text("seene mein dard ho raha hai")
        patient = {"chief_complaint": resolve_kiosk_chief_complaint(kiosk_result)}
        matches = match_ambiguous_presentations(patient)
        self.assertTrue(matches)
        self.assertEqual(matches[0]["pathway_id"], "ACUTE_CHEST_DISCOMFORT")
        self.assertEqual(matches[0]["maximum_allowed_esi"], 3)


class IdentityBindingTests(unittest.TestCase):
    def test_falls_back_to_ephemeral_alias_without_spacy(self):
        alias = patient_identity_binding("my stomach hurts")
        self.assertTrue(alias.startswith("Trauma-Unknown-"))


class ConfidenceGateTests(unittest.TestCase):
    def test_rejects_empty_transcript(self):
        result = process_kiosk_text("")
        self.assertFalse(result["confidence_gate_passed"])
        self.assertIsNone(result["extracted_complaint"])

    def test_rejects_degenerate_repetition(self):
        result = process_kiosk_text("the the the")
        self.assertFalse(result["confidence_gate_passed"])

    def test_passes_normal_transcript(self):
        result = process_kiosk_text("my chest hurts a lot")
        self.assertTrue(result["confidence_gate_passed"])
        self.assertEqual(result["extracted_complaint"], "chest pain")


class ManualFallbackEntryPointTests(unittest.TestCase):
    def test_process_kiosk_text_matches_the_audio_pipeline_shape(self):
        """A clinician typing what was said should get the same result shape as the audio
        pipeline, without any audio, VAD, or ASR involved."""
        result = process_kiosk_text("patient says I am not unconscious but pelvic pain is severe")
        self.assertEqual(result["clinical_acuity_red_flags"], [])
        self.assertEqual(result["extracted_complaint"], "pelvic pain")
        self.assertTrue(result["patient_alias"].startswith("Trauma-Unknown-"))


if __name__ == "__main__":
    unittest.main()

"""EXPERIMENTAL Task 12 spike; text pipeline."""
from __future__ import annotations

import re
import uuid
from typing import Any, Mapping, Optional

EXPERIMENTAL_NOT_DEMO_READY = True

# Each red flag is matched by *any* of its phrase variants (English + common Hindi renderings,
# romanized and Devanagari). This is a keyword list, not a language model — it is deliberately
# small and auditable, matching the checklist's "no NLP model needed for this part" scope.
RED_FLAGS: list[dict[str, Any]] = [
    {"id": "bleeding_profusely", "phrases": ["bleeding profusely", "bahut khoon beh raha", "बहुत खून बह रहा"]},
    {"id": "chest_pain", "phrases": ["chest pain", "seene mein dard", "chest mein dard", "सीने में दर्द"]},
    {"id": "unconscious", "phrases": ["unconscious", "behosh", "besudh", "बेहोश"]},
    {"id": "cannot_breathe", "phrases": ["cannot breathe", "saans nahi aa rahi", "saans lene mein takleef", "सांस नहीं आ रही"]},
    {"id": "sudden_weakness", "phrases": ["sudden weakness", "achanak kamzori", "ek taraf kamzori", "अचानक कमज़ोरी"]},
    {"id": "stroke", "phrases": ["stroke", "lakwa", "falij", "लकवा"]},
]

# Negation tokens checked within a 3-token backward window of a matched flag's first word.
NEGATION_TOKENS = ["not", "no", "never", "didn't", "don't", "doesn't", "nahi", "nahin", "na", "mat", "नहीं", "बिना"]

# Maps kiosk complaint categories directly onto the *exact* trigger phrases in
# ambiguous_presentations.json, so an extracted complaint feeds match_ambiguous_presentations()
# (and therefore score_with_confidence()) exactly as if it had been typed as chief_complaint text.
_COMPLAINT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("chest pain", ("chest", "heart", "seene", "seena", "dil mein dard", "छाती", "सीने")),
    ("syncope", ("faint", "pass out", "passed out", "dizzy", "behosh", "chakkar", "बेहोश", "चक्कर")),
    ("lower abdominal pain", ("stomach", "belly", "abdominal", "pet mein dard", "pet dard", "पेट")),
    ("pelvic pain", ("pelvic", "pelvis")),
]


def process_kiosk_text(transcript: str) -> dict[str, Any]:
    """Run the dependency-free text stages (steps 4-6) on an already-obtained transcript.

    This is the manual-fallback entry point: a clinician/attendant can type what was said (no
    microphone or ASR involved) and get the same red-flag/complaint/identity extraction that the
    audio pipeline produces from a transcript. Works with the standard library only.
    """
    text = (transcript or "").strip()
    result: dict[str, Any] = {
        "transcript": text, "confidence_gate_passed": False,
        "clinical_acuity_red_flags": [], "extracted_complaint": None, "patient_alias": None,
    }
    result["confidence_gate_passed"] = _passes_confidence_gate(text)
    if not result["confidence_gate_passed"]:
        return result
    result["clinical_acuity_red_flags"] = detect_acuity_with_negation(text)
    result["extracted_complaint"] = extract_chief_complaint(text)
    result["patient_alias"] = patient_identity_binding(text)
    return result


def resolve_kiosk_chief_complaint(kiosk_result: Mapping[str, Any]) -> Optional[str]:
    """Return the extracted complaint text, ready to drop into a patient dict's chief_complaint.

    Usage: ``patient = {**patient, "chief_complaint": resolve_kiosk_chief_complaint(kiosk_result)}``
    then run the normal `match_ambiguous_presentations` / `score_with_confidence` path unchanged.
    """
    return kiosk_result.get("extracted_complaint")


def _passes_confidence_gate(text: str) -> bool:
    """Reject empty, too-short, or degenerate (single word repeated) transcripts.

    Honest limitation: the HuggingFace ASR pipeline used below does not return per-token
    confidence/logprobs by default, so this is a text-shape heuristic, not a calibrated ASR
    confidence score. A real confidence gate would need `return_dict_in_generate` + logprob
    extraction from Whisper directly; that has not been built or validated here.
    """
    if len(text) < 2:
        return False
    words = text.lower().split()
    if len(words) >= 3 and len(set(words)) == 1:
        return False  # e.g. "the the the" - garbage/repetition artifact
    return True


def detect_acuity_with_negation(text: str) -> list[str]:
    """Match ESI red-flags but ignore any hit negated within a 3-token backward window."""
    text_lower = text.lower()
    words = re.findall(r"\b\w+\b", text_lower)
    triggered = []
    for flag in RED_FLAGS:
        phrase = next((p for p in flag["phrases"] if p in text_lower), None)
        if not phrase:
            continue
        first_word = phrase.split()[0]
        try:
            idx = words.index(first_word)
            window = words[max(0, idx - 3):idx]
            negated = any(neg in window for neg in NEGATION_TOKENS)
        except ValueError:
            negated = False  # tokenizer split the phrase unexpectedly; fail open to the flag
        if not negated:
            triggered.append(flag["id"])
    return triggered


def extract_chief_complaint(text: str) -> Optional[str]:
    """Map transcript text to a canonical differential-table trigger phrase.

    Returns the exact string an entry in ambiguous_presentations.json expects in
    chief_complaint (e.g. "chest pain"), or None if nothing matched — never a free-form category
    label, so callers can feed this straight into match_ambiguous_presentations().
    """
    text_lower = text.lower()
    for trigger_phrase, keywords in _COMPLAINT_KEYWORDS:
        if any(keyword in text_lower for keyword in keywords):
            return trigger_phrase
    return None


def patient_identity_binding(text: str) -> str:
    """Extract a name via spaCy NER if available, else fall back to an ephemeral trauma alias."""
    try:
        import spacy
    except ImportError:
        return _ephemeral_alias()
    try:
        nlp = _load_spacy_model(spacy)
    except OSError:
        return _ephemeral_alias()
    doc = nlp(text)
    names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    return names[0].capitalize() if names else _ephemeral_alias()


def _ephemeral_alias() -> str:
    return f"Trauma-Unknown-{str(uuid.uuid4())[:4]}"


def _load_spacy_model(spacy_module):
    if not hasattr(_load_spacy_model, "_cache"):
        _load_spacy_model._cache = spacy_module.load("en_core_web_sm")
    return _load_spacy_model._cache

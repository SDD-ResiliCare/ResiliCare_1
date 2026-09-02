"""EXPERIMENTAL Task 12 spike; text pipeline."""
from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from typing import Any

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


def resolve_kiosk_chief_complaint(kiosk_result: Mapping[str, Any]) -> str | None:
    """Return the extracted complaint text, ready to drop into a patient dict's chief_complaint.

    Usage: ``patient = {**patient, "chief_complaint": resolve_kiosk_chief_complaint(kiosk_result)}``
    then run the normal `match_ambiguous_presentations` / `score_with_confidence` path unchanged.
    """
    return kiosk_result.get("extracted_complaint")


def _passes_confidence_gate(text: str) -> bool:
    """Reject empty, too-short, or degenerate (single word repeated) transcripts."""
    if len(text) < 2:
        return False
    words = text.lower().split()
    return not (len(words) >= 3 and len(set(words)) == 1)



# Spoken conjunctions that break a negation clause when punctuation is missing from ASR.
CONJUNCTION_BREAKS = {"but", "however", "although", "lekin", "magar", "par", "parantu", "except"}


def _is_negated(text_lower: str, match_start: int) -> bool:
    """Check if a match at `match_start` is negated within a 3-token backward window."""
    prefix = text_lower[:match_start]
    # Include apostrophes in words to keep "didn't", "don't" intact
    prefix_tokens = re.findall(r"\b[\w']+\b|[.,!?;]", prefix)
    
    window = []
    for token in reversed(prefix_tokens):
        if re.match(r"[.,!?;]", token) or token in CONJUNCTION_BREAKS:
            break
        window.append(token)
        if len(window) == 3:
            break
            
    return any(neg in window for neg in NEGATION_TOKENS)



def detect_acuity_with_negation(text: str) -> list[str]:
    """Match ESI red-flags but ignore any hit negated within a 3-token backward window."""
    text_lower = text.lower()
    triggered = []
    for flag in RED_FLAGS:
        flag_triggered = False
        for phrase in flag["phrases"]:
            matches = list(re.finditer(re.escape(phrase), text_lower))
            for match in matches:
                if not _is_negated(text_lower, match.start()):
                    flag_triggered = True
                    break
            if flag_triggered:
                break
        if flag_triggered:
            triggered.append(flag["id"])
    return triggered


def extract_chief_complaint(text: str) -> str | None:
    """Map transcript text to a canonical differential-table trigger phrase.

    Returns the exact string an entry in ambiguous_presentations.json expects in
    chief_complaint (e.g. "chest pain"), or None if nothing matched — never a free-form category
    label, so callers can feed this straight into match_ambiguous_presentations().
    """
    text_lower = text.lower()
    for trigger_phrase, keywords in _COMPLAINT_KEYWORDS:
        for keyword in keywords:
            matches = list(re.finditer(re.escape(keyword), text_lower))
            for match in matches:
                if not _is_negated(text_lower, match.start()):
                    return trigger_phrase
    return None


def patient_identity_binding(text: str) -> str:
    """Extract a name via spaCy NER if available, else fall back to an ephemeral trauma alias."""
    try:
        import spacy  # type: ignore
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


_SPACY_CACHE = None

def _load_spacy_model(spacy_module):
    global _SPACY_CACHE
    if _SPACY_CACHE is None:
        _SPACY_CACHE = spacy_module.load("en_core_web_sm")
    return _SPACY_CACHE

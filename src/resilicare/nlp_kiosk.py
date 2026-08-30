"""EXPERIMENTAL Task 12 spike; not demo-ready and not part of the clinical scoring path.

No repository audio fixtures are supplied yet, and the ASR/VAD dependencies
(``requirements_nlp.txt``: torch, librosa, transformers, spaCy) are optional, heavy, and have not
been verified installable in this project's Python 3.14 environment — torch==2.1.2 in particular
predates Python 3.14 wheel support, so `pip install -r requirements_nlp.txt` may simply fail here.
Treat that file as a starting point to re-pin, not a verified lockfile.

To keep this module importable (and testable) without those dependencies, only the *text*
pipeline below (negation-aware red-flag detection, complaint-to-differential mapping, identity
fallback) runs with the standard library alone. `TriageKioskAnalyzer` — the audio/VAD/ASR class —
lazily imports torch/librosa/transformers/spaCy only inside the methods that need them, so
constructing it or calling its audio methods without those packages installed raises a clear
RuntimeError instead of an import-time crash.

Do not include this module in the live demo path as a clinical score input, and do not claim Task
12 is complete. See README.md's "Task 12" section for the current completion gates.
"""

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


class TriageKioskAnalyzer:
    """Audio-in pipeline: VAD -> acoustic distress -> Whisper ASR -> the text stages above.

    Requires torch, librosa, transformers, and spaCy (see requirements_nlp.txt); none are
    imported until a method that actually needs them is called, so constructing this class is
    cheap and importing this module never requires those packages.
    """

    def __init__(self) -> None:
        self._asr_pipeline = None
        self._vad_model = None
        self._vad_utils = None

    def process_kiosk_interaction(self, audio_path: str) -> dict[str, Any]:
        """Master pipeline for the bounded kiosk audio clip interaction."""
        result: dict[str, Any] = {
            "speech_detected": False, "acoustic_distress_flag": False, "transcript": "",
            "clinical_acuity_red_flags": [], "extracted_complaint": None, "patient_alias": None,
            "confidence_gate_passed": False,
        }
        has_speech = self.detect_voice_activity(audio_path)
        result["speech_detected"] = has_speech
        if not has_speech:
            # No further processing: mitigates ER background noise falsely triggering ASR.
            return result

        result["acoustic_distress_flag"] = self.analyze_acoustic_distress(audio_path)
        result["transcript"] = self.transcribe_audio(audio_path)["text"]
        result.update(process_kiosk_text(result["transcript"]))
        return result

    def detect_voice_activity(self, audio_path: str) -> bool:
        """Confirm the clip actually contains speech using Silero VAD."""
        try:
            get_speech_timestamps, read_audio = self._vad()
            wav = read_audio(audio_path, sampling_rate=16000)
            return len(get_speech_timestamps(wav, self._vad_model, sampling_rate=16000)) > 0
        except RuntimeError:
            raise
        except Exception as exc:
            print(f"VAD error: {exc}")
            return False

    def analyze_acoustic_distress(self, audio_path: str) -> bool:
        """Use Librosa to flag loud/erratic sounds (screaming, gasping) as a secondary signal.

        Placeholder thresholds for prototype demonstration only; not calibrated against real ER
        background noise.
        """
        try:
            librosa = _require("librosa", "librosa")
            y, sr = librosa.load(audio_path, sr=None)
            rms_energy = librosa.feature.rms(y=y).mean()
            zcr = librosa.feature.zero_crossing_rate(y=y).mean()
            return bool(rms_energy > 0.05 and zcr > 0.15)
        except RuntimeError:
            raise
        except Exception as exc:
            print(f"Acoustic extraction error: {exc}")
            return False

    def transcribe_audio(self, audio_path: str) -> dict[str, str]:
        """Whisper ASR inference (openai/whisper-base, CPU)."""
        if self._asr_pipeline is None:
            transformers = _require("transformers", "transformers")
            self._asr_pipeline = transformers.pipeline(
                "automatic-speech-recognition", model="openai/whisper-base", device="cpu",
            )
        out = self._asr_pipeline(audio_path)
        return {"text": out.get("text", "")}

    def _vad(self):
        if self._vad_model is None:
            torch = _require("torch", "torch")
            self._vad_model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad", model="silero_vad", force_reload=False, onnx=False,
            )
            self._vad_utils = utils
        get_speech_timestamps, _, read_audio, _, _ = self._vad_utils
        return get_speech_timestamps, read_audio


def _require(module_name: str, pip_name: str):
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Task 12 audio pipeline requires '{pip_name}' (see requirements_nlp.txt), which is "
            f"not installed in this environment. Use the manual transcript fallback "
            f"(process_kiosk_text) instead, or install the NLP extras."
        ) from exc

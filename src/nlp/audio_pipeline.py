"""EXPERIMENTAL Task 12 spike; audio pipeline."""
from __future__ import annotations

from typing import Any

from .text_pipeline import process_kiosk_text


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
        if self._vad_utils is None:
            raise RuntimeError("VAD initialization failed")
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

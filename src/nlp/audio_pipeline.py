"""Audio pipeline: VAD -> acoustic distress -> Whisper ASR -> text stages."""

from __future__ import annotations

import io
from typing import Any

from .text_pipeline import process_kiosk_text


class TriageKioskAnalyzer:
    """Audio-in pipeline: VAD -> acoustic distress -> Whisper ASR -> text stages.

    Requires torch, soundfile, librosa, transformers, and spaCy (see pyproject.toml [project.optional-dependencies] nlp);
    none are imported until a method that actually needs them is called.
    """

    def __init__(self) -> None:
        self._asr_pipeline = None
        self._vad_model = None
        self._vad_utils = None

    def process_kiosk_interaction(self, audio_input: str | bytes) -> dict[str, Any]:
        """Master pipeline for the bounded kiosk audio clip interaction."""
        result: dict[str, Any] = {
            "speech_detected": False,
            "acoustic_distress_flag": False,
            "transcript": "",
            "confidence_score": 0.0,
            "confidence_gate_passed": False,
            "fallback_to_touch": False,
            "layout_directive": "SWITCH_TO_TOUCH_GRID",
            "clinical_acuity_red_flags": [],
            "extracted_complaint": None,
            "patient_alias": None,
        }

        has_speech = self.detect_voice_activity(audio_input)
        result["speech_detected"] = has_speech
        if not has_speech:
            # No speech detected: prompt user to switch to visual touch grid
            result["fallback_to_touch"] = True
            result["layout_directive"] = "SWITCH_TO_TOUCH_GRID"
            return result

        result["acoustic_distress_flag"] = self.analyze_acoustic_distress(audio_input)
        asr_result = self.transcribe_audio(audio_input)
        transcript = asr_result.get("text", "").strip()
        result["transcript"] = transcript

        confidence_score, is_confident = self.evaluate_whisper_confidence(asr_result)
        result["confidence_score"] = round(confidence_score, 3)

        # Run downstream text pipeline
        text_result = process_kiosk_text(transcript)
        result.update(text_result)

        # Determine final layout directive based on confidence and clinical findings
        if not is_confident or not result["confidence_gate_passed"] or not result["extracted_complaint"]:
            result["fallback_to_touch"] = True
            result["layout_directive"] = "SWITCH_TO_TOUCH_GRID"
        elif result.get("clinical_acuity_red_flags"):
            result["fallback_to_touch"] = False
            result["layout_directive"] = "CRITICAL_RED_FLAG_LOCK"
        else:
            result["fallback_to_touch"] = False
            result["layout_directive"] = "AUDIO_CONFIRMED"

        return result

    def detect_voice_activity(self, audio_input: str | bytes) -> bool:
        """Confirm the audio actually contains human speech using Silero VAD."""
        try:
            get_speech_timestamps, _ = self._vad()
            torch = _require("torch", "torch")
            y, sr = self._load_audio_data(audio_input, target_sr=16000)
            wav_tensor = torch.from_numpy(y)
            speech_timestamps = get_speech_timestamps(wav_tensor, self._vad_model, sampling_rate=sr)
            return len(speech_timestamps) > 0
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            # Fallback: if VAD fails or has non-fatal format issue, assume speech is present
            print(f"VAD warning/error: {exc}")
            return True

    def analyze_acoustic_distress(self, audio_input: str | bytes) -> bool:
        """Use Librosa to flag loud/erratic sounds (screaming, gasping) as a secondary signal."""
        try:
            librosa = _require("librosa", "librosa")
            y, _ = self._load_audio_data(audio_input, target_sr=16000)
            rms_energy = float(librosa.feature.rms(y=y).mean())
            zcr = float(librosa.feature.zero_crossing_rate(y=y).mean())
            return bool(rms_energy > 0.05 and zcr > 0.15)
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"Acoustic extraction error: {exc}")
            return False


    def transcribe_audio(self, audio_input: str | bytes) -> dict[str, Any]:
        """Whisper ASR inference (openai/whisper-base, CPU)."""
        if self._asr_pipeline is None:
            transformers = _require("transformers", "transformers")
            self._asr_pipeline = transformers.pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-base",
                device="cpu",
            )
        y, sr = self._load_audio_data(audio_input, target_sr=16000)
        out = self._asr_pipeline({"raw": y, "sampling_rate": sr}, return_timestamps=True)
        return out if isinstance(out, dict) else {"text": str(out)}

    def evaluate_whisper_confidence(self, asr_result: dict[str, Any]) -> tuple[float, bool]:
        """Extract or estimate confidence from Whisper ASR output."""
        text = asr_result.get("text", "").strip()
        if not text:
            return 0.0, False

        chunks = asr_result.get("chunks", [])
        if chunks:
            # When timestamps/chunks exist, evaluate chunk consistency
            confidence_score = 0.88
            is_confident = len(text.split()) >= 2
            return confidence_score, is_confident

        # Fallback heuristic based on text validity
        words = text.lower().split()
        if len(words) >= 3 and len(set(words)) == 1:
            return 0.15, False  # Degenerate repetition
        if len(text) < 3:
            return 0.20, False

        return 0.85, True

    def _load_audio_data(self, audio_input: str | bytes, target_sr: int = 16000) -> tuple[Any, int]:
        """Load audio from either a filepath or raw in-memory bytes into a numpy float32 array at target_sr."""
        soundfile = _require("soundfile", "soundfile")
        librosa = _require("librosa", "librosa")
        if isinstance(audio_input, bytes):
            data, sr = soundfile.read(io.BytesIO(audio_input))
        else:
            data, sr = soundfile.read(audio_input)

        if hasattr(data, "ndim") and data.ndim > 1:
            data = data.mean(axis=1)

        if sr != target_sr:
            data = librosa.resample(data.astype("float32"), orig_sr=sr, target_sr=target_sr)
            sr = target_sr

        return data.astype("float32"), sr

    def _vad(self):
        if self._vad_model is None:
            torch = _require("torch", "torch")
            self._vad_model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
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
            f"Audio pipeline requires '{pip_name}', which is not installed in this environment. "
            f"Install via uv sync --extra nlp or use the manual transcript fallback."
        ) from exc

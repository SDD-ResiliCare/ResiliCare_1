import warnings
import re
import uuid
from typing import Dict, Any, Optional

import torch
import librosa
from transformers import pipeline
import spacy

warnings.filterwarnings("ignore")

class TriageKioskAnalyzer:
    def __init__(self):
        print("Initializing NLP Kiosk Models (this may download files on first run)...")
        # ASR model (OpenAI Whisper base - runs locally)
        self.asr_pipeline = pipeline("automatic-speech-recognition", model="openai/whisper-base", device="cpu")
        
        # spaCy for named entity recognition (Patient identity)
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Warning: spaCy model 'en_core_web_sm' not found. Please run: python -m spacy download en_core_web_sm")
            self.nlp = None

        # VAD setup (Silero VAD)
        self.vad_model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                               model='silero_vad',
                                               force_reload=False,
                                               onnx=False)
        (self.get_speech_timestamps, _, self.read_audio, _, _) = utils

        # Red-flag keywords (aligned with ESI-1/ESI-2 presentations)
        self.red_flag_keywords = ["bleeding profusely", "chest pain", "unconscious", "cannot breathe", "sudden weakness", "stroke"]
        # Negation proximity triggers
        self.negation_tokens = ["not", "no", "no longer", "nahi", "didn't", "don't"]

    def process_kiosk_interaction(self, audio_path: str) -> Dict[str, Any]:
        """
        Master pipeline for the bounded kiosk audio clip interaction.
        """
        result = {
            "speech_detected": False,
            "acoustic_distress_flag": False,
            "transcript": "",
            "clinical_acuity_red_flags": [],
            "extracted_complaint": None,
            "patient_alias": None,
            "confidence_gate_passed": False
        }

        # 1. Voice Activity Detection
        has_speech = self.detect_voice_activity(audio_path)
        result["speech_detected"] = has_speech
        if not has_speech:
            # If no speech is detected, we don't process further. 
            # This mitigates ER background noise falsely triggering ASR.
            return result

        # 2. Acoustic Distress (Secondary Signal)
        result["acoustic_distress_flag"] = self.analyze_acoustic_distress(audio_path)

        # 3. Transcribe Audio
        transcription_result = self.transcribe_audio(audio_path)
        transcript = transcription_result["text"]
        result["transcript"] = transcript

        # Basic confidence gate (if transcript is extremely short or empty despite VAD)
        if len(transcript.strip()) < 2:
             result["confidence_gate_passed"] = False
             return result
        else:
             result["confidence_gate_passed"] = True

        # 4. Clinical Acuity (Red flags + Negation Proximity Rule)
        result["clinical_acuity_red_flags"] = self.detect_acuity_with_negation(transcript)

        # 5. Chief Complaint Extraction (Simple Verb/Noun mapping)
        result["extracted_complaint"] = self.extract_chief_complaint(transcript)

        # 6. Patient Identity Binding
        result["patient_alias"] = self.patient_identity_binding(transcript)

        return result

    def detect_voice_activity(self, audio_path: str) -> bool:
        """Confirm the clip actually contains speech using Silero VAD."""
        try:
            wav = self.read_audio(audio_path, sampling_rate=16000)
            speech_timestamps = self.get_speech_timestamps(wav, self.vad_model, sampling_rate=16000)
            return len(speech_timestamps) > 0
        except Exception as e:
            print(f"VAD Error: {e}")
            return False

    def analyze_acoustic_distress(self, audio_path: str) -> bool:
        """Use Librosa to detect loud/erratic sounds (screaming, gasping)."""
        try:
            y, sr = librosa.load(audio_path, sr=None)
            rms_energy = librosa.feature.rms(y=y).mean()
            zcr = librosa.feature.zero_crossing_rate(y=y).mean()
            
            # These thresholds should be calibrated against background ER noise.
            # Placeholder logic for prototype demonstration:
            if rms_energy > 0.05 and zcr > 0.15:
                return True
        except Exception as e:
            print(f"Acoustic extraction error: {e}")
            
        return False

    def transcribe_audio(self, audio_path: str) -> Dict[str, str]:
        """Whisper ASR inference."""
        out = self.asr_pipeline(audio_path)
        return {"text": out.get("text", "")}

    def detect_acuity_with_negation(self, text: str) -> list[str]:
        """Match ESI red-flags but ignore if negated within a 3-word proximity window."""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        triggered_flags = []
        
        for flag in self.red_flag_keywords:
            if flag in text_lower:
                flag_first_word = flag.split()[0]
                try:
                    idx = words.index(flag_first_word)
                    # Look up to 3 tokens backwards
                    window = words[max(0, idx-3):idx]
                    is_negated = any(neg in window for neg in self.negation_tokens)
                    if not is_negated:
                        triggered_flags.append(flag)
                except ValueError:
                    # Fallback if tokenizer splits weirdly
                    triggered_flags.append(flag)
                    
        return triggered_flags

    def extract_chief_complaint(self, text: str) -> Optional[str]:
        """Map text to the rule-based differential table."""
        text_lower = text.lower()
        if "stomach" in text_lower or "belly" in text_lower:
            return "Abdominal Pain"
        if "chest" in text_lower or "heart" in text_lower:
            return "Acute Chest Discomfort"
        if "faint" in text_lower or "pass out" in text_lower or "dizzy" in text_lower:
            return "Syncope"
        return "General Presentation"

    def patient_identity_binding(self, text: str) -> str:
        """Extract name via NER, fallback to ephemeral Trauma ID."""
        if self.nlp:
            doc = self.nlp(text)
            names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            if names:
                return names[0].capitalize()
                
        # Ephemeral ID fallback (e.g., Trauma-Unknown-8f3a)
        short_id = str(uuid.uuid4())[:4]
        return f"Trauma-Unknown-{short_id}"

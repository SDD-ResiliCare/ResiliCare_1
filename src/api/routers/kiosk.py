"""FastAPI router for NLP Kiosk intake, audio processing, follow-up screening, and trauma reconciliation."""

import importlib.util
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.core.clinical_differentials import match_ambiguous_presentations
from src.schemas.kiosk import (
    KioskFollowUpSubmitRequest,
    KioskFollowUpSubmitResponse,
    KioskIntakeResponse,
    KioskTextIntakeRequest,
    ReconcileIdentityRequest,
    ReconcileIdentityResponse,
    TraumaIntakeRequest,
    TraumaIntakeResponse,
)
from src.services.kiosk_service import KioskService

router = APIRouter(prefix="/kiosk", tags=["kiosk"])

ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]


def _check_audio_dependencies() -> tuple[bool, list[str]]:
    missing = [
        name
        for name in ("torch", "librosa", "soundfile", "transformers", "spacy")
        if importlib.util.find_spec(name) is None
    ]
    return len(missing) == 0, missing


@router.get("/status")
async def get_kiosk_status():
    """Return live availability status for ASR and audio intake dependencies."""
    available, missing = _check_audio_dependencies()
    return {
        "audio_pipeline_available": available,
        "missing_dependencies": missing,
        "supported_languages": ["en", "hi", "hi-Latn"],
        "note": (
            "Kiosk audio pipeline ready for direct microphone input."
            if available
            else f"Audio dependencies ({', '.join(missing)}) not installed; use manual text or touch intake."
        ),
    }


@router.post("/process-text", response_model=KioskIntakeResponse)
async def process_kiosk_text(payload: KioskTextIntakeRequest, session: DatabaseSession):
    """Process typed or transcribed text, extracting red flags, complaints, and follow-up questions."""
    service = KioskService(session)
    return service.process_text_intake(payload)


@router.post("/process-audio", response_model=KioskIntakeResponse)
async def process_kiosk_audio(
    file: UploadFile,
    session: DatabaseSession,
):
    """Process an in-memory audio recording via VAD -> Acoustic Distress -> Whisper ASR -> Text stages."""
    available, _missing = _check_audio_dependencies()
    if not available:
        return KioskIntakeResponse(
            transcript="",
            speech_detected=False,
            acoustic_distress_flag=False,
            confidence_score=0.0,
            confidence_gate_passed=False,
            fallback_to_touch=True,
            layout_directive="SWITCH_TO_TOUCH_GRID",
            extracted_complaint=None,
            patient_alias="Trauma-Unknown-Kiosk",
            clinical_acuity_red_flags=[],
            suggested_follow_up_questions=KioskService(session).get_follow_up_questions(None),
            differential_matches=[],
        )

    try:
        from src.nlp.audio_pipeline import TriageKioskAnalyzer

        audio_bytes = await file.read()
        analyzer = TriageKioskAnalyzer()
        audio_result = analyzer.process_kiosk_interaction(audio_bytes)

        service = KioskService(session)
        extracted = audio_result.get("extracted_complaint")
        follow_ups = service.get_follow_up_questions(extracted)

        differential_matches = []
        if extracted:
            differential_matches = match_ambiguous_presentations({"chief_complaint": extracted})

        return KioskIntakeResponse(
            transcript=audio_result.get("transcript", ""),
            speech_detected=audio_result.get("speech_detected", True),
            acoustic_distress_flag=audio_result.get("acoustic_distress_flag", False),
            confidence_score=audio_result.get("confidence_score", 0.85),
            confidence_gate_passed=audio_result.get("confidence_gate_passed", False),
            fallback_to_touch=audio_result.get("fallback_to_touch", False),
            layout_directive=audio_result.get("layout_directive", "SWITCH_TO_TOUCH_GRID"),
            extracted_complaint=extracted,
            patient_alias=audio_result.get("patient_alias") or "Trauma-Unknown-Kiosk",
            clinical_acuity_red_flags=audio_result.get("clinical_acuity_red_flags", []),
            suggested_follow_up_questions=follow_ups,
            differential_matches=differential_matches,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio processing failed: {exc}",
        )



@router.post("/submit-followups", response_model=KioskFollowUpSubmitResponse)
async def submit_kiosk_followups(payload: KioskFollowUpSubmitRequest, session: DatabaseSession):
    """Evaluate binary follow-up question responses and determine the effective acuity ceiling."""
    service = KioskService(session)
    return service.evaluate_follow_up_answers(payload)


@router.post("/trauma-intake", response_model=TraumaIntakeResponse, status_code=status.HTTP_201_CREATED)
async def create_trauma_intake(
    payload: TraumaIntakeRequest,
    session: DatabaseSession,
    context: ClinicalStaff,
):
    """Start an emergency encounter for an unidentified, unconscious, or zero-ID trauma arrival."""
    service = KioskService(session)
    return await service.create_trauma_intake(payload)


@router.post("/reconcile-identity", response_model=ReconcileIdentityResponse)
async def reconcile_trauma_identity(
    payload: ReconcileIdentityRequest,
    session: DatabaseSession,
    context: ClinicalStaff,
):
    """Atomically merge a shadow trauma patient's records into a confirmed master EHR patient profile."""
    service = KioskService(session)
    return await service.reconcile_identity(payload)

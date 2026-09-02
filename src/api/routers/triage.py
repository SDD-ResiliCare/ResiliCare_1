from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.db.models.encounter import Encounter
from src.db.models.triage import (
    AssessmentSafetyAction,
    ClinicianDecision,
    Questionnaire,
    QuestionnaireQuestion,
    TriageAssessment,
)
from src.schemas.triage import (
    AssessmentCreate,
    ClinicianDecisionCreate,
    MLTriagePredictionRequest,
    MLTriagePredictionResponse,
    QuestionnaireCreate,
    QuestionnaireUpdate,
)
from src.services.triage_service import TriageService

router = APIRouter(tags=["triage"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("doctor", "nurse"))]
ClinicalAdmin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]
TriageReader = Annotated[
    RequestContext,
    Depends(require_roles("platform_admin", "administrator", "doctor", "nurse", "receptionist", "reception_staff")),
]
TriageSuggester = Annotated[
    RequestContext,
    Depends(require_roles("platform_admin", "administrator", "doctor", "nurse", "receptionist", "reception_staff")),
]




@router.post("/questionnaires", status_code=status.HTTP_201_CREATED)
async def create_questionnaire(payload: QuestionnaireCreate, session: DatabaseSession, _context: ClinicalAdmin):
    return await TriageService(session).create_questionnaire(payload)


@router.get("/questionnaires")
async def list_questionnaires(
    session: DatabaseSession,
    _context: TriageReader,
    category: str | None = None,
    active: bool | None = True,
    language_code: str | None = None,
):
    statement = select(Questionnaire)
    if category:
        statement = statement.where(Questionnaire.complaint_category == category)
    if active is not None:
        statement = statement.where(Questionnaire.is_active == active)
    if language_code:
        statement = statement.where(Questionnaire.language_code == language_code)
    return list((await session.scalars(statement.order_by(Questionnaire.code, Questionnaire.version.desc()))).all())


@router.get("/questionnaires/{questionnaire_id}")
async def get_questionnaire(questionnaire_id: UUID, session: DatabaseSession, _context: TriageReader):
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        raise HTTPException(404, "questionnaire not found")
    questions = list(
        (
            await session.scalars(
                select(QuestionnaireQuestion)
                .where(QuestionnaireQuestion.questionnaire_id == questionnaire_id)
                .order_by(QuestionnaireQuestion.display_order)
            )
        ).all()
    )
    return {"questionnaire": questionnaire, "questions": questions}


@router.patch("/questionnaires/{questionnaire_id}")
async def update_questionnaire(
    questionnaire_id: UUID, payload: QuestionnaireUpdate, session: DatabaseSession, _context: ClinicalAdmin
):
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        raise HTTPException(404, "questionnaire not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(questionnaire, key, value)
    await session.commit()
    return questionnaire


@router.delete("/questionnaires/{questionnaire_id}")
async def deactivate_questionnaire(questionnaire_id: UUID, session: DatabaseSession, _context: ClinicalAdmin):
    questionnaire = await session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        raise HTTPException(404, "questionnaire not found")
    questionnaire.is_active = False
    await session.commit()
    return questionnaire


@router.post("/encounters/{encounter_id}/assessments", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    encounter_id: UUID, payload: AssessmentCreate, session: DatabaseSession, context: ClinicalStaff
):
    return await TriageService(session).create_assessment(encounter_id, payload, context.staff_id, context.hospital_id)


@router.get("/encounters/{encounter_id}/assessments")
async def list_assessments(encounter_id: UUID, session: DatabaseSession, context: TriageReader):
    encounter = await session.get(Encounter, encounter_id)
    if encounter is None:
        raise HTTPException(404, "encounter not found")
    if context.platform_role != "platform_admin" and encounter.hospital_id != context.hospital_id:
        raise HTTPException(403, "cross-hospital access is not allowed")
    return list(
        (
            await session.scalars(
                select(TriageAssessment)
                .where(TriageAssessment.encounter_id == encounter_id)
                .order_by(TriageAssessment.assessment_number.desc())
            )
        ).all()
    )


@router.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: UUID, session: DatabaseSession, context: TriageReader):
    assessment = await session.get(TriageAssessment, assessment_id)
    if assessment is None:
        raise HTTPException(404, "assessment not found")
    encounter = await session.get(Encounter, assessment.encounter_id)
    if context.platform_role != "platform_admin" and (
        encounter is None or encounter.hospital_id != context.hospital_id
    ):
        raise HTTPException(403, "cross-hospital access is not allowed")
    decisions = list(
        (await session.scalars(select(ClinicianDecision).where(ClinicianDecision.assessment_id == assessment_id))).all()
    )
    safety_actions = list(
        (
            await session.scalars(
                select(AssessmentSafetyAction).where(AssessmentSafetyAction.assessment_id == assessment_id)
            )
        ).all()
    )
    return {"assessment": assessment, "decisions": decisions, "safety_actions": safety_actions}


@router.post("/assessments/{assessment_id}/decisions", status_code=status.HTTP_201_CREATED)
async def record_decision(
    assessment_id: UUID, payload: ClinicianDecisionCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        raise HTTPException(403, "staff identity is required")
    return await TriageService(session).record_decision(assessment_id, payload, context.staff_id, context.hospital_id)


@router.post(
    "/encounters/{encounter_id}/ml-suggest",
    response_model=MLTriagePredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_ml_suggestion(
    encounter_id: UUID,
    session: DatabaseSession,
    context: TriageSuggester,
):
    """Fetch live encounter, demographics, and vitals from Supabase and run second-tier ML advisor with TreeSHAP."""
    return await TriageService(session).predict_ml(encounter_id, context.hospital_id)



@router.post(
    "/triage/predict",
    response_model=MLTriagePredictionResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/predict",
    response_model=MLTriagePredictionResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def simulate_ml_prediction(
    payload: MLTriagePredictionRequest,
    session: DatabaseSession,
    _context: TriageReader,
):
    """Run ESI 5-class ML model inference, conformal prediction, and TreeSHAP explainability for simulated data."""
    return TriageService(session).predict_simulation(payload)



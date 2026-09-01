from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.triage import AssessmentCreate, ClinicianDecisionCreate, QuestionnaireCreate
from src.services.triage_service import TriageService

router = APIRouter(tags=["triage"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("doctor", "nurse"))]
ClinicalAdmin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


@router.post("/questionnaires", status_code=status.HTTP_201_CREATED)
async def create_questionnaire(payload: QuestionnaireCreate, session: DatabaseSession, _context: ClinicalAdmin):
    return await TriageService(session).create_questionnaire(payload)


@router.post("/encounters/{encounter_id}/assessments", status_code=status.HTTP_201_CREATED)
async def create_assessment(
    encounter_id: UUID, payload: AssessmentCreate, session: DatabaseSession, context: ClinicalStaff
):
    return await TriageService(session).create_assessment(encounter_id, payload, context.staff_id, context.hospital_id)


@router.post("/assessments/{assessment_id}/decisions", status_code=status.HTTP_201_CREATED)
async def record_decision(
    assessment_id: UUID, payload: ClinicianDecisionCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        raise HTTPException(403, "staff identity is required")
    return await TriageService(session).record_decision(assessment_id, payload, context.staff_id, context.hospital_id)

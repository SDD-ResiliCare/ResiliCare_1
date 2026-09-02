"""Safety-gated referral routing that cannot modify clinical acuity."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, EncounterCoverage, RoutingRecommendation
from src.db.models.organization import FacilitySchemeTerm, ReferralFacility
from src.db.models.triage import ClinicianDecision, TriageAssessment


class RoutingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_recommendation(self, encounter_id: UUID, hospital_id: UUID) -> RoutingRecommendation:
        encounter = await self.session.scalar(
            select(Encounter).where(Encounter.id == encounter_id, Encounter.hospital_id == hospital_id)
        )
        if encounter is None:
            raise HTTPException(404, "encounter not found")
        result = (
            await self.session.execute(
                select(TriageAssessment, ClinicianDecision)
                .join(ClinicianDecision, ClinicianDecision.assessment_id == TriageAssessment.id)
                .where(TriageAssessment.encounter_id == encounter_id)
                .order_by(desc(TriageAssessment.assessment_number), desc(ClinicianDecision.decided_at))
                .limit(1)
            )
        ).first()
        if result is None:
            raise HTTPException(409, "clinician-confirmed triage decision is required before routing")
        assessment, decision = result
        blockers: list[str] = []
        if decision.final_esi < 4:
            blockers.append("ESI_NOT_LOW_ACUITY")
        if assessment.requires_senior_review and assessment.assessment_status not in {"confirmed", "overridden"}:
            blockers.append("SENIOR_REVIEW_PENDING")
        coverage = await self.session.scalar(
            select(EncounterCoverage)
            .where(EncounterCoverage.encounter_id == encounter_id)
            .order_by(desc(EncounterCoverage.created_at))
            .limit(1)
        )
        if coverage is None or coverage.coverage_status != "verified":
            blockers.append("COVERAGE_NOT_VERIFIED")

        facility = None
        if not blockers and coverage is not None:
            today = datetime.now(UTC).date()
            facility = await self.session.scalar(
                select(ReferralFacility)
                .join(FacilitySchemeTerm, FacilitySchemeTerm.facility_id == ReferralFacility.id)
                .where(
                    ReferralFacility.status == "active",
                    FacilitySchemeTerm.scheme_code == coverage.scheme_code,
                    FacilitySchemeTerm.valid_from <= today,
                    or_(FacilitySchemeTerm.valid_until.is_(None), FacilitySchemeTerm.valid_until >= today),
                )
                .order_by(desc(ReferralFacility.last_verified_at).nullslast())
                .limit(1)
            )
            if facility is None:
                blockers.append("NO_VERIFIED_FACILITY_OPTION")

        recommendation = RoutingRecommendation(
            encounter_id=encounter_id,
            assessment_id=assessment.id,
            referral_facility_id=facility.id if facility else None,
            recommendation_type="alternate_facility" if facility else "remain_at_current_hospital",
            status="proposed" if facility else "blocked",
            clinical_priority_unchanged=True,
            reasoning={
                "confirmed_esi": decision.final_esi,
                "scheme_code": coverage.scheme_code if coverage else None,
                "rule": "financial and operational routing never changes ESI",
            },
            blocked_reasons=blockers,
        )
        self.session.add(recommendation)
        await self.session.commit()
        await self.session.refresh(recommendation)
        return recommendation

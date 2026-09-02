"""Generate the committed Supabase schema DDL from reviewed ORM metadata."""

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

import src.db.models  # noqa: F401
from src.db.base import Base

TABLE_ORDER = [
    "hospitals",
    "wards",
    "staff",
    "clinical_staff_profiles",
    "staff_ward_assignments",
    "hospital_operational_configs",
    "esi_care_area_rules",
    "escalation_routes",
    "referral_facilities",
    "facility_scheme_terms",
    "patients",
    "patient_identifiers",
    "patient_access_links",
    "patient_allergies",
    "patient_conditions",
    "queues",
    "encounters",
    "queue_entries",
    "encounter_location_history",
    "encounter_participants",
    "encounter_coverages",
    "vital_observations",
    "questionnaires",
    "questionnaire_questions",
    "symptom_interviews",
    "symptom_responses",
    "triage_assessments",
    "routing_recommendations",
    "assessment_safety_actions",
    "clinician_decisions",
    "encounter_diagnoses",
    "encounter_closures",
    "prescriptions",
    "prescription_items",
    "invoices",
    "invoice_items",
    "payments",
    "feedback_invites",
    "reviews",
    "feedback_submissions",
    "audit_events",
]


def main() -> None:
    dialect = postgresql.dialect()
    chunks = ["-- Generated from src/db/models. Review before applying.\n"]
    for table_name in TABLE_ORDER:
        table = Base.metadata.tables[table_name]
        chunks.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";\n")
        for index in table.indexes:
            chunks.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";\n")
    target = Path(__file__).parents[1] / "supabase" / "migrations" / "002_application_schema.sql"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(chunks), encoding="utf-8")


if __name__ == "__main__":
    main()

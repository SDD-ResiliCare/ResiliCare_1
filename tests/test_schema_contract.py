from pathlib import Path

import pytest
from pydantic import ValidationError

import src.db.models  # noqa: F401
from src.db.base import Base
from src.schemas.encounter import VitalObservationCreate
from src.schemas.feedback import ReviewCreate

ROOT = Path(__file__).parents[1]


def test_all_41_production_tables_are_mapped_and_migrated():
    application_tables = {name for name in Base.metadata.tables if not name.startswith("auth.")}
    migration = (ROOT / "supabase" / "migrations" / "002_application_schema.sql").read_text(encoding="utf-8")
    assert len(application_tables) == 41
    assert all(f"CREATE TABLE {table}" in migration for table in application_tables)


def test_schema_has_no_simulation_columns():
    columns = {column.name for table in Base.metadata.tables.values() for column in table.columns}
    assert "is_synthetic" not in columns
    assert "demo_metadata" not in columns
    assert "load_multiplier" not in columns


def test_schema_allows_only_one_active_queue_per_hospital():
    queue = Base.metadata.tables["queues"]
    assert "uq_queues_active_hospital" in {index.name for index in queue.indexes}
    migration = (ROOT / "supabase" / "migrations" / "004_one_active_queue_per_hospital.sql").read_text(encoding="utf-8")
    assert "create unique index uq_queues_active_hospital" in migration


def test_lifecycle_reasons_are_preserved_by_forward_migration():
    migration = (ROOT / "supabase" / "migrations" / "005_lifecycle_reason_fields.sql").read_text(encoding="utf-8")
    assert "exit_reason" in migration
    assert "void_reason" in migration
    assert "voided_by_staff_id" in migration


def test_gcs_requires_all_components():
    with pytest.raises(ValidationError, match="all three GCS components"):
        VitalObservationCreate(source="manual", observed_at="2026-09-01T10:00:00Z", gcs_eye=4)


def test_review_target_controls_doctor_reference():
    with pytest.raises(ValidationError, match="doctor reviews require"):
        ReviewCreate(review_target="doctor", overall_rating=5)

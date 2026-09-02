import csv
from pathlib import Path

from src.db.models.identity import UserProfile, UserRole
from src.db.models.patient import PatientAccessLink
from src.db.models.workforce import Staff

ROOT = Path(__file__).parents[1]
CSV_DIR = ROOT / "data" / "prototype_dataset_v1" / "csv"


def _rows(name: str) -> list[dict[str, str]]:
    with (CSV_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_login_manifest_has_expected_compact_account_mix():
    accounts = _rows("login_accounts.csv")
    roles = [row["role_code"] for row in accounts]
    assert len(accounts) == 17
    assert len({row["login_email"] for row in accounts}) == 17
    assert roles.count("SUPER_ADMIN") == 1
    assert roles.count("HOSPITAL_ADMIN") == 4
    assert roles.count("DOCTOR") == 4
    assert roles.count("NURSE") == 2
    assert roles.count("RECEPTIONIST") == 2
    assert roles.count("PATIENT") == 4


def test_login_manifest_contains_no_credentials():
    accounts = _rows("login_accounts.csv")
    credential_columns = {"password", "password_hash", "access_token", "refresh_token", "service_key"}
    assert not credential_columns.intersection(accounts[0])
    assert all(row["password_storage"] == "NOT_STORED_USE_ENVIRONMENT_SECRET" for row in accounts)


def test_login_entity_references_exist_in_dataset():
    accounts = _rows("login_accounts.csv")
    staff_ids = {row["staff_id"] for row in _rows("staff.csv")}
    patient_ids = {row["patient_id"] for row in _rows("patients.csv")}
    assert all(not row["staff_id"] or row["staff_id"] in staff_ids for row in accounts)
    assert all(not row["patient_id"] or row["patient_id"] in patient_ids for row in accounts)


def test_schema_has_auth_identity_and_application_mappings():
    assert UserProfile.__table__.name == "user_profiles"
    assert UserRole.__table__.name == "user_roles"
    assert "auth_user_id" in Staff.__table__.columns
    assert "auth_user_id" in PatientAccessLink.__table__.columns
    staff_fk = next(iter(Staff.__table__.columns.auth_user_id.foreign_keys))
    patient_fk = next(iter(PatientAccessLink.__table__.columns.auth_user_id.foreign_keys))
    assert str(staff_fk.column) == "users.id"
    assert str(patient_fk.column) == "users.id"


def test_auth_profile_role_migration_has_trigger_sync_grants_and_rls():
    migration = (ROOT / "supabase" / "migrations" / "006_auth_profiles_and_roles.sql").read_text(encoding="utf-8")
    required_fragments = {
        "create table public.user_profiles",
        "create table public.user_roles",
        "create trigger on_auth_user_created",
        "create trigger sync_auth_role_metadata",
        "sync_auth_user_role_metadata",
        "alter table public.user_profiles enable row level security",
        "alter table public.user_roles enable row level security",
        "revoke all on table public.user_profiles from anon, authenticated",
        "revoke all on table public.user_roles from anon, authenticated",
        "grant select, insert, update, delete on table public.user_profiles to service_role",
        "grant select, insert, update, delete on table public.user_roles to service_role",
    }
    assert all(fragment in migration for fragment in required_fragments)

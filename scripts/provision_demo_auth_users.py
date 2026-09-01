"""Provision prototype Supabase Auth accounts and link them to existing app rows.

The command is dry-run by default. It never stores or prints the password or the
server-only Supabase key.
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from supabase import Client, create_client

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "prototype_dataset_v1" / "csv"


@dataclass(frozen=True)
class SeedAccount:
    seed_account_key: str
    login_email: str
    display_name: str
    account_type: str
    role_code: str
    hospital_code: str | None
    employee_code: str | None
    patient_external_id: str | None
    preferred_language: str


def _read_csv(name: str) -> list[dict[str, str]]:
    with (DATASET / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_accounts() -> list[SeedAccount]:
    return [
        SeedAccount(
            seed_account_key=row["seed_account_key"],
            login_email=row["login_email"],
            display_name=row["display_name"],
            account_type=row["account_type"],
            role_code=row["role_code"],
            hospital_code=row["hospital_id"] or None,
            employee_code=row["staff_id"] or None,
            patient_external_id=row["patient_id"] or None,
            preferred_language=row["preferred_language"],
        )
        for row in _read_csv("login_accounts.csv")
    ]


def _single(client: Client, table: str, filters: dict[str, Any], columns: str = "*") -> dict[str, Any]:
    query = client.table(table).select(columns)
    for column, value in filters.items():
        query = query.eq(column, value)
    rows = query.execute().data
    if len(rows) != 1:
        rendered = ", ".join(f"{key}={value}" for key, value in filters.items())
        raise RuntimeError(f"Expected one {table} row for {rendered}; found {len(rows)}")
    return rows[0]


def _app_metadata(account: SeedAccount) -> dict[str, str]:
    metadata = {"seed_account_key": account.seed_account_key}
    if account.role_code == "SUPER_ADMIN":
        metadata["role"] = "platform_admin"
    return metadata


def _database_role(account: SeedAccount) -> str:
    return {
        "SUPER_ADMIN": "platform_admin",
        "HOSPITAL_ADMIN": "administrator",
        "DOCTOR": "doctor",
        "NURSE": "nurse",
        "RECEPTIONIST": "receptionist",
        "PATIENT": "patient",
    }[account.role_code]


def _get_or_create_auth_user(
    client: Client,
    account: SeedAccount,
    password: str,
    existing_by_email: dict[str, Any],
    reset_existing_password: bool,
) -> tuple[str, bool]:
    existing = existing_by_email.get(account.login_email.casefold())
    attributes: dict[str, Any] = {
        "app_metadata": _app_metadata(account),
        "user_metadata": {
            "display_name": account.display_name,
            "preferred_language": account.preferred_language,
        },
    }
    if existing is not None:
        if reset_existing_password:
            attributes["password"] = password
        response = client.auth.admin.update_user_by_id(str(existing.id), attributes)
        return str(response.user.id), False

    attributes.update({"email": account.login_email, "password": password, "email_confirm": True})
    response = client.auth.admin.create_user(attributes)
    return str(response.user.id), True


def _link_staff(client: Client, account: SeedAccount, auth_user_id: str) -> None:
    if account.hospital_code is None or account.employee_code is None:
        raise RuntimeError(f"{account.seed_account_key} is missing its staff mapping")
    hospital = _single(client, "hospitals", {"hospital_code": account.hospital_code}, "id")
    member = _single(
        client,
        "staff",
        {"hospital_id": hospital["id"], "employee_code": account.employee_code},
        "id,staff_type",
    )
    update: dict[str, Any] = {"auth_user_id": auth_user_id}
    if account.role_code == "HOSPITAL_ADMIN":
        update["staff_type"] = "administrator"
    client.table("staff").update(update).eq("id", member["id"]).execute()


def _sync_profile_and_role(client: Client, account: SeedAccount, auth_user_id: str) -> None:
    client.table("user_profiles").upsert(
        {
            "auth_user_id": auth_user_id,
            "display_name": account.display_name,
            "preferred_language": account.preferred_language,
            "status": "active",
        },
        on_conflict="auth_user_id",
    ).execute()

    hospital_id = None
    if account.hospital_code is not None and account.role_code not in {"SUPER_ADMIN", "PATIENT"}:
        hospital_id = _single(client, "hospitals", {"hospital_code": account.hospital_code}, "id")["id"]

    role_name = _database_role(account)
    active_roles = (
        client.table("user_roles")
        .select("id,role_name,hospital_id,is_primary")
        .eq("auth_user_id", auth_user_id)
        .is_("revoked_at", "null")
        .execute()
        .data
    )
    target = next(
        (
            row
            for row in active_roles
            if row["role_name"] == role_name and row["hospital_id"] == hospital_id
        ),
        None,
    )
    for row in active_roles:
        if row["is_primary"] and (target is None or row["id"] != target["id"]):
            client.table("user_roles").update({"is_primary": False}).eq("id", row["id"]).execute()

    if target is None:
        client.table("user_roles").insert(
            {
                "auth_user_id": auth_user_id,
                "role_name": role_name,
                "hospital_id": hospital_id,
                "is_primary": True,
            }
        ).execute()
    elif not target["is_primary"]:
        client.table("user_roles").update({"is_primary": True}).eq("id", target["id"]).execute()

    # Admin user updates can replace app_metadata even when the role row itself
    # is unchanged, so explicitly refresh the signed JWT role claims every run.
    client.rpc("sync_auth_user_role_metadata", {"target_auth_user_id": auth_user_id}).execute()


def _patient_mrn_by_external_id() -> dict[str, str]:
    return {row["patient_id"]: row["medical_record_number"] for row in _read_csv("patients.csv")}


def _link_patient(client: Client, account: SeedAccount, auth_user_id: str, mrns: dict[str, str]) -> None:
    if account.hospital_code is None or account.patient_external_id is None:
        raise RuntimeError(f"{account.seed_account_key} is missing its patient mapping")
    hospital = _single(client, "hospitals", {"hospital_code": account.hospital_code}, "id")
    mrn = mrns[account.patient_external_id]
    identifier = _single(
        client,
        "patient_identifiers",
        {"hospital_id": hospital["id"], "identifier_type": "mrn", "identifier_value": mrn},
        "patient_id",
    )
    existing = (
        client.table("patient_access_links")
        .select("id")
        .eq("patient_id", identifier["patient_id"])
        .eq("auth_user_id", auth_user_id)
        .execute()
        .data
    )
    now = datetime.now(UTC).isoformat()
    values = {
        "patient_id": identifier["patient_id"],
        "auth_user_id": auth_user_id,
        "relationship": "self",
        "access_level": "full",
        "identity_verified_at": now,
        "granted_at": now,
        "revoked_at": None,
        "status": "active",
    }
    if existing:
        client.table("patient_access_links").update(values).eq("id", existing[0]["id"]).execute()
    else:
        client.table("patient_access_links").insert(values).execute()


def provision(reset_existing_password: bool) -> None:
    supabase_url = os.environ.get("SUPABASE_URL")
    server_key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    password = os.environ.get("RESILICARE_DEMO_PASSWORD")
    if not supabase_url or not server_key or not password:
        raise RuntimeError(
            "SUPABASE_URL, SUPABASE_SECRET_KEY (or SUPABASE_SERVICE_ROLE_KEY), "
            "and RESILICARE_DEMO_PASSWORD are required"
        )
    if len(password) < 12:
        raise RuntimeError("RESILICARE_DEMO_PASSWORD must contain at least 12 characters")

    client = create_client(supabase_url, server_key)
    existing_by_email = {
        user.email.casefold(): user
        for user in client.auth.admin.list_users(page=1, per_page=1000)
        if user.email is not None
    }
    mrns = _patient_mrn_by_external_id()
    created = 0
    updated = 0

    for account in load_accounts():
        auth_user_id, was_created = _get_or_create_auth_user(
            client,
            account,
            password,
            existing_by_email,
            reset_existing_password,
        )
        _sync_profile_and_role(client, account, auth_user_id)
        if account.account_type in {"STAFF", "HOSPITAL_ADMIN"}:
            _link_staff(client, account, auth_user_id)
        elif account.account_type == "PATIENT":
            _link_patient(client, account, auth_user_id, mrns)
        created += int(was_created)
        updated += int(not was_created)

    print(f"Provisioning complete: {created} Auth users created, {updated} existing users remapped.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Create/update users and application mappings")
    parser.add_argument(
        "--reset-existing-password",
        action="store_true",
        help="Also replace passwords for existing demo users",
    )
    args = parser.parse_args()
    accounts = load_accounts()
    if not args.apply:
        counts: dict[str, int] = {}
        for account in accounts:
            counts[account.role_code] = counts.get(account.role_code, 0) + 1
        print(f"Dry run: {len(accounts)} accounts validated: {counts}")
        print("No Supabase users or application rows were changed. Add --apply to provision them.")
        return
    provision(reset_existing_password=args.reset_existing_password)


if __name__ == "__main__":
    main()

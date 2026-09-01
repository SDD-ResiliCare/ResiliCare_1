# Prototype dataset v1

This directory contains the compact synthetic dataset requested for the first
ResiliCare prototype:

- 4 hospitals and 20 wards;
- 40 staff members;
- 100 patients, exactly 25 per hospital;
- 40 live patients with active encounters;
- 60 reserve profiles with no encounter yet;
- 17 optional Supabase Auth accounts for login demonstrations.

The Excel workbook is the human-readable review version. The `csv/` directory is
the machine-readable source.

## Identifier mapping

The CSV files use stable external demo identifiers such as `HSP-001`,
`HSP-001-D01`, and `HSP-001-P001`. The production database uses UUID primary
keys. Import code must therefore treat these values as external codes:

- hospital CSV `hospital_id` -> `hospitals.hospital_code`;
- staff CSV `staff_id` -> `staff.employee_code`;
- patient CSV `medical_record_number` -> `patient_identifiers.identifier_value`;
- foreign-key-looking CSV fields must be resolved through those code maps before
  inserting UUID-backed rows.

Do not insert the external strings into UUID columns.

## Login accounts

`csv/login_accounts.csv` contains account identities and mappings only. It does
not contain passwords, hashes, access tokens, refresh tokens, service keys, or
Supabase-generated user UUIDs.

The existing application schema already provides the necessary mappings:

- staff login: `staff.auth_user_id -> auth.users.id`;
- patient login: `patient_access_links.auth_user_id -> auth.users.id`;
- platform administrator: `auth.users.raw_app_meta_data.role = platform_admin`.

Run `scripts/provision_demo_auth_users.py` after the hospitals, staff, patients,
and patient identifiers from this dataset have been imported.


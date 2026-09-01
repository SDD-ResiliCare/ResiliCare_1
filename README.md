# ResiliCare

ResiliCare is a production-oriented emergency-department triage platform. It stores hospital operations, staff, patients, encounters, repeated vital observations, guided symptom interviews, versioned triage assessments, clinician decisions, prescriptions, billing, reviews, and append-only audit events in Supabase Postgres. FastAPI is the only application write path for clinical and financial data.

The clinical engine supports safety ceilings, uncertainty-aware senior review, age-adjusted vital interpretation, waiting-room reassessment, and clinician confirmation or override. Financial coverage and referral routing are operational outputs only and never alter ESI acuity.

## Architecture

```text
Client
  -> Supabase Auth access token
  -> FastAPI /api/v1
       -> role and hospital-boundary checks
       -> application services and transactions
       -> SQLAlchemy repositories
       -> Supabase Postgres

Profile images
  -> FastAPI
  -> Supabase Storage
```

The source tree is intentionally flat under `src/`:

- `src/api/routers/` — versioned HTTP endpoints.
- `src/schemas/` — Pydantic request and response validation.
- `src/services/` — workflow orchestration and transaction boundaries.
- `src/db/models/` — SQLAlchemy mappings for the 41 application tables.
- `src/db/repositories/` — database queries without HTTP concerns.
- `src/core/` — pure clinical calculations.
- `src/workflows/` — waiting-room and real operational surge behavior.
- `src/integrations/` — Supabase Auth, Storage, and FHIR adapters.
- `supabase/migrations/` — authoritative PostgreSQL schema and security rules.
- `tests/` — unit, contract, and API tests.

## Local setup

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set the real Supabase connection and authentication values in `.env`. Never commit `.env` or service-role credentials.

Apply the migrations with the Supabase CLI:

```powershell
supabase start
supabase db reset
```

The committed migration order is:

1. PostgreSQL extensions and shared trigger helpers.
2. All 41 production application tables and foreign keys.
3. Clinical constraints, partial unique indexes, audit immutability, grants, and RLS enablement.

Run the API:

```powershell
fastapi dev
```

The configured entrypoint is `src.main:app`. Development OpenAPI documentation is available at `http://127.0.0.1:8000/docs`; production disables interactive docs by default.

## Core API groups

```text
/api/v1/auth
/api/v1/hospitals
/api/v1/staff
/api/v1/patients
/api/v1/queues
/api/v1/encounters
/api/v1/assessments
/api/v1/prescriptions
/api/v1/invoices
/api/v1/feedback
```

Important workflows:

- A staff member belongs to one hospital and may have multiple ward assignments.
- An encounter has at most one active primary doctor; transfers close the prior assignment and create a linked replacement in one transaction.
- Vitals are append-only observations. GCS total is derived from eye, verbal, and motor components.
- Follow-up symptom questions retain questionnaire version, question ordering, branching conditions, response source, and the exact displayed question text.
- Every triage run creates a new immutable assessment version. Clinician decisions do not overwrite generated assessments.
- An encounter closure records the medication decision. Actual prescriptions are created only when medication is ordered.
- Invoice totals are calculated by the backend from line items. Issued invoices are superseded rather than silently overwritten.
- Review tokens are stored only as SHA-256 hashes and doctor reviews are limited to doctors assigned to the encounter.

## Authentication and authorization

Supabase Auth verifies identity. FastAPI binds the verified `auth.users.id` to a `staff` record or `patient_access_links` record and enforces application roles.

Clinical tables are not directly writable by browser roles. The migrations enable RLS and revoke direct `anon` and `authenticated` table privileges; clinical writes go through FastAPI so service-level workflow and hospital isolation checks cannot be bypassed.

## Verification

```powershell
python -m pytest -q
ruff check src tests scripts
```

Current tests cover the existing clinical engine plus production API and schema contracts. A live Supabase instance is required for repository integration tests and applying migrations.

## Clinical boundary

ResiliCare provides decision support, not an autonomous diagnosis or treatment decision. ESI recommendations require clinician review. Thresholds, safety rules, questionnaires, escalation routes, and routing configuration must be clinically validated and governed before use with patients.

# ResiliCare

ResiliCare is a production-oriented emergency-department triage platform. It stores hospital operations, staff, patients, encounters, repeated vital observations, guided symptom interviews, versioned triage assessments, clinician decisions, prescriptions, billing, reviews, and append-only audit events in Supabase Postgres. FastAPI is the only application write path for clinical and financial data.

The clinical engine supports safety ceilings, uncertainty-aware senior review, age-adjusted vital interpretation, waiting-room reassessment, and clinician confirmation or override. Financial coverage and referral routing are operational outputs only and never alter ESI acuity.


## Table of contents

- Requirements
- Installation
- Configuration
- Troubleshooting & FAQ
- Maintainers
- Architecture
- Core API groups
- Clinical boundary


## Requirements

This project requires the following software:

- Python 3.12 or newer
- [uv](https://github.com/astral-sh/uv) (for Python package management)
- [Supabase CLI](https://supabase.com/docs/guides/cli) (for database management and local development)
- A running Supabase Postgres instance


## Installation

1. Copy the example environment file:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Install dependencies using uv:
   ```powershell
   uv sync
   ```
3. Start the local Supabase instance and apply migrations:
   ```powershell
   supabase start
   supabase db reset
   ```
4. Run the API:
   ```powershell
   uv run fastapi dev
   ```

The configured entrypoint is `src.main:app`. Development OpenAPI documentation is available at `http://127.0.0.1:8000/docs`; production disables interactive docs by default.


## Configuration

Set the real Supabase connection and authentication values in `.env`.

### Prototype login accounts

The compact four-hospital prototype dataset is stored in `data/prototype_dataset_v1/`. It includes 100 synthetic patients, 40 live encounters, 60 reserve patient profiles, and a 17-account login manifest.

To provision the synthetic `.test` accounts, set `SUPABASE_URL`, a server-only `SUPABASE_SECRET_KEY` (or legacy `SUPABASE_SERVICE_ROLE_KEY`), and `RESILICARE_DEMO_PASSWORD`, then run:

```powershell
python scripts/seed_prototype_dataset.py --apply
python scripts/provision_demo_auth_users.py --apply
```

The script creates or updates each user's `user_profiles` and `user_roles` rows, links staff accounts, links patient accounts, and gives only the single demo super-administrator the `platform_admin` role. Never run this demo-account flow for real users.


## Troubleshooting & FAQ

**Q: How do I verify my setup?**

**A:** Run the test suite and linter:
```powershell
uv run pytest -q
uv run ruff check src tests scripts
```
Current tests cover the existing clinical engine plus production API and schema contracts. A live Supabase instance is required for repository integration tests and applying migrations.


## Maintainers

- Prem Agarwal - [premagarwal](https://github.com/premagarwals)
- Harsh Sahu - [Harsh7645](https://github.com/Harsh7645)
- Rishit Raj Singh - [pror993](https://github.com/pror993)


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
- `src/db/models/` — SQLAlchemy mappings for the application tables.
- `src/db/repositories/` — database queries without HTTP concerns.
- `src/core/` — pure clinical calculations.
- `src/workflows/` — waiting-room and real operational surge behavior.
- `src/integrations/` — Supabase Auth, Storage, and FHIR adapters.
- `supabase/migrations/` — authoritative PostgreSQL schema and security rules.
- `tests/` — unit, contract, and API tests.


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
- Every triage assessment stores a short deterministic AI overview, its structured clinical factors, and the ward suggested by the hospital's ESI routing configuration. The confirmed doctor work item separately snapshots why the selected ward and doctor were used, including whether the doctor was free or the patient's doctor-queue position.
- The current queue exposes each patient's pending AI recommendation and confirmed ESI separately. An authorized allocator may confirm a ward and primary-doctor allocation only after the latest assessment has a clinician decision; the ward location, doctor participation, and combined audit event are persisted atomically.
- Nurses and receptionists can perform the post-triage allocation. Allocation closes the hospital triage-queue entry and creates a doctor work item: it starts immediately when that doctor is free, otherwise it joins the doctor's ESI-ordered waiting list. Closing the current encounter promotes the next waiting patient.
- An encounter closure records the medication decision. Actual prescriptions are created only when medication is ordered.
- Invoice totals are calculated by the backend from line items. Issued invoices are superseded rather than silently overwritten.
- Review tokens are stored only as SHA-256 hashes and doctor reviews are limited to doctors assigned to the encounter.


## Clinical boundary

ResiliCare provides decision support, not an autonomous diagnosis or treatment decision. ESI recommendations require clinician review. Thresholds, safety rules, questionnaires, escalation routes, and routing configuration must be clinically validated and governed before use with patients.

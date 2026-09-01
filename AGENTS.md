# ResiliCare AI Contributor Guide

This file applies to the entire repository. It is the shared operating context for AI coding assistants and human contributors. More specific `AGENTS.md` files may be added in subdirectories when a component needs stricter local rules; the nearest file takes precedence.

## Mission and safety boundary

ResiliCare is an emergency-department triage and operations platform built with FastAPI, SQLAlchemy, and Supabase Postgres. It provides clinician decision support; it does not autonomously diagnose, prescribe, or make final treatment decisions.

Treat clinical behavior as safety-critical:

- Never weaken a safety ceiling, mandatory review, clinician-confirmation requirement, or escalation rule merely to simplify code or make a test pass.
- In ESI, a lower number means greater urgency. Combining recommendations with a safety ceiling must never reduce acuity; preserve the `min(regular_esi, ceiling)` invariant.
- Missing, conflicting, ambiguous, borderline, or worsening data must remain visible and must fail toward review, not silent reassurance.
- Keep generated assessments immutable and versioned. Record clinician acceptance or override separately, and require a reason for overrides.
- Financial coverage, facility availability, and referral routing may affect operational routing but must never change clinical acuity.
- Any new clinical threshold, rule, questionnaire, or claim requires an explicit source and clinical validation before production use. Mark unvalidated behavior clearly in code and documentation.
- Use synthetic or de-identified data in tests, examples, logs, and fixtures. Never add real patient data.

## Architecture and ownership

The primary application entrypoint is `src.main:app`, exposed under `/api/v1`.

- `src/api/routers/`: HTTP transport only: request handling, dependencies, response models, and status codes.
- `src/schemas/`: Pydantic request/response contracts and validation.
- `src/services/`: workflows, authorization-sensitive orchestration, and transaction boundaries.
- `src/db/repositories/`: reusable SQLAlchemy queries without HTTP concerns.
- `src/db/models/`: SQLAlchemy mappings.
- `src/core/`: deterministic, side-effect-free clinical calculations where practical.
- `src/workflows/`: waiting-room reassessment and operational surge behavior.
- `src/integrations/`: Supabase Auth/Storage and external formats such as FHIR.
- `src/config/`: versionable clinical and operational configuration.
- `supabase/migrations/`: authoritative database schema, constraints, grants, and RLS rules.
- `tests/`: unit, contract, schema, and API tests; `examples/` contains runnable demonstrations.

Keep dependencies flowing inward: routers call services, services call repositories/core logic, and repositories operate on models. Do not place business rules in routers or HTTP concerns in repositories/core modules. Prefer pure functions for clinical calculations so edge cases are easy to test.

There are some legacy modules under `src/api/routes/`, `src/adapters/`, and `src/data/`. Before extending one, confirm that the production router/service/repository path does not already own that behavior. Avoid creating a third implementation of the same workflow.

## Non-negotiable data and security rules

- FastAPI is the only application write path for clinical and financial tables. Do not grant browser roles direct table writes.
- Validate Supabase JWTs and bind callers to an application identity. Enforce role and hospital/tenant boundaries in every protected workflow and query.
- Never trust client-supplied hospital IDs, totals, role claims, audit fields, assessment versions, or calculated clinical values when the server can derive them.
- Never expose or commit `.env`, service-role keys, JWTs, connection strings, patient identifiers, or other secrets. Add only safe placeholders to `.env.example`.
- Preserve append-only semantics for vital observations, assessments, audit events, and other clinical history. Corrections should create linked/versioned records rather than rewrite history.
- Preserve audit provenance: actor, timestamp, source, resource, input/config version, rationale, and before/after meaning where applicable.
- Perform related state transitions atomically in one service transaction. Examples include doctor transfer, queue movement, assessment plus safety actions, invoice issue/supersession, and encounter closure.
- Calculate invoice and line-item totals on the backend. Issued invoices are superseded, not silently edited.
- Review tokens must be cryptographically random and stored only as hashes.
- Use parameterized SQL/SQLAlchemy expressions. Never construct SQL from untrusted input.

## Database changes

Treat the committed SQL migrations as the source of truth.

- Add migrations in numeric order and make the intended forward change explicit. Do not edit an already-deployed migration unless the task explicitly concerns unreleased migration cleanup.
- Keep SQLAlchemy models, constraints, indexes, grants/RLS, and schema-contract tests aligned with every schema change.
- Prefer database constraints for invariants that must hold regardless of application path, while retaining user-friendly validation in schemas/services.
- Use UTC-aware timestamps and database-generated UUIDs/defaults consistently with the existing schema.
- Do not run destructive database commands, reset shared environments, or apply migrations to a remote project without explicit user authorization.

## Python conventions

- Target Python 3.12+ and use modern type hints.
- Follow the existing Ruff configuration: 120-character maximum lines and the Python 3.12 target.
- Use async SQLAlchemy APIs for application database access; avoid blocking I/O in async request paths.
- Use Pydantic schemas at API boundaries. Do not accept or return unstructured dictionaries when a stable contract exists.
- Raise domain-appropriate errors in services and translate them consistently through the existing API error handling.
- Keep functions focused, names clinical-domain specific, and comments centered on safety reasoning or non-obvious invariants.
- Avoid broad exception handling, hidden fallbacks, mutable global state, and nondeterministic clinical scoring.
- Do not add a dependency when the standard library or an existing dependency handles the need cleanly. Update both `pyproject.toml` and `uv.lock` when dependencies genuinely change.

## Working method

Before editing:

1. Read `README.md`, `pyproject.toml`, and the files/tests closest to the requested behavior.
2. Check `git status` and preserve all unrelated or pre-existing changes; never discard user work.
3. Trace the complete path across schema, router, service, repository, model, migration, and tests as applicable.
4. State assumptions when requirements are clinically ambiguous or would materially change behavior. Do not invent a clinical policy.

While editing:

- Make the smallest coherent change that satisfies the request.
- Reuse existing abstractions and naming; avoid speculative refactors.
- Add or update tests with the implementation. Include normal, boundary, authorization, cross-hospital, missing-data, and failure cases as relevant.
- Keep API and schema changes backward compatible unless a breaking change is explicitly requested and documented.
- Update README/examples/configuration when setup, endpoints, workflows, or operator-visible behavior changes.

After editing:

1. Run the narrowest relevant tests first.
2. Run the full local verification commands when feasible.
3. Review the diff for secrets, PHI, accidental generated files, unsafe clinical behavior, and unrelated edits.
4. Report what changed, what was verified, and any remaining risk or external validation requirement. Never claim tests passed unless they were run successfully.

## Setup and verification

Use `uv` from the repository root:

```powershell
Copy-Item .env.example .env
uv sync
uv run fastapi dev
```

The local Supabase workflow, when required and explicitly safe for the selected environment, is:

```powershell
supabase start
supabase db reset
```

Run focused tests during development, then the full checks:

```powershell
uv run pytest -q tests/test_safety.py
uv run pytest -q
uv run ruff check src tests scripts
```

Some repository integration tests require a running local Supabase instance. If an external service is unavailable, run all unaffected checks and state exactly what could not be verified.

## Definition of done

A change is complete only when it respects the clinical and authorization invariants, follows the intended architecture, includes proportionate tests, leaves unrelated work untouched, contains no secrets or real patient data, and has verification results accurately reported. Production-facing clinical behavior also requires human clinical governance; passing automated tests alone is not approval for patient use.

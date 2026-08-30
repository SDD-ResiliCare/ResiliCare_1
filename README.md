# ResiliCare prototype

ResiliCare is a hackathon prototype of a safety-first emergency-department triage
support tool. It suggests an Emergency Severity Index (ESI) level with an explicit
confidence range, applies deterministic clinical safety ceilings that can escalate
but never autonomously downgrade acuity, explains every score in one or two lines,
re-assesses waiting patients as their vitals change, and records every clinician
override in an append-only audit ledger.

It also demonstrates operational layers around triage: a deterministic 3x surge
replay, a queue-length-triggered reduced-density "Combat Mode" display, simulated
scheme-aware alternate-facility routing, simulated hospital capability profiles, and
a ResiliCare-local visit history with a FHIR-shaped export.

This is an educational prototype, not a clinically validated medical device. Every
patient, facility, scheme, contact, and capability value in this repository is
synthetic. Reference ESI labels and local safety-rule inputs require review by
qualified emergency clinicians before any clinical evaluation.

## Table of contents

- Requirements
- Recommended optional dependencies
- Installation
- Configuration
- Troubleshooting
- FAQ
- Maintainers

## Requirements

The clinical scorer, the demo server, the example scripts, and the full test suite
run on the Python standard library alone. There are no required third-party
packages, no build step, no database, and no network access.

- Python 3.10 or newer. Developed and verified on CPython 3.14.6 (Windows 11).
- A modern browser for the demo UI (the interface uses `<dialog>` and `fetch`).

Optional, and needed only for the experimental Task 12 audio pipeline, are the
packages listed under "Recommended optional dependencies" below.

## Recommended optional dependencies

These enhance the project but are not needed to run, demo, or test it. This is the
Drupal template's "Recommended modules" slot, adapted for a Python project.

- `requirements_nlp.txt` (torch, torchaudio, transformers, librosa, soundfile,
  spaCy) enables the experimental Task 12 audio intake — Silero voice-activity
  detection, a Librosa acoustic-distress heuristic, and Whisper speech-to-text.
  Without them, `resilicare.nlp_kiosk` still imports and its text pipeline still
  works; only the audio methods raise a clear error.
- The `en_core_web_sm` spaCy model enables name extraction in the kiosk identity
  step. Without it, identity binding falls back to an ephemeral `Trauma-Unknown-…`
  alias, which is the intended default behaviour anyway.

**These pins are not verified on Python 3.14.** `torch==2.1.2` predates Python 3.14
wheel support, so `pip install -r requirements_nlp.txt` is expected to fail on this
project's own interpreter until the file is re-pinned or run under a separate
Python 3.10–3.12 environment. Nothing else in the repository depends on this.

## Installation

All commands are run from the project root. PowerShell examples are given first
because the project was developed on Windows; the bash equivalents follow.

### 1. Get the code

```powershell
git clone https://github.com/SDD-ResiliCare/ResiliCare_1.git
cd ResiliCare_1
```

### 2. Put `src` on the Python path

There is no packaging step. Every entry point expects `src` on `PYTHONPATH`.

```powershell
$env:PYTHONPATH = "src"
```

```bash
export PYTHONPATH=src
```

Set this once per terminal session. Every command below assumes it is set.

### 3. Verify the installation by running the test suite

```powershell
python -m unittest discover -s tests -v
```

This runs 124 tests across every layer and should end in `OK`. It requires no
optional dependencies. If it passes, the prototype is correctly installed.

### 4. Run the browser demo

```powershell
python demo/audit_server.py
```

Then open `http://127.0.0.1:8000`. The server accepts `--host`, `--port`, and
`--log` (audit-ledger path, default `data/audit_log.jsonl`); it binds to localhost
only. See "Configuration" for what to click through once it is open.

### 5. Run the command-line examples (optional)

Each script prints one layer's behaviour and exits.

```powershell
python examples/run_safety_layer.py
python examples/run_confidence_layer.py
python examples/run_missingness_layer.py
python examples/run_waiting_room.py
python examples/run_surge_simulation.py
```

`run_surge_simulation.py` is the headless proof of the Task 10 rubric requirement
and prints the quiet-versus-surge comparison directly:

```
QUIET_1X: 7 arrivals / 15 min, queue=7, Combat Mode=OFF
SURGE_3X: 21 arrivals / 15 min, queue=21, Combat Mode=ON
Deterioration replay: Q-001 (PT-018) rank 18 -> 9
```

### 6. Install the optional audio extras (only if demoing Task 12 audio)

```powershell
pip install -r requirements_nlp.txt
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz
```

Expect this to fail on Python 3.14 (see "Recommended optional dependencies"). The
demo's voice-intake tab works regardless, using manual transcript entry.

## Configuration

### Demo walkthrough

Once `python demo/audit_server.py` is running at `http://127.0.0.1:8000`:

1. **Patient queue** opens on a 7-encounter quiet shift in the normal detailed
   layout. Each card shows the ESI badge with confidence, the one-to-two-line
   explanation, any mandatory safety workup, hospital operational guidance, and
   simulated financial routing.
2. **Override ESI** on any card requires a clinician ID, a different ESI level, a
   structured reason category, and free-text rationale. The server, not the
   browser, looks up the canonical AI output before appending the event.
3. **Run 3x surge** replays 21 arrivals into the same 15-minute window, crosses the
   queue-length threshold of 20, and automatically activates Combat Mode. **Declare
   surge manually** triggers the same display for drills; **Reset quiet shift**
   returns to 7 encounters.
4. **Open & acknowledge** on a Combat Mode card requires a clinician ID (enter it in
   the surge control bar first) and restores the full detail view.
5. **Hospital profile · simulated** swaps between the urban trauma centre and the
   rural clinic live. `Q-007` is the clearest demo: the ESI badge stays identical
   while the operational recommendation changes to stabilise-and-transfer.
6. **Open details** shows ResiliCare-local visit history and offers **Export as
   FHIR-shaped bundle**. `PT-016` / `RC-P-016` is the seeded returning patient.
7. **Audit log** is the append-only viewer for overrides and Combat Mode
   acknowledgements.
8. **Voice intake (experimental)** provides the Task 12 manual transcript fallback.

### Tunable configuration files

Prototype thresholds are deliberately isolated in versioned JSON rather than
hard-coded, so a clinician can review and replace them:

- `src/resilicare/vital_thresholds.json` — age-calibrated vital reference bands.
- `src/resilicare/confidence_config.json` — confidence thresholds and penalties.
- `src/resilicare/missingness_config.json` — history/vitals blend weights.
- `src/resilicare/waiting_room_config.json` — reassessment ceilings per ESI level.
- `src/resilicare/ambiguous_presentations.json` — differential pathway table.
- `src/resilicare/facilities.json` — simulated scheme-to-facility routing table.
- `src/resilicare/hospital_profiles.json` — simulated hospital capability profiles.

Runtime state is written to `data/audit_log.jsonl` and
`data/resilicare_history_runtime.json`; both are gitignored. The committed
`data/resilicare_history_seed.json` is copied to the runtime file on first run.

### Task 2: safety override and clinician confirmation

`src/resilicare/safety.py` evaluates every deterministic safety rule, chooses the
most urgent matched ceiling, and never autonomously lowers acuity. A normal scorer
can later be combined through `apply_safety_ceiling()`.

The layer returns the provisional ESI ceiling, uncertainty range, all matched rule
IDs, plain-language rationales, review priority, missing/conflicting information,
and a mandatory clinician-confirmation flag. Provisional and clinician decisions can
be appended to JSONL logs.

### Task 3: age-calibrated vital thresholds

`src/resilicare/vital_thresholds.json` is a versioned, auditable lookup table. It
covers neonate, infant, toddler, child, adolescent, adult, and geriatric patients;
pediatric child and adolescent brackets use finer source-age anchors to avoid
another overly broad cutoff.

`normalize_vitals()` converts HR, RR, SpO2, systolic BP, and temperature into a
signed, dimensionless distance outside the selected reference band. Values inside
the band are zero; negative values are below it and positive values are above it.
Diastolic BP is still checked for missingness by the intake safety layer, but is not
normalized because the selected early warning references use systolic BP.

When `age_years` is present, `evaluate_safety_rules()` automatically attaches these
normalized signals and uses their LOW/HIGH states for the existing clinician-review
rule. The geriatric profile deliberately reuses the adult NEWS2 numerical band and
marks baseline context as required; no universal older-adult ranges were invented.

Reference bands are sourced from the Royal Children's Hospital Melbourne pediatric
table, Queensland Health's Primary Clinical Care Manual (pediatric temperature and
SpO2), and the Royal College of Physicians NEWS2 zero-score bands for adults. They
are operational screening bands, not proof that a patient is stable and not a
diagnosis.

### Task 4: confidence and uncertainty on every score

Application-facing code should call `score_with_confidence()` rather than display
the integer returned by the low-level safety-ceiling helper. Every result contains
an `esi_set`, confidence score and label, deferral decision, uncertainty reasons,
and a ready-to-render `badge`, such as:

- `ESI 2 — High confidence`
- `ESI 2-3 — Escalate for senior nurse review`

With a future classifier, the function requires the complete ESI 1-5 probability
vector. A low top probability or small top-two gap produces a contiguous ordinal
set. Without a classifier it uses a clearly identified evidence-completeness
heuristic — never invented class probabilities. Zero history, missing vitals,
ambiguity, conflicts, and age-adjusted vital deviations reduce the score and trigger
deferral; set widening is biased toward the higher-acuity (smaller ESI) side and can
never violate the Task 2 safety ceiling.

Thresholds and penalties live in `src/resilicare/confidence_config.json`. This is a
transparent selective-deferral prototype inspired by conformal prediction, but it is
not labelled as calibrated conformal prediction and `coverage_guarantee` remains
false. A real coverage claim requires a trained probabilistic model, an independent
calibration split, and prospective validation.

### Task 5: missingness-aware zero-history handling

`has_prior_history` is required to be a real boolean — strings, integers, and absent
values are rejected instead of silently interpreting them. `prepare_history_context()`
creates a separate scorer view while preserving the raw patient record for audit:

- history available: history-derived numeric features are retained;
- no history on file: supplied/stale history-derived values are forced to `0.0`, an
  explicit missingness indicator is set, and no guessed history value is imputed;
- the history/vitals blend changes from `75% observed vitals + 25% history` to
  `100% observed vitals + 0% history` for that record.

The zero-history confidence output includes the visible notice: `No prior history on
file — score based on presenting vitals only.` These prototype blend weights are
isolated in `src/resilicare/missingness_config.json` and require clinician-reviewed
calibration later.

### Task 6: waiting-room reassessment loop

`tick_waiting_room()` evaluates every waiting entry using elapsed time and manually
re-entered vitals only. The update channel rejects non-vital fields, so there is no
microphone, acoustic, camera, or other sensor dependency. It:

- flags ESI-1 as ineligible for the ordinary waiting queue;
- triggers when the configured reassessment interval is exceeded;
- compares repeat vitals using Task 3 age-normalized deviations;
- re-runs Tasks 2, 4, and 5, permits acuity escalation but never automated
  downgrading;
- sorts escalated/flagged patients forward and emits queue ranks;
- writes `waiting_room_retriage` and clinician `waiting_room_reassessment_completed`
  events to the same timestamped JSONL audit stream used by the other layers.

The demo intervals (`0/10/30/60/120` minutes for ESI 1-5) are deliberately labelled
local prototype reassessment ceilings in `waiting_room_config.json`. ESI itself does
not prescribe time-to-provider or reassessment intervals, so these are not
represented as a "safe wait" guarantee and must be replaced by an approved local ED
policy before clinical evaluation.

### Task 7: clinician override capture and append-only audit viewer

Every displayed AI suggestion has an Override button. The modal requires clinician
ID, a different ESI level, a structured reason category, and a free-text clinical
rationale. The server — not the browser — looks up the canonical AI output and
appends its score set, point estimate, confidence, clinician choice, direction,
reason, UTC timestamp, and event UUID to `data/audit_log.jsonl`.

The demo exposes only insert and read operations; HTTP PUT, PATCH, and DELETE return
`405`. Concurrent in-process appends are locked, and reserved audit fields cannot be
replaced by payload data. The Audit log tab provides the requested viewer. This is
honestly an application-level append-only ledger, not a cryptographically immutable
or OS-tamper-proof store.

Until the regular scorer is implemented, the screen clearly labels its synthetic
reference-label scores as a UI stub; no model-accuracy claim is made from them.

The server binds to localhost by default and has no authentication; it is a
hackathon demo, not a production clinical deployment. Clinician IDs are captured as
entered, not identity-verified.

### Task 8: one-to-two-line explanation per score

Every `score_with_confidence()` result includes one or two prioritized
`explanation_lines`, a combined `explanation_text`, and the exact
`explanation_rule_ids`. Explanations identify the displayed ESI/set and the most
decision-relevant patient-specific basis — for example, the observed SpO2 value and
its selected age-adjusted reference floor. Immediate/high-risk rules outrank vital
deviations, which outrank missing, ambiguous, conflicting, and zero-history
uncertainty.

The demo renders this text directly below every score badge and also shows it in the
Override modal. Override audit snapshots retain the explanation seen by the
clinician. Explanations are rule templates because no trained classifier exists yet;
SHAP has deliberately not been installed or simulated. If a tree classifier is later
built, SHAP attribution needs separate validation and wiring at that point.

### Task 9: rule-based differential table for ambiguous presentations

`ambiguous_presentations.json` contains three small, sourced pathways: acute chest
discomfort, syncope/near-syncope, and acute lower-abdominal/pelvic pain. Matching
uses bounded phrases from the chief complaint only (avoiding negated background-text
false positives), evaluates every matched pathway, and returns:

- non-diagnostic differential considerations;
- a mandatory-safety-workup flag and pathway actions;
- the matched phrase, pathway ID, source links, and maximum allowed ESI.

Each match adds an escalation-only ESI-3 ceiling, so a regular ESI 4/5 suggestion
becomes ESI 3, while an existing ESI 1/2 is never downgraded. PT-004 (`Central chest
burning`) is the primary demo: it visibly retains ACS and other dangerous
alternatives plus an ECG/cardiac-troponin pathway even though indigestion remains
plausible. The mandatory flag is independent of the final ESI.

These entries are clinician prompts, not diagnoses or autonomous orders. Required
actions must be implemented through an approved local ED pathway. The chest-pain
entry follows the 2021 AHA/ACC chest-pain guidance; syncope follows ACC/AHA/HRS
guidance; pregnancy-relevant pelvic pain uses ACOG ectopic-pregnancy guidance. A GNN
is deliberately omitted because no validated symptom-diagnosis graph or suitable
labels exist in this prototype.

### Task 10: deterministic 3x surge replay

`replay_arrivals()` compares 7 baseline arrivals with exactly 21 arrivals in the same
15-minute window. Replayed records receive unique queue encounter IDs while
preserving their synthetic source patient ID. The 21-patient run crosses the Combat
Mode threshold of 20. Its deterioration case begins as a low-acuity encounter and
demonstrably moves from queue rank 18 to 9 after age-normalized vital worsening and
the existing escalation-only re-triage path; it is no longer an already-ESI-1
patient.

Run `python examples/run_surge_simulation.py`. Automated tests verify the exact 3x
rate, unique encounter IDs, threshold transition, forward re-sort, and unchanged
scoring behavior.

### Task 11: India jurisdiction and compliance note

[`compliance.md`](compliance.md) states the India assumption without claiming legal
certification. It uses the DPDP Act's actual `certain legitimate use` terminology for
a medical emergency, records the phased commencement date for sections 3–17,
separates ABDM consent-driven sharing from local care, and adopts a three-year
prototype retention baseline subject to longer hospital/state/legal-hold
requirements. It removes the unsupported blanket seven-year retention,
instant-erasure, and future camera/microphone compliance claims.

### Task 12: multilingual voice intake — text pipeline done, audio still experimental

`nlp_kiosk.py` is split into two parts. The **text pipeline** (negation-aware
red-flag detection, complaint-to-differential mapping, identity fallback —
`process_kiosk_text()` and friends) needs only the standard library, is unit-tested
(`tests/test_nlp_kiosk.py`), and is wired into the existing Task 9 differential
table: `extract_chief_complaint()` returns the *exact* trigger-phrase text
`ambiguous_presentations.json` expects, so a kiosk transcript feeds
`match_ambiguous_presentations()` exactly as if the complaint had been typed. Keyword
lists cover common English and Hindi (romanized + Devanagari) phrasing. The demo
server exposes this as `/api/kiosk/text` (a **preview only** — it does not score a
real patient, touch the queue, or write to the audit log) and the demo UI's "Voice
intake (experimental)" tab gives clinicians a real, working manual-transcript
fallback that needs no microphone or ASR at all.

The **audio pipeline** (`TriageKioskAnalyzer`: Silero VAD -> Librosa
acoustic-distress heuristic -> Whisper ASR) is still an **experimental spike, not
demo-ready**. It is not imported by the clinical scoring path or by the demo server's
normal patient flow. Its heavy dependencies are imported lazily, so the module is
importable and its text stages testable without them, but they remain optional,
unpinned for Python 3.14, and unverified in this project's environment
(`/api/kiosk/status` reports this live). The repository still does not contain the
required 2–3 prerecorded multilingual audio fixtures — recording those is the one
piece intentionally left for the team. Place them in `examples/` (the notebook
expects `examples/test.wav`) and drive them through
`TriageKioskAnalyzer().process_kiosk_interaction(path)` or
`examples/test_nlp_pipeline.ipynb`. Confidence gating remains a text-shape heuristic
(length plus degenerate-repetition check), not a calibrated ASR confidence score; the
HuggingFace ASR pipeline used here does not return per-token confidence by default.

Do not present the audio half of Task 12 as demo-ready or claim it is complete until
team-recorded clips exist and the ASR/VAD environment has been verified to actually
install and run.

### Task 13: simulated scheme-aware alternate-facility routing

Every synthetic patient carries one of four coverage labels: `PM-JAY`, `ESIC`,
`Private Insurer X`, or `Self-pay`. `facilities.json` is a deliberately small, static
table of four fictional nearby facilities, simulated distances, accepted schemes,
cashless flags, and room-rent caps. The JSON, CSV, and XLSX datasets contain the same
patient-to-scheme mapping.

`suggest_scheme_route()` is downstream of triage and cannot change the ESI score or
queue priority. It shows an alternate fast-track/outpatient option only for
clinician-confirmed ESI 4/5 cases. Routing is withheld if there is a hard safety
override, mandatory safety workup, worsening vitals, or unresolved ESI uncertainty.
The server derives the score and scheme from its canonical patient record rather than
accepting them from the browser.

The demo labels every scheme and route as simulated and displays: `Simulated scheme
data — a live NHCX integration would replace this lookup table in production.` It
does **not** call NHCX, verify beneficiary eligibility, confirm cashless
authorization, check live capacity, or perform a transfer. The fictional values
demonstrate the workflow and financial-routing differentiator only.

Production integration would replace the table with payer and facility verification.
NHCX is the Government of India's standardized health-claims exchange layer;
scheme-specific eligibility and benefits still require authoritative payer workflows.
Background sources: [ABDM NHCX FAQ](https://abdm.gov.in/DHIS/faqs),
[ABDM FAQ](https://abdm.gov.in/FAQ), and
[ESIC benefits](https://www.esic.gov.in/Publications/ESIAct1948Amendedupto010610.htm).

### Task 14: queue-triggered Combat Mode

The local demo starts with a 7-encounter quiet queue in the normal detailed layout.
Running the Task-10 3x replay produces 21 encounters in the same 15-minute window;
when queue length reaches the agreed threshold of **20**, the server automatically
activates Combat Mode. A separate manual declaration control is available for drills,
but keystroke monitoring is not used.

Each Combat Mode card contains only the queue/patient ID, one prioritized safety
badge with its reason, and `Open & acknowledge`. A clinician ID is required before
that action can open the normal full-detail view. The append-only event captures
clinician ID, UTC timestamp, patient ID, current AI score/set/confidence, surge
trigger and queue length, and the exact safety badge shown. Full detail restores
vitals, complaint, age, history/missingness, ESI confidence, explanation, workup
flags, scheme-routing context, and override controls.

Combat Mode calls the same scorer and does not change ESI, confidence, queue rank,
safety rules, or routing. It changes information density only. The design framing is
Wickens' multiple-resource model for overload-aware interface design and Sweller's
cognitive-load work; this prototype does not claim those papers clinically validate
this particular UI. Sources: [Wickens, 2008](https://doi.org/10.1518/001872008X288394)
and [Sweller, 1988](https://doi.org/10.1207/s15516709cog1202_4).

### Task 16: ResiliCare-local visit history and FHIR-shaped export

The prototype separates a stable `Patient` identity (`RC-P-016`) from individual
triage `Encounter` identifiers (`PT-016`, or `Q-005` during queue replay), so one
synthetic patient can have multiple ResiliCare visits. The committed
`data/resilicare_history_seed.json` contains a clearly synthetic earlier visit for
the returning-patient demo. On first run it is copied to the ignored
`data/resilicare_history_runtime.json`; later demo visits and clinician overrides
update that local runtime copy without rewriting the seed.

Opening a patient's full details shows date/time, complaint, key vitals, suggested
ESI and confidence, final clinician decision, and safety flags under the exact
boundary label **"History from previous ResiliCare visits only."** This is not
presented as complete hospital/EHR history. PT-016/RC-P-016 is the seeded
returning-patient path; other patients honestly show that no previous ResiliCare
visit was found.

`Export as FHIR-shaped bundle` downloads local JSON with `Patient`, `Encounter`, and
vital-sign `Observation`-like resources inside a `Bundle`-like collection. The file
and UI explicitly state that this is a **FHIR-shaped prototype, not a
validated/conformant FHIR implementation**, and it is not transmitted to ABDM or an
EHR. The shape follows the roles described by the official HL7 FHIR R4 documentation
for [Patient](https://hl7.org/fhir/R4/patient.html),
[Encounter](https://hl7.org/fhir/R4/encounter.html),
[Observation](https://hl7.org/fhir/R4/observation.html), and
[Bundle](https://hl7.org/fhir/R4/bundle.html).

Production would replace local JSON with an authenticated, encrypted,
access-controlled database and use authorized EHR/ABDM/FHIR integrations where
available. Conformance profiles, terminology validation, consent/authorization,
identity matching, transport security, and audit governance are future production
work — not claims made by this hackathon prototype.

### Task 17: simulated hospital capability profiles

Hospital capability and operational assumptions live in
`src/resilicare/hospital_profiles.json`, separate from clinical scoring. Two
fictional profiles are included:

- `urban_trauma_center`: 36 ED beds, 24 ICU beds, and simulated trauma, cardiology,
  pediatrics, surgery, neurology and other specialty coverage;
- `rural_clinic`: four ED beds, eight inpatient beds, no ICU, general medicine only,
  and a transfer-first pathway when a required specialty or critical-care capability
  is unavailable.

The profile layer returns only operational information: unavailable-specialty and
capacity alerts, whether clinician-led transfer coordination is recommended, a
suggested local care/stabilization area, and a fictional escalation-contact
identifier. It receives the already-computed ESI as an input and cannot change ESI,
its uncertainty/confidence, safety rules, or queue rank.

`Q-007` (the abdominal-pain encounter sourced from PT-009) is the clearest quiet-shift
demo: its ESI badge remains identical, while the urban profile recommends its local
monitored/surgical pathway and the rural profile highlights unavailable general
surgery, local capacity pressure, and stabilize-and-transfer coordination. Combat
Mode remains clinically and visually unchanged; the full operational assessment is
restored after `Open & acknowledge`.

All profile values and contacts are synthetic static configuration — not live bed
availability, staffing, referral acceptance, or a completed transfer. Production must
use authenticated, hospital-approved configuration plus real-time
capability/occupancy and clinician-confirmed receiving-facility acceptance. The
application must never delay stabilization or down-triage a patient because a
capability is absent.

## Troubleshooting

**`ModuleNotFoundError: No module named 'resilicare'`** — `PYTHONPATH` is not set for
the current terminal session. Re-run `$env:PYTHONPATH = "src"` (PowerShell) or
`export PYTHONPATH=src` (bash) from the project root. Opening a new terminal clears
it.

**`OSError: [WinError 10048]` or "address already in use" on startup** — port 8000 is
taken, often by an earlier demo server that is still running. Start on another port
with `python demo/audit_server.py --port 8080`.

**The demo shows no previous visits for a patient** — this is correct behaviour for
every patient except the seeded returning patient `PT-016` / `RC-P-016`. To reset
history entirely, delete `data/resilicare_history_runtime.json`; it is regenerated
from the committed seed on next start.

**`pip install -r requirements_nlp.txt` fails** — expected on Python 3.14; see
"Recommended optional dependencies". Nothing except the Task 12 audio pipeline needs
it, and the voice-intake tab works without it.

**`RuntimeError: Task 12 audio pipeline requires 'torch' …`** — an audio method was
called without the optional extras installed. Use `process_kiosk_text()` or the demo's
manual transcript box instead.

**Combat Mode does not activate** — it triggers at a queue length of 20 or more. The
quiet shift is 7 encounters; select `Run 3x surge` first, or use `Declare surge
manually` to force the display below threshold.

## FAQ

**Is this safe to use on real patients?**
No. It is an educational hackathon prototype, not a clinically validated medical
device, and it has no authentication, encryption, or access control. Every safety
threshold in it is a prototype default awaiting clinician review.

**Can the AI lower a patient's acuity on its own?**
No. Every automated path is escalation-only. Safety ceilings, differential pathways,
and waiting-room re-triage can move a patient to a more urgent ESI but never to a
less urgent one; only a clinician can downgrade, and that is recorded as an override.

**Is the audit log tamper-proof?**
It is an application-level append-only ledger — insert and read only, with PUT,
PATCH, and DELETE returning `405`. It is not cryptographically immutable and not
protected against an operator with filesystem access.

**Is the FHIR export real FHIR? Does it talk to ABDM?**
No to both. It is FHIR-*shaped* prototype JSON, downloaded locally, never
transmitted, and not conformance-validated.

**Does the routing feature check real insurance eligibility?**
No. Schemes, facilities, distances, and room-rent caps are all fictional static
lookup data. There is no NHCX call, eligibility check, or cashless authorization.

**Why is there no trained model?**
No validated labelled dataset exists for this prototype, so inventing class
probabilities would misrepresent confidence. The confidence layer uses a clearly
identified evidence-completeness heuristic instead, and explanations are rule
templates rather than SHAP attributions.

**Why is a GNN / live microphone intake not implemented?**
Both were deliberately scoped out. A GNN needs a labelled symptom-diagnosis graph
that does not exist here; live-microphone intake fails unpredictably in noisy demo
venues, so Task 12 is built around pre-recorded clips and a manual fallback.

## Maintainers

- ResiliCare team (Samosa Driven Development) —
  [github.com/SDD-ResiliCare](https://github.com/SDD-ResiliCare)

Replace this section with individual maintainer names and handles before publishing.

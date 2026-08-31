# ResiliCare Feature/Task Breakdown

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

`nlp/` is split into two parts. The **text pipeline** (negation-aware
red-flag detection, complaint-to-differential mapping, identity fallback —
`process_kiosk_text()` and friends) needs only the standard library, is unit-tested
(`tests/test_nlp/`), and is wired into the existing Task 9 differential
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

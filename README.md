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
python demo/backend/audit_server.py
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

Once `python demo/backend/audit_server.py` is running at `http://127.0.0.1:8000`:

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

For a detailed breakdown of the clinical and operational tasks implemented in this prototype (Tasks 2 through 17), please see [TASKS.md](TASKS.md).


## Troubleshooting

**`ModuleNotFoundError: No module named 'resilicare'`** — `PYTHONPATH` is not set for
the current terminal session. Re-run `$env:PYTHONPATH = "src"` (PowerShell) or
`export PYTHONPATH=src` (bash) from the project root. Opening a new terminal clears
it.

**`OSError: [WinError 10048]` or "address already in use" on startup** — port 8000 is
taken, often by an earlier demo server that is still running. Start on another port
with `python demo/backend/audit_server.py --port 8080`.

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

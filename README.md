# ResiliCare prototype

## Task 4: confidence and uncertainty on every score

Application-facing code should call `score_with_confidence()` rather than display the integer
returned by the low-level safety-ceiling helper. Every result contains an `esi_set`, confidence
score and label, deferral decision, uncertainty reasons, and a ready-to-render `badge`, such as:

- `ESI 2 — High confidence`
- `ESI 2-3 — Escalate for senior nurse review`

With a future classifier, the function requires the complete ESI 1-5 probability vector. A low
top probability or small top-two gap produces a contiguous ordinal set. Without a classifier it
uses a clearly identified evidence-completeness heuristic—never invented class probabilities.
Zero history, missing vitals, ambiguity, conflicts, and age-adjusted vital deviations reduce the
score and trigger deferral; set widening is biased toward the higher-acuity (smaller ESI) side and
can never violate the Task 2 safety ceiling.

Thresholds and penalties live in `src/resilicare/confidence_config.json`. This is a transparent
selective-deferral prototype inspired by conformal prediction, but it is not labelled as calibrated
conformal prediction and `coverage_guarantee` remains false. A real coverage claim requires a
trained probabilistic model, an independent calibration split, and prospective validation.

## Task 3: age-calibrated vital thresholds

`src/resilicare/vital_thresholds.json` is a versioned, auditable lookup table. It covers
neonate, infant, toddler, child, adolescent, adult, and geriatric patients; pediatric child
and adolescent brackets use finer source-age anchors to avoid another overly broad cutoff.

`normalize_vitals()` converts HR, RR, SpO2, systolic BP, and temperature into a signed,
dimensionless distance outside the selected reference band. Values inside the band are zero;
negative values are below it and positive values are above it. Diastolic BP is still checked
for missingness by the intake safety layer, but is not normalized because the selected early
warning references use systolic BP.

When `age_years` is present, `evaluate_safety_rules()` automatically attaches these normalized
signals and uses their LOW/HIGH states for the existing clinician-review rule. The geriatric
profile deliberately reuses the adult NEWS2 numerical band and marks baseline context as
required; no universal older-adult ranges were invented.

Reference bands are sourced from the Royal Children's Hospital Melbourne pediatric table,
Queensland Health's Primary Clinical Care Manual (pediatric temperature/SpO2), and the Royal
College of Physicians NEWS2 zero-score bands for adults. They are operational screening bands,
not proof that a patient is stable and not a diagnosis.

## Task 2: safety override and clinician confirmation

`src/resilicare/safety.py` evaluates every deterministic safety rule, chooses the most urgent
matched ceiling, and never autonomously lowers acuity. A normal scorer can later be combined
through `apply_safety_ceiling()`.

The layer returns the provisional ESI ceiling, uncertainty range, all matched rule IDs,
plain-language rationales, review priority, missing/conflicting information, and a mandatory
clinician-confirmation flag. Provisional and clinician decisions can be appended to JSONL logs.

Run tests from the project root:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Run the dataset example:

```powershell
$env:PYTHONPATH = "src"
python examples/run_safety_layer.py
python examples/run_confidence_layer.py
```

This is an educational prototype, not a clinically validated medical device. Reference ESI
labels and local safety-rule inputs require review by qualified emergency clinicians.

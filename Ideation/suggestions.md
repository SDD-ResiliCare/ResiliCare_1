# ResiliCare — Upgrade Recommendations by Task

Tags: **Necessary** (rubric-required, real safety gap, or a glaring internal contradiction — fix before demo day) / **Good for win** (cheap, high credibility, differentiates you) / **Okayish** (fine polish, low urgency) / **If ample time** (real but marginal, only if everything else is done) / **No benefit** (skip — cost/risk exceeds any demo payoff).

---

### Task 2 — Safety override & clinician confirmation
- **Necessary:** Define a fallback for confirmation timeout/failure (network drop, nurse occupied). A system that blocks finalization until human ack needs an explicit answer for "what happens if the ack never comes" — the brief's own D1 (infrastructure unreliability) applies here too. Default should be "stays at the safety-ceiling level, flagged for senior review," never silently pass through.
- **Necessary:** Confirm rule-conflict resolution — if two safety rules fire simultaneously with different `maximum_allowed_esi` values, verify the code takes the *more urgent* (lower) number, not the first-matched or last-matched rule. Write one test case that exercises this.
- **Good for win:** Require the clinician ID to carry a role tag (RN/MD) rather than any string — cheap, and it's the kind of detail that reads as "actually thought about accountability."
- **Okayish:** Log which specific rule triggered the ceiling alongside the clinician ID, if not already captured in the audit snapshot.
- **If ample time:** Two-person co-sign for the most extreme overrides (mirrors real hospital double-check protocols for high-risk actions).
- **No benefit:** Cryptographic signing of the confirmation payload — real hospitals don't do this for triage overrides either; it's solving a problem you don't have.

### Task 3 — Age-calibrated vital thresholds
- **Necessary:** Verify your bracket boundaries and normal ranges against a real published pediatric reference (e.g., PALS/APLS age-banded vital sign tables) rather than invented numbers — this is the specific claim most likely to get a direct "where did this number come from" question, given it's the brief's headline example (fever of 38.5°C in a toddler vs. a 75-year-old).
- **Good for win:** Smooth the bracket edges (interpolate rather than a hard cliff at exact birthday boundaries) — a 17-year, 364-day-old patient shouldn't jump to a completely different threshold table than a patient one day older.
- **Okayish:** Weight-based (not just age-based) pediatric ranges for the toddler/infant brackets specifically, where weight varies more than age-implies.
- **If ample time:** Sex-based threshold variation for the handful of vitals where it matters clinically.
- **No benefit:** Full continuous percentile/growth-chart-style modeling — massive overkill next to a bracketed deviation score that already does the job.

### Task 4 — Confidence and uncertainty
- **Necessary:** Confirm a Low-confidence result actually changes system behavior (widens the recommended range / triggers "escalate for review"), not just a passive label a nurse could ignore. The brief is explicit that bias-toward-escalation-under-uncertainty must be *demonstrated*, not just displayed.
- **Good for win:** Feed the specific penalty reasons (which deductions fired) into Task 8's explanation text, so "Low confidence" always comes with a stated reason, not a bare label.
- **Okayish:** Make penalty weights configurable rather than hardcoded, for demo flexibility.
- **If ample time:** Check whether "Low confidence" cases in your synthetic dataset actually correspond to the ones you, as the record's author, consider genuinely ambiguous — a informal calibration sanity check.
- **No benefit:** Swapping this for a trained ML uncertainty estimator at this stage — you deliberately chose transparent penalties over black-box probabilities for explainability; reversing that now is rework for the same functional outcome, and reintroduces exactly the opacity you designed around.

### Task 5 — Missingness-aware handling
- **Necessary:** Same escalation tie-in as Task 4 — confirm depressed confidence from missingness actually blocks low-acuity auto-routing in practice (the doc says it should; verify with a test case, since this is one of your best-aligned features to the brief).
- **Good for win:** A distinct, louder badge for the worst case — no history *and* missing vitals simultaneously — since that's genuine zero-information territory and deserves to look different from either alone.
- **Okayish:** Per-vital (not just blanket) missingness tracking.
- **If ample time:** A disclosed "estimated, not measured" fallback value — use cautiously, since it cuts against your own stated philosophy of treating missingness as a feature rather than imputing.
- **No benefit:** A real imputation model (MICE etc.) — directly contradicts your own design principle for no demo payoff.

### Task 6 — Waiting-room reassessment loop
- **Necessary:** Nothing missing here for correctness — but explicitly document in your pitch that wait-time alone never changes ESI (only new vitals do), and name-check "avoiding triage drift" as the reason. This is a genuine strength; make sure it doesn't get lost or accidentally "fixed" into auto-escalation later.
- **Good for win:** Tag decay-triggered flags (`active_time_alert`) distinctly from vitals-triggered escalations in the audit log — lets a nurse (and a judge) see at a glance that the system caught a wait-time breach without a new sensor reading.
- **Okayish:** A visible countdown-to-reassessment per patient in the queue UI.
- **If ample time:** Continuous decay-curve modeling instead of a discrete threshold check — more sophisticated, but the threshold already produces the correct safety behavior for a demo.
- **No benefit:** True 60-second-tick full-queue resimulation — same functional outcome as your current check, more compute, no visible demo difference.

### Task 7 — Audit log
- **Necessary:** Nothing blocking — this is one of your strongest-built features (the exact-millisecond screen-state snapshot is a genuinely good, non-obvious detail; make sure it's in your pitch).
- **Good for win:** A lightweight hash-chain (each entry stores a hash of the previous entry) — roughly 10-15 lines, and it makes your "immutable ledger" claim technically true (tamper-evident) rather than just structurally true (append-only).
- **Good for win:** A redacted "compliance view" export formatted to match your Task 11 jurisdiction write-up — ties two already-built features together for the pitch.
- **Okayish:** Retention/purge enforcement matching your stated policy (unlikely to be visibly testable in a demo, but worth having for the write-up).
- **If ample time:** Search/filter on the log viewer.
- **No benefit:** Distributed-consensus/replicated ledger infrastructure — solving a scale problem this prototype doesn't have.

### Task 8 — One-to-two-line explanations
- **Necessary:** Verify explanation text still appears (even truncated to a clause) when Combat Mode (Task 14) trims the payload. If Combat Mode drops it entirely, you've removed 2-second explainability exactly during the surge scenario where it matters most — that's a direct contradiction with D3's own premise.
- **Necessary:** Confirm confidence-penalty reasons (Task 4) actually surface here, not just vital+differential-rule text — a "Low confidence" badge with no stated cause fails the "2-second verification" goal.
- **Okayish:** Localize explanation text to match the intake language (Hindi in, Hindi explanation out) — nice symmetry with Task 12, not essential.
- **If ample time:** Configurable verbosity (1-line vs. 3-line).
- **No benefit:** LLM-generated free-text explanations instead of templated — reintroduces hallucination risk into a system that specifically avoided black-box ML elsewhere (Task 4) for explainability reasons. Contradicts your own design philosophy for zero benefit.

### Task 9 — Rule-based differential table
- **Necessary:** Confirm `ambiguous_presentations.json` actually contains an entry matching the "ambiguous presentation" record in your required 15-20-patient test set — an easy thing to silently miss if the table and the dataset were authored separately.
- **Good for win:** Wire the table's "required safety actions" into Task 7's override-reason options as pre-filled choices when a nurse overrides a differential-flagged case — connects three already-built features for a good demo narrative at near-zero extra cost.
- **Okayish:** Age/sex-specific differential variants (e.g., abdominal pain differentials shift by age and sex) — clinically accurate, moderate effort.
- **If ample time:** Expand from a couple of example complaints to 10-15 categories for demo breadth.
- **No benefit:** Runtime LLM-generated differentials instead of the curated static table — defeats the entire point of a vetted safety-net list, for a feature whose value *is* that it's deterministic and reviewed.

### Task 10 — Deterministic 3x surge replay
- **Necessary:** Run one actual end-to-end demo pass that fires the surge replay, the waiting-room loop (Task 6), and Combat Mode (Task 14) together, not as three independently-tested features. Integration failures between individually-working pieces are the classic hackathon demo-day risk.
- **Good for win:** Auto-capture a before/after queue-order snapshot pair as script output — directly reusable in your pitch deck.
- **Okayish:** Configurable surge multiplier instead of hardcoded 3x.
- **If ample time:** Log the random seed for reproducibility if you move off a fully fixed seed.
- **No benefit:** Realistic non-Poisson ED arrival-distribution modeling — an ops-research exercise with no visible demo difference from what you have.

### Task 11 — Jurisdiction and compliance
- **Necessary:** Audit every endpoint that mentions jurisdiction (FHIR export, routing, anywhere else) for consistent language — this exact class of bug (mismatched legal-framework references) already happened once in this project's earlier drafts.
- **Good for win:** Name the specific DPDP consent basis you're relying on ("deemed consent for medical emergency purposes") in the disclaimer text itself, not just "not a live integration."
- **Okayish:** A visual toggle simulating a "connected" ABDM/NHCX state purely for demo storytelling.
- **If ample time:** A short data-flow diagram showing where PII would touch a live ABDM connection in production vs. today's offline mode — good for Q&A, no code needed.
- **No benefit:** Attempting real ABDM/NHCX sandbox registration during the hackathon — you won't get the onboarding turnaround in time.

### Task 12 — Multilingual voice intake
- **Necessary:** Resolve the ASR/punctuation gap flagged above — either confirm your negation logic degrades gracefully with no punctuation present (e.g., falls back to a slightly wider default window when no comma/period tokens exist at all in the transcript), or explicitly restrict the punctuation-based demo to typed-text input and narrate the ASR path separately with its own (wider, more conservative) negation handling.
- **Necessary:** Decide and rehearse exactly how the ASR spike is presented — as a clearly-labeled "decoupled concept demo: pre-recorded clip → transcript → matched via text pipeline," not wired live into the scorer, consistent with its current decoupled status and the ~25-27% real-world WER risk already documented for this class of model.
- **Good for win:** Extend negation-scope breaking to also stop at strong conjunctions ("but", "however") even without a comma — helps exactly the ASR-transcript case where punctuation is often missing but conjunctions still appear as spoken words.
- **Okayish:** N/A beyond the above for this task.
- **If ample time:** N/A.
- **No benefit:** N/A — this task doesn't have a "throw more infrastructure at it" failure mode the way others do; it's already scoped correctly, it just has the one integration gap above.

### Task 13 — Scheme-aware alternate-facility routing
- **Necessary:** Handle the case where a patient's ESI changes *after* an alternate-facility suggestion was already generated (e.g., waiting-room escalation from Task 6 bumps them from ESI 5 to ESI 3) — confirm the stale low-acuity routing suggestion is retracted or re-evaluated, not left visible as if still valid.
- **Good for win:** Show the reasoning together — scheme accepted, distance, and current capacity (Task 17) — as one cohesive suggestion, tying three built features into one demo beat.
- **Okayish:** Graceful "no matching facility" messaging instead of an empty/silent response.
- **If ample time:** A fictional but plausible distance/travel-time field.
- **No benefit:** Real geocoding/maps API integration — external dependency, no functional demo improvement over a static fictional distance.

### Task 14 — Queue-triggered Combat Mode
- **Necessary:** Make the trigger threshold read from the active hospital profile (Task 17) rather than a hardcoded `20` — a rural clinic's "surge" and an urban trauma center's are different numbers by definition, and leaving this as one global constant directly contradicts the hospital-variability story Task 17 exists to tell. Cheap fix, real credibility cost if left as-is.
- **Necessary:** Cross-check with Task 8 — confirm the trimmed payload still carries a truncated one-clause explanation, not nothing.
- **Okayish:** A distinct visual/audio cue when Combat Mode triggers, beyond payload trimming.
- **If ample time:** Tiered degradation (partial trim at 15, full at 20) instead of one binary threshold.
- **No benefit:** Any keystroke-dynamics or biometric stress trigger — already correctly excluded; don't let it resurface.

### Task 15 — Rolling override rate tracking
- **Necessary:** Add a minimum-sample-size guard before flagging — a rule evaluated 3 times with 1 de-escalation (33%) is noise, not signal, and shouldn't trip the same flag as a rule evaluated 200 times at 15%. This is a real statistical-correctness gap and a two-line fix (`if total_evaluations < N: skip`).
- **Good for win:** Link flagged cases directly back to the specific audit-log entries (Task 7) for one-click drill-down.
- **Okayish:** A trend view (rate over time) instead of a single snapshot number.
- **No benefit:** Per-clinician override-pattern breakdown — this recreates the same staff-surveillance trust problem already flagged and cut for keystroke-dynamics monitoring elsewhere in this project. Aggregate by rule, not by person.

### Task 16 — Visit history & FHIR export
- **Necessary:** Validate the exported JSON against the actual FHIR R4 resource requirements (required fields, correct resource `resourceType` values) before demo day — this is a specific, checkable technical claim, and Accenture's own healthcare practice means a judge who knows FHIR is a real possibility.
- **Good for win:** Include the confidence score and explanation text as a FHIR `Observation` component/extension in the export — carries your system's distinguishing feature through into the interoperability story, not just the ESI number.
- **Okayish:** A minimal in-app view of prior visit history, not just the raw export.
- **If ample time:** Support importing a FHIR bundle, not just exporting (bidirectional).
- **No benefit:** Standing up a full spec-compliant FHIR server (e.g., HAPI FHIR) instead of the lightweight mapping module you have — infra overkill for a static export demo.

### Task 17 — Hospital capability profiles
- **Necessary:** See Task 14 — wire Combat Mode's threshold to this config; it's the same fix viewed from either task.
- **Good for win:** Demo both profiles side-by-side against the same patient record to visibly show differing outcomes — cheap to script, directly illustrates "hospital variability" addressed.
- **Okayish:** A third "mid-size community hospital" profile for a fuller spectrum.
- **If ample time:** Bed-count depletion during the Task 10 surge replay, so beds actually fill up live.
- **No benefit:** Full resource-scheduling optimization (staff rosters, OR scheduling) — out of scope for what this system is meant to do.
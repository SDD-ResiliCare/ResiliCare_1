# PatientTriage.ai — Round 2 Build Priority Checklist

Three tiers. **Tier 1** is what the brief literally grades you on and what a hackathon team can actually finish — treat it as non-negotiable. **Tier 2** is where you differentiate once Tier 1 is solid. **Tier 3** is stuff that reads great on a slide but is a bad time-to-payoff trade in a hackathon window, or actively risky to demo live — cut it, or downgrade it to a labeled "future work" slide.

Each item: what problem it kills, exactly how to build it, and the real feasibility read (including what breaks if you try to overreach it).

---

## TIER 1 — Core (build this, in roughly this order)

### [ ] 1. Simulated patient dataset (do this FIRST)
- **Problem addressed:** Explicit rubric requirement — 15-20 records covering ambiguous, pediatric/geriatric, zero-history cases.
- **Approach:** Hand-author (or LLM-assist-author, then sanity-check yourself) a fixed CSV/JSON of patients.
- **Build steps:**
  1. Define schema: age, chief complaint, vitals (HR, RR, SpO2, BP, Temp), GCS/AVPU, self-reported pain, `has_prior_history` flag, arrival timestamp.
  2. Write 15-20 rows: spread across ESI 1-5, include 1 ambiguous (chest pain that could be indigestion or MI), 1 pediatric, 1 geriatric, 1 zero-history.
  3. For each row, write down the ESI level *you'd* defend as ground truth — you will get asked why, in Q&A.
- **Feasibility:** High. An afternoon. Everything else runs on this — don't leave it for last.

### [ ] 2. Hard-override rule layer (your actual scorer, v1)
- **Problem addressed:** Core scoring engine; foundation for B2/B4/B5.
- **Approach:** A short if/else table of clinical red flags that force a floor on ESI level, regardless of anything else. This alone is a legitimate, safe, honestly-described prototype scorer.
- **Build steps:**
  1. List red-flag conditions from published ESI algorithm decision points (SpO2 < 90, unresponsive/AVPU=U, active hemorrhage, HR/RR outside age-adjusted critical range → force ESI 1 or 2).
  2. Implement as a simple ordered rule evaluator: first matching rule wins, else fall through to step 3 below (classifier) or a default mid-tier score.
  3. (Optional, only if time remains) Layer a small classifier (logistic regression / small gradient-boosted tree) trained on a public ED triage CSV or your own synthetic data, to add nuance where no rule fires.
- **Feasibility:** High. This can be your entire scorer and it's still honest and defensible — don't feel obligated to add ML on top just because the ideation doc implies a big model.

### [ ] 3. Age-calibrated vital thresholds
- **Problem addressed:** B2 — one adult-calibrated model silently misjudging pediatric/geriatric patients.
- **Approach:** Lookup table, not a model.
- **Build steps:**
  1. Build an age-bracket table (neonate, infant, toddler, child, adolescent, adult, geriatric ≥65) with normal HR/RR/BP/Temp ranges per bracket, pulled from published pediatric early warning score tables and standard adult vital ranges (freely available, no data-access wait).
  2. In the scorer, convert each raw vital into a "deviation from normal-for-this-age-bracket" value instead of comparing to one universal adult threshold.
  3. Feed that normalized deviation into the rule layer / classifier, not the raw number.
- **Feasibility:** High. Pure engineering, zero ML, directly kills the exact failure mode the brief calls out by name.

### [ ] 4. Confidence/uncertainty on every score — never a bare number
- **Problem addressed:** B5, and an explicit rubric line ("must not return a score without a confidence indicator"). This is your best-grounded idea in the whole doc — don't cut or water this down.
- **Approach:** A simplified but real version of conformal-style deferral. You don't need to reproduce the full Triage-CP math to be legitimate.
- **Build steps:**
  1. If using a classifier: output class probabilities, not just the top class.
  2. Define a deferral rule: if top-class probability is below a threshold, or the gap between top-2 classes is small, output a *set* (e.g., "ESI 2-3") instead of a single level, and flag "escalate to senior nurse review."
  3. For zero-history patients or missing-vitals rows, explicitly widen the set / lower the confidence score — this represents missing-data uncertainty, and bias the set toward the higher-acuity side (this is your literal answer to "asymmetric cost of error").
  4. Surface it as a visible badge: "ESI 2 — High confidence" vs "ESI 2-3 — Escalate for review."
- **Feasibility:** High. Half a day. Highest judge-visibility-to-effort ratio in the whole list.

### [ ] 5. Missingness-aware handling for zero-history patients
- **Problem addressed:** A5.
- **Build steps:**
  1. Add `has_prior_history` boolean feature.
  2. When false: don't impute a guessed history value — zero out history-derived features and reweight the scorer toward directly observed vitals for that record.
  3. Surface it in the UI: "No prior history on file — score based on presenting vitals only."
- **Feasibility:** High. Half a day, pure data handling.

### [ ] 6. Waiting-room decay / re-triage loop (vitals + wait-time only, no acoustics)
- **Problem addressed:** B1 — "patients don't get forgotten in the waiting room."
- **Build steps:**
  1. Give each waiting patient a "safe wait" ceiling from their ESI level (published ESI time-to-provider targets exist for this).
  2. Run a simple ticking loop over your patient list; if a patient exceeds their ceiling, or their re-entered vitals worsen, re-score and bump queue position, flag for re-assessment.
  3. Log the re-triage event the same way you log everything else.
- **Feasibility:** High. It's a timer + rule loop over your own data structure. No sensor dependency needed to demo the concept.

### [ ] 7. Clinician override capture + audit log
- **Problem addressed:** D4, explicit rubric requirement.
- **Build steps:**
  1. "Override" button next to every AI-suggested ESI level.
  2. On click: require a reason (dropdown + free text); capture clinician ID, timestamp, original AI score + confidence, overridden score, reason.
  3. Store as append-only (JSON-lines file or a table with inserts only, no UPDATE/DELETE) — this honestly satisfies "immutable ledger" without needing real hash-chaining.
  4. Build one log-viewer screen for the demo.
- **Feasibility:** High. Standard CRUD-adjacent feature.

### [ ] 8. One-line explanation per score
- **Problem addressed:** D3 — clinician needs to verify in ~2 seconds.
- **Build steps:**
  1. Rule-triggered case: template the exact rule that fired ("ESI 2 — SpO2 91% below age-adjusted threshold of 94%").
  2. Classifier case (if you built one): use the `shap` package (works out of the box on tree models) to grab top 1-2 contributing features, template into a sentence.
  3. Display under the score badge.
- **Feasibility:** High if rule-based (trivial). Medium if SHAP-based (a couple hours of wiring, well-trodden library).

### [ ] 9. Rule-based differential table for ambiguous presentations (skip the GNN)
- **Problem addressed:** B4, simplified to something you can actually ship.
- **Build steps:**
  1. Small lookup table: common ambiguous complaint → differential considerations + mandatory safety-workup flag (e.g., "chest pain" → EKG + troponin recommended, regardless of ESI).
  2. When a complaint hits this table, force a minimum ESI ceiling (never let "chest pain" auto-resolve below ESI 3, even if vitals look mild).
  3. This becomes your demo's ambiguous-presentation test case, straight out of the brief.
- **Feasibility:** High. A GNN needs a labeled symptom-diagnosis graph you don't have; this table gets the same safety behavior demoed for near-zero risk.

### [ ] 10. Surge simulation (3x load)
- **Problem addressed:** Explicit rubric requirement.
- **Build steps:**
  1. Script that generates/replays patients arriving at 3x your baseline rate.
  2. Run against your scorer + queue; capture the re-sort behavior (and Tier-2 Combat Mode trigger, if built).
  3. Record before/after screenshots or a short clip for the demo.
- **Feasibility:** High. It's a load-test harness on top of logic you already built.

### [ ] 11. Written jurisdiction/compliance page (not code)
- **Problem addressed:** Explicit rubric requirement to state your assumed jurisdiction.
- **Build steps:**
  1. One page: "We assume deployment in India. Governing frameworks: DPDP Act 2023 (consent, purpose limitation, data minimization) + ABDM Health Data Management Policy (health data specifically). Consent model: deemed consent under DPDP's emergency-care carve-out, informed consent captured retroactively where possible. Retention: audit logs kept per [state a number] per hospital medico-legal retention practice."
  2. Cross-check every other section of your deck/doc that references a legal framework — make sure nothing else name-drops HIPAA or another jurisdiction by accident.
- **Feasibility:** High. Writing, not code. Cheap points to lose if skipped.

---

## TIER 2 — USP / Differentiators (build only once Tier 1 is solid and demoable)

### [ ] 12. Voice/multilingual intake (ASR kiosk) — canned audio, not live mic
- **Problem addressed:** A1 (data-entry bottleneck) + A3 (language barriers). Neither is in Accenture's explicit minimum-prototype list, so this is a differentiator, not a rubric checkbox — skipping it costs nothing on grading; building it well earns you a "we understand the actual Indian ED" narrative most teams won't have.
- **Approach:** Off-the-shelf ASR inference, no training. Whisper (OpenAI, open-source, workable on Hindi/major Indian languages) or AI4Bharat's IndicWav2Vec/IndicConformer via a HuggingFace inference call — either is fine for a hackathon; don't build your own model.
- **Build steps:**
  1. Record (don't live-capture) 2-3 short audio clips in different languages stating a plausible chief complaint — this is your test set.
  2. Pass each clip through Whisper or an AI4Bharat ASR model to get a transcript.
  3. Run basic keyword/entity extraction on the transcript (a small keyword-to-complaint dictionary mapping into your Tier-1 #9 differential table — no NLP model needed for this part).
  4. Feed the matched complaint into your existing scorer exactly as if it had been typed in.
  5. For the live demo: play a pre-recorded clip through a speaker into the mic, or just click "run" on a stored audio file — don't rely on a judge's-room mic and acoustics live. Speech demos fail in noisy venues more than any other demo type; a canned-but-real pipeline reads better than a live one that mishears.
- **Feasibility:** Medium. A few hours — the ASR call itself is one line, the keyword-extraction glue is the actual work. The honesty caveat (pre-recorded input, not live mic) matters more here than almost anywhere else in this doc — don't let this be the thing that visibly breaks in front of judges.

### [ ] 13. Insurance/scheme-aware routing (simulated data, not live NHCX)
- **Problem addressed:** C1, C2, your "financial exposure forecasting" idea.
- **Approach:** Fake the eligibility data — a live NHCX/insurer integration needs B2B sandbox onboarding you won't get in a hackathon window.
- **Build steps:**
  1. Attach a `scheme` field to each simulated patient (PM-JAY / ESI Scheme / private insurer X / self-pay).
  2. Build a small static table: which nearby facility accepts which scheme, cashless, room-rent cap ₹Y/day.
  3. For ESI 4/5 patients, have routing suggest an alternate fast-track/outpatient facility matching their scheme, tagged "cashless eligible at X."
  4. Label this explicitly in the demo: "simulated scheme data — a live NHCX integration would replace this lookup table in production." Don't let it read as a real integration.
- **Feasibility:** Medium. An afternoon of data modeling, zero real API dependency. Good differentiator — most teams won't touch the financial-routing angle at all.

### [ ] 14. "Combat Mode" surge UI (trigger off queue length, not keystrokes)
- **Problem addressed:** C3, D2.
- **Approach:** Same visual payoff as the original idea, honest trigger condition.
- **Build steps:**
  1. Build a second, stripped UI state: patient name, single critical-safety badge, one action button — nothing else.
  2. Trigger it automatically when your Tier-1 #10 surge simulation crosses a queue-length threshold you define (or via a manual "declare surge" button).
  3. Cite Wickens'/cognitive-load-theory framing in the pitch — that part of the reasoning is genuinely sound, you're just changing what triggers it.
- **Feasibility:** Medium. Visually strong demo moment, cheap once the queue engine exists.

### [ ] 15. Override-rate flagging (softened version of the 15% idea)
- **Problem addressed:** D4 extension.
- **Approach:** Flag for human review, don't auto-lock a rule — and split by override direction.
- **Build steps:**
  1. From your Tier-1 #7 log, compute a rolling override rate per rule/module.
  2. Track "escalating" (nurse raised acuity) and "de-escalating" (nurse lowered it) overrides separately — given your own asymmetric-cost framing, these mean very different things and shouldn't be one number.
  3. If de-escalating-override rate on a rule crosses a threshold, flag it for engineering review (don't auto-disable — that removes a safety net mid-review).
  4. Small dashboard panel showing this for the demo; script a few synthetic override events if you don't have enough real ones to show a rate.
- **Feasibility:** Medium. Needs populated log data to be visible — synthesize some for the demo.

### [ ] 16. FHIR-shaped export
- **Problem addressed:** D5.
- **Build steps:**
  1. Hand-map one simulated patient record into FHIR `Patient` / `Observation` / `Encounter` JSON resource shapes (HL7 FHIR publishes example resources you can pattern-match).
  2. Add an "Export as FHIR bundle" button that dumps this JSON.
  3. This proves you understand FHIR as a data *shape*, without needing an Epic/Cerner sandbox connection you won't get.
- **Feasibility:** Medium-low effort, disproportionately high credibility with any judge who actually knows healthcare IT.

### [ ] 17. Hospital-config templates (rural vs. urban)
- **Problem addressed:** C4.
- **Build steps:**
  1. Externalize rule thresholds and available-specialty flags into a config file (JSON/YAML) instead of hardcoding.
  2. Make two example configs: "urban trauma center" (full specialties, larger bed count) and "rural clinic" (no pediatric/surgical ward, smaller bed count — forces those cases to auto-flag for transfer).
  3. Demo by swapping the config file live and showing routing logic change.
- **Feasibility:** Medium-low. Mostly a refactor of Tier-1 work to stop hardcoding assumptions — good ROI once the core engine exists.

---

## TIER 3 — Cut for this round (future-work slide only, don't build)

### [ ] 18. Live camera-based rPPG vitals
- **Why cut:** Needs a real CV pipeline, controlled lighting, and your own audit already flagged accuracy/equity failure below 90% SpO2 — exactly the range that matters clinically. High effort, high risk of an embarrassing live-demo failure, undercuts your safety-first pillar if it breaks in front of judges.
- **If you still want it on a slide:** a pre-recorded clip with hardcoded output values, clearly labeled "concept demo, not live inference."

### [ ] 19. Bioacoustic ceiling-mic monitoring
- **Why cut:** COUGHVID/Coswara are COVID-cough classifiers, not general-deterioration detectors — repurposing them is a research project, not a hackathon feature. Also raises always-on-mic privacy optics you'd have to defend in Q&A.
- **If you still want it on a slide:** keep it as a labeled future-phase architecture diagram only.

### [ ] 20. Biometric MPI / facial recognition on unconscious patients
- **Why cut:** Real consent-for-the-incapacitated legal question with no clean answer, plus zero actual path to biometric registry access in a hackathon. Proposing it as "addressed" is a legal/ethical overreach for no prototype payoff.
- **What's actually worth keeping:** the `Trauma-Male-35` ephemeral shadow-record + EHR-merge-on-ID-confirmation workflow is a genuinely good idea and needs zero biometric hardware — build that part as a placeholder-ID flow in your UI, drop the facial recognition claim.

### [ ] 21. Keystroke-dynamics nurse stress detection
- **Why cut:** Confounded signal (typing style/ergonomics vary per person, unrelated to patient acuity), no way to validate it in a hackathon, and it reads as covert staff surveillance — directly undercutting the "get nurses to trust and adopt this" pillar you're also being judged on.
- **Alternative:** use Tier-2 #14's queue-length trigger instead — same visual payoff, none of the risk.

### [ ] 22. Real edge-fog-cloud Kubernetes multi-node deployment
- **Why cut:** Zero visible demo value — a single running instance proves the architectural point equally well to a judge. Orchestration setup time is better spent on Tier 1.
- **Alternative:** one Dockerfile, describe the scaling story verbally.

### [ ] 23. Live NHCX/IRDAI claims integration
- **Why cut:** Real B2B system requiring insurer/TPA onboarding and sandbox credentials you will not get during a hackathon.
- **Alternative:** Tier-2 #13 (simulated scheme lookup) gets you the same demo beat honestly.

### [ ] 24. Symptom-Graph Neural Network
- **Why cut:** Needs a labeled symptom→diagnosis graph dataset that doesn't exist off-the-shelf for this; training/validating a GNN from scratch is a multi-week research project on its own.
- **Alternative:** Tier-1 #9 (rule-based differential table) gets you the same "ambiguous chest pain forces a safety workup" demo beat for near-zero risk.

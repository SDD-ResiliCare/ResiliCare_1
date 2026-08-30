# NLP & Acoustic Triage Kiosk: Revised Architecture (Kiosk-Bounded Scope)

This revision keeps the original's self-critical format (name the failure mode, name the mitigation) but rescopes every component to what a hackathon team can actually build and defend, and corrects three claims that didn't hold up under checking: the negation-detection library, the downstream routing target, and the identity-binding mechanism.

**Scope boundary, stated explicitly:** everything below operates on a single bounded audio clip captured during one kiosk intake interaction. This is not a continuous ambient/ceiling-mic monitoring system. If a future phase wants that, it's a separate, much larger proposal — don't let it re-enter through this document.

---

## 1. Acoustic Distress Signal (kiosk-moment only, secondary signal — never a sole trigger)

*   **Original Concept (call-center):** `librosa` RMS energy, zero-crossing rate, and MFCCs to detect customer frustration from loudness and pitch.
*   **Kiosk Adaptation:** Run the same handful of `librosa` features on the *same clip already captured for ASR* — no separate always-on audio pipeline. Compare against a calibrated "normal speech" baseline (a few calm test recordings you make yourself) rather than an absolute threshold.
*   **Failure Mode:** ER environments are loud and non-speech noise (alarms, other patients, PA systems) will trip a naive loudness threshold constantly. This is a real risk — but note it applies whether the audio pipeline is continuous or kiosk-bounded; bounding it to one deliberate patient/family utterance at the kiosk removes most of the false-positive surface, since you're not trying to classify ambient hallway noise at all.
*   **Mitigation:** Voice Activity Detection (Silero VAD — one `pip install`, no training needed) to confirm the clip actually contains speech before running any feature extraction. Multi-feature fusion (require RMS *and* zero-crossing rate both above baseline, not either alone) to reduce single-feature false triggers.
*   **Triage Action:** If the fused signal crosses threshold, attach a soft flag — *"elevated vocal distress — verify"* — to the record. It never changes the ESI score on its own; it's a prompt for the nurse to double-check, exactly the same status as any other unconfirmed signal in this system.
*   **Effort:** A few hours, since it reuses the ASR clip. Skip entirely if time is tight — it's the most cuttable piece here and the rest of the pipeline works without it.

---

## 2. Clinical Acuity Detection (Red-Flag Keywords + Negation)

*   **Original Concept (call-center):** Generic urgency-word dictionaries (`"as soon as possible"`, `"priority"`).
*   **Kiosk Adaptation:** A red-flag keyword set aligned to ESI-1/ESI-2 presentations: `{"bleeding profusely", "crushing chest pain", "unconscious", "cannot breathe", "sudden weakness", "stroke symptoms"}`, extended with the equivalent phrases in whatever languages your ASR model outputs or transliterates to.
*   **Failure Mode:** Colloquial phrasing (`"feels like my chest is going to explode"`) and negation (`"not bleeding anymore, but..."`) break plain keyword matching.
*   **Correction from the previous draft:** that draft named `medspaCy`'s `ConText` module as the mitigation. ConText is real and well-established, but it's built and rule-tuned for formal English clinical documentation — physician notes, discharge summaries, phrasing like "no evidence of" or "ruled out." It is not tuned for colloquial speech transcribed from regional-language ASR output, and installing it will not give you working negation coverage for this input without rewriting the rule set yourself anyway — at which point you've done the same work without the library. **Don't add the dependency; write the check directly:**
    *   A short list of negation trigger words/phrases in each language you support (`"not"`, `"no longer"`, `"nahi"`, etc.).
    *   A simple proximity rule: if a negation trigger appears within ~3 tokens before a red-flag keyword, treat the match as negated and don't fire the override.
    *   This is roughly 20-30 lines of code, matched to your actual input register, instead of a library tuned for a different one.
*   **Triage Action:** An unnegated red-flag match immediately overrides the standard intake flow and locks the triage tier at maximum urgency, pending clinician confirmation — it does not silently auto-finalize a score.

---

## 3. Chief Complaint Extraction (Symptom Parsing)

*   **Original Concept (call-center):** `spaCy` dependency parsing / `KeyBERT` for intent categories (`"death claim"`, `"policy cancellation"`).
*   **Kiosk Adaptation:** Extract simple verb-noun/anatomical-entity pairs from the transcript and map them to the existing rule-based differential table (`ambiguous_presentations.json`).
    *   `"my stomach hurts severely"` → `Abdominal Pain (High Risk if Elderly)`
    *   `"feels like an elephant sitting on my chest"` → `Acute Chest Discomfort (ESI-2)`
*   **Failure Mode:** Clinical abbreviations, hyphenated terms, and jargon can break naive tokenization.
*   **Correction from the previous draft:** that draft routed extracted complaints into `evaluate_safety_rules()` *and* a "Symptom-Graph Neural Network engine." The GNN was already cut from this project's scope — there's no labeled symptom-diagnosis graph dataset to train it on, and building one is a multi-week research effort on its own, not a hackathon task. **Route matched complaints into the existing rule-based differential table only.** If this line reappears in a future draft, it's leftover text from the original ideation doc that didn't get reconciled with the actual build plan — flag it the same way next time.
*   **Triage Action:** Matched complaint feeds the rule-based differential table, which can force a minimum ESI ceiling (e.g., chest pain never auto-resolves below ESI 3) regardless of what the base scorer would otherwise output.

---

## 4. Multilingual ASR (The Indian Ecosystem)

*   **Original Concept (call-center):** Single-language commercial speech-to-text tuned for clean audio.
*   **Kiosk Adaptation:** AI4Bharat's `IndicConformer-600M-multilingual` (open-source, MIT-licensed, covers all 22 scheduled Indian languages) or Whisper, run as a single inference call — no training or fine-tuning required.
*   **Verified numbers (this is new — the previous draft asserted the failure mode existed but had no hard data):** A March 2026 benchmark (the DISPLACE-M challenge, IISc Bangalore) evaluated exactly this scenario — real Hindi conversations between community health workers and patients, recorded in villages and primary health centers in Haryana and Bihar, spontaneous and code-switched. Zero-shot IndicConformer-600M scored **25.56% WER / 26.78% tcpWER**. Fine-tuning on their annotated dev set brought it to ~19-20% WER — but that requires their training data and a fine-tuning run, which is out of scope for a hackathon. (Source: "Benchmarking Speech Systems for Frontline Health Conversations: The DISPLACE-M Challenge," arXiv:2603.02813, 2026.)
*   **What this changes:** roughly 1 in 4 words wrong, zero-shot, is not an edge case to patch around — it's the expected outcome for a meaningful share of interactions. The confidence-gated fallback below needs to be built and tested as a first-class UI path, not an error state that rarely fires.
*   **Mitigation:** Combine language ID (`IndicLID`) with a confidence gate: if the transcript doesn't produce an unambiguous keyword match in Section 3, or the model's own confidence signal is low, fall back immediately to icon-based manual entry. Don't attempt real-time fine-tuning, custom beam-search vocabulary constraints, or any other in-flight model adaptation — none of that is buildable in hackathon time, and the confidence gate achieves the same safety outcome more cheaply.
*   **Effort:** One model call plus the confidence-gate logic — a few hours total, most of which is testing the gate threshold against your own sample clips.

---

## 5. Patient Identity Binding (Trauma Alias, Not Biometrics)

*   **Original Concept (call-center):** `spaCy` NER to extract `PERSON` entities from `"My name is X"`.
*   **Kiosk Adaptation:** For unconscious, disoriented, or trauma patients who can't provide a name, generate an ephemeral shadow-record with a placeholder ID (`Trauma-Male-35`) that anchors initial point-of-care orders. Once identity is established — via an ID document, a family member, or hospital documentation — the shadow record merges into the real EHR entry.
*   **Correction from the previous draft:** that draft named biometric capture (fingerprint/facial recognition against a registry) as the identity-establishment mechanism. That's a real consent-for-the-incapacitated legal question with no clean answer, and there's no actual path to biometric registry access in a hackathon — it was already flagged for removal. **The placeholder-ID-to-EHR-merge workflow itself is genuinely good and needs zero biometric hardware to demo** — build that part as a simple UI flow (assign alias → confirm identity via a manual field → merge), and don't reintroduce biometrics as the trigger for that merge.
*   **Effort:** A UI workflow, not a recognition system — a few hours.

---

## 6. Summary of Core Technical Risks & Mitigations (revised)

| Pipeline Component | Risk / Failure Mode | Corrected Mitigation | Scope Note |
| :--- | :--- | :--- | :--- |
| **Acoustic Signal** | False positives from ER background noise. | VAD (Silero) + multi-feature fusion, run only on the kiosk-captured clip. | Kiosk-bounded, secondary/soft signal only — not continuous monitoring. |
| **Clinical Keyword Matching** | Colloquial phrasing and negation break plain keyword search. | A small, hand-written negation-proximity rule matched to your actual transcript register — not medspaCy/ConText, which is tuned for formal English clinical notes. | ~20-30 lines of custom code. |
| **Complaint Extraction** | Jargon/tokenization errors. | Route into the existing rule-based differential table. | No GNN — that's out of scope; don't let it reappear. |
| **Multilingual ASR** | ~25-27% WER zero-shot on real code-switched health conversations (verified, DISPLACE-M 2026). | Confidence gate to icon-based manual fallback, treated as a common path, not an edge case. | No live fine-tuning attempt in hackathon time. |
| **Identity Binding** | Unconscious/no-ID patients. | Placeholder alias + manual-confirmation EHR merge. | No biometric capture — legal/consent risk already flagged, not resolved by re-adding it here. |

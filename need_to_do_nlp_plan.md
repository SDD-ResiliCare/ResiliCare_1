# ResiliCare — Pillar 1 (Data & Intake) NLP & Audio Implementation Plan

This plan focuses strictly on **high-level architecture and backend logic** for the Pillar 1 intake prototype. It excludes minor regex/vocabulary tuning, focusing instead on robust demo execution, direct microphone processing, Whisper confidence evaluation, dynamic follow-up questioning logic, and fallback workflows.

---

## 1. Direct Microphone & Audio Ingestion Pipeline

```
┌─────────────────┐       ┌──────────────────────┐       ┌────────────────────────┐
│  Browser / Mic  │ ────> │ In-Memory Resampler  │ ────> │ Silero VAD (Speech Check│
│ (Raw WebM / WAV)│       │ (16kHz Mono Float32) │       │   + Librosa Distress)  │
└─────────────────┘       └──────────────────────┘       └───────────┬────────────┘
                                                                     │
                                                                     ▼
                                                         ┌────────────────────────┐
                                                         │   Whisper Inference    │
                                                         │ + Confidence Extractor │
                                                         └────────────────────────┘
```

### Architecture
1. **In-Memory Audio Ingestion**:
   * Ingest raw audio buffers (WebM/Opus or PCM WAV) directly into memory.
   * Transcode/resample to $16\text{ kHz}$ single-channel mono using `pydub` / `soundfile` without writing unencrypted audio files to disk (DPDP data minimization compliant).
2. **Silero VAD Gating**:
   * Evaluates voice probability. If no speech is detected (e.g. ambient ER noise, coughing, background chatter), short-circuit execution and return `speech_detected: false`.
3. **Acoustic Distress Signal**:
   * Compute Librosa RMS energy and Zero-Crossing Rate on the speech segment.
   * If threshold is exceeded, attach a soft flag (`acoustic_distress: true`, label: *"Elevated Vocal Distress — Verify"*) to the intake session without altering ESI scoring autonomously.

---

## 2. Whisper Confidence Scoring & Dynamic Touch Fallback

### Technical Confirmation: Does Whisper Provide Confidence Levels?
**Yes.** Whisper provides three distinct native confidence and quality metrics per segment and token:

1. **`avg_logprob` (Average Token Log Probability)**:
   * Computed as $\frac{1}{N} \sum_{i=1}^N \ln P(w_i \mid w_{<i})$.
   * **Interpretation**: Values close to $0$ (e.g. $\ge -0.3$) indicate high confidence. Values below $-0.8$ or $-1.0$ indicate high uncertainty, noise, or hallucinated text.
2. **`no_speech_prob` (Probability of Silence / Non-Speech)**:
   * Direct sigmoid probability from the `<|nospeech|>` token.
   * **Interpretation**: If $\text{no\_speech\_prob} > 0.6$, the segment is background noise rather than intelligible patient speech.
3. **`compression_ratio` (Gzip Repetition / Degeneracy Metric)**:
   * Ratio of raw text size to zlib compressed size.
   * **Interpretation**: Ratios $> 2.4$ indicate degenerate looping (e.g. repeating the same word indefinitely), a known Whisper failure mode.

```python
# Reference Implementation for Whisper Confidence Extraction
def evaluate_whisper_confidence(segment: dict) -> tuple[float, bool]:
    avg_logprob = segment.get("avg_logprob", 0.0)
    no_speech_prob = segment.get("no_speech_prob", 0.0)
    compression_ratio = segment.get("compression_ratio", 1.0)
    
    # Confidence score mapped to [0.0, 1.0] range
    confidence_score = float(max(0.0, min(1.0, 1.0 + (avg_logprob / 2.0))))
    
    # Trigger fallback if logprob is low, no_speech is high, or repetitive hallucination
    is_confident = (avg_logprob > -0.75) and (no_speech_prob < 0.5) and (compression_ratio < 2.2)
    return confidence_score, is_confident
```

### Dynamic Fallback Logic
* When `is_confident == True`:
  * Backend returns `layout_directive: "AUDIO_CONFIRMED"`, with extracted `chief_complaint` and transcript.
* When `is_confident == False` or speech is unintelligible:
  * Backend returns `layout_directive: "SWITCH_TO_TOUCH_GRID"`, prompting the client to display high-contrast touch cards (Chest, Abdomen, Head, Trauma, etc.).
* **Demo Narrative**:
  * **Happy Path**: Speaker speaks clearly into the mic (*"Severe pain in my chest"* / *"Seene mein tez dard"*); system extracts complaint with $>0.85$ confidence.
  * **Fallback Path**: Muffled/unintelligible audio is submitted; system demonstrates safety by rejecting the transcript and switching to touch selection.

---

## 3. Dynamic Follow-Up Logic: Architecture Comparison & Selection

The goal of dynamic follow-up questioning is to solve the **"Hidden Symptoms"** problem (e.g. patient mentions a stomach ache but fails to disclose vomiting blood or pregnancy).

### Options Evaluated:

| Architecture | How It Works | Strengths | Risks / Drawbacks for Demo |
| :--- | :--- | :--- | :--- |
| **Option A: Full GenAI / RAG** | An LLM queries a vector DB of medical guidelines (AHA/ACOG) and generates free-text questions. | Dynamic phrasing; adapts to rare complaints. | **High Latency (1.5–3s delay)**; risk of clinical hallucination; unvalidated medical questions violating our safety invariants. |
| **Option B: Deterministic Clinical Decision Trees** | Direct mapping from `chief_complaint` to 2–3 pre-vetted, high-yield binary (Yes/No) questions in DB [`Questionnaires`](file:///Users/rishit/Projects/ResiliCare_1/src/db/models/triage.py#L41-L51). | **Instant (0ms latency)**; 100% clinically auditable and sourced (AHA/ACC, ACOG); zero hallucination risk; fully reproducible demo. | Fixed question sets per mapped category. |
| **Option C: Hybrid (Deterministic Tree + Guardrailed LLM Fallback)** | Deterministic trees for primary categories (Chest, Abdomen, Head, Pelvis); structured LLM JSON schema for unmapped complaints. | Full coverage with safety-first determinism for major cases. | Slightly higher implementation surface. |

### Selected Architecture: **Deterministic Clinical Rule-Tree Engine (Option B)**
For our prototype and demo day, **Option B is the superior choice**. It directly utilizes our database schema ([`Questionnaire`](file:///Users/rishit/Projects/ResiliCare_1/src/db/models/triage.py#L41-L51), [`QuestionnaireQuestion`](file:///Users/rishit/Projects/ResiliCare_1/src/db/models/triage.py#L53-L71), and [`SymptomInterview`](file:///Users/rishit/Projects/ResiliCare_1/src/db/models/triage.py#L73-L88)) and prevents latency hiccups or hallucinated medical questions during live judging.

```
┌────────────────────────────┐
│ Extracted Chief Complaint  │  (e.g., "lower abdominal pain")
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ Clinical Rule-Out Resolver │  ──> Loads matching Questionnaire
└─────────────┬──────────────┘
              │
              ├───────> Question 1: "Are you vomiting blood or having black stools?" (Bleeding Risk)
              │         └─ If YES: Promotes intake to ESI-2 / forces immediate clinician review
              │
              └───────> Question 2: "Is there sudden severe dizziness or fainting?" (Hypovolemia / Shock)
                        └─ If YES: Triggers syncope / circulatory collapse safety pathway
```

### Core Follow-Up Protocol Mapping:
1. **Acute Chest Discomfort**:
   * Q1: *"Does the pain radiate to your jaw, neck, back, or left arm?"* (ACS Marker)
   * Q2: *"Are you experiencing shortness of breath, sweating, or nausea?"* (Diaphoresis/Dyspnea)
2. **Lower Abdominal / Pelvic Pain**:
   * Q1: *"Are you experiencing any vomiting of blood, black stools, or severe dizziness?"* (GI Bleed)
   * Q2: *(For female of childbearing age)* *"Is there a possibility of pregnancy?"* (Ectopic Rule-out, ACOG)
3. **Syncope / Dizziness / Fall**:
   * Q1: *"Did you lose consciousness completely, even for a few seconds?"* (True Syncope vs Presyncope)
   * Q2: *"Did you hit your head or experience chest palpitations before falling?"* (Trauma/Arrhythmia)

---

## 4. Ephemeral "Trauma-XXX" Shadow Intake & EHR Merge Workflow

For unconscious, disoriented, or zero-ID arrivals (Pillar A2):

```
┌────────────────────────────────┐
│  Silent / Unconscious Arrival  │
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│ Generate Shadow Patient Record │  ──> Alias: "Trauma-Male-35-Unidentified"
│  + Open Emergency Encounter    │      (is_unidentified: true)
└───────────────┬────────────────┘
                │  [Point-of-Care Vitals & Triage Orders Logged]
                ▼
┌────────────────────────────────┐
│   Patient Identity Established │  ──> Family arrives / ID found
└───────────────┬────────────────┘
                │
                ▼
┌────────────────────────────────┐
│  Atomic EHR Merge Transaction  │  ──> Re-parents all Vitals, Interventions &
│   (Preserves Full Audit Trail) │      Assessments to permanent Master Record
└────────────────────────────────┘
```

1. **Shadow Intake Endpoint**:
   * Generates ephemeral alias (`Trauma-Male-35` or `Trauma-Unknown-XXXX`).
   * Opens encounter and stores initial vital readings and clinical observations.
2. **Atomic Merge Service**:
   * When identity is confirmed, executes an atomic database transaction re-parenting all `VitalObservation`, `SymptomInterview`, `TriageAssessment`, and `ClinicianDecision` records to the permanent patient record.
   * Preserves full cryptographic audit provenance recording the original alias and transition timestamp.

---

## 5. Step-by-Step Implementation Sequence

```
1. Audio Pipeline Upgrade
   ├── Update `src/nlp/audio_pipeline.py` with in-memory buffer handling
   ├── Extract Whisper `avg_logprob` & `no_speech_prob`
   └── Add confidence calculation helper

2. Dynamic Follow-Up Questioning Service
   ├── Seed canonical questionnaires (Chest Pain, Abdominal Pain, Syncope)
   ├── Create `SymptomInterview` resolver matching complaints to question trees
   └── Add rule-out escalation logic (upgrades safety ceiling if critical answer is "Yes")

3. Trauma Alias & Reconciliation Service
   ├── Add shadow patient creation logic
   └── Add atomic EHR merge service with audit trail

4. Unified Kiosk Intake Engine
   └── Combine Speech/Text -> Complaint -> Follow-Up Tree -> Intake Payload for `score_with_confidence()`
```

# PatientTriage.ai: Extended Problem Statement (Round 2)

## Recap & Expanded Context
In Round 1, you explored a patient triage assistant that helps hospital staff prioritize and route patients as they arrive, aiming to reduce wait times without replacing clinical judgment. In practice, no two emergency departments look alike—patient mix, staffing levels, and existing systems vary enormously, and the tool must work under real-time pressure with imperfect information.

For Round 2, develop your concept into a more complete solution, backed by a working prototype that demonstrates how it would behave with realistic (even if simplified or simulated) patient data.

## Real-World Complexities to Consider
- **Overlapping/Ambiguous Symptoms:** Patients present with overlapping or ambiguous symptoms that don't map cleanly onto standard severity scales — some patients under-report pain or symptoms, and presentation can differ significantly by age or condition.
- **Demographic Variances:** Vital sign thresholds and symptom weights differ significantly across pediatric, adult, and geriatric populations — a fever of 38.5°C carries different clinical urgency in a 3-year-old versus a 75-year-old. Solutions that apply to a single adult-calibrated scoring model across all age groups introduce silent safety risk.
- **Data Quality & Availability:** Data quality and availability at intake varies hugely — a returning patient may have a rich history in the hospital's systems, while a first-time patient may have almost nothing beyond what's observed in the moment.
- **Time Pressure:** Triage decisions must be made — and be explainable — within seconds, by a clinician who is often simultaneously managing several other patients.
- **Asymmetric Costs of Error:** Under-triage and over-triage carry asymmetric costs — missing a critical case is categorically worse than over-prioritizing a minor one. Any solution must be deliberately tuned to bias toward escalation under uncertainty rather than optimized for average accuracy, and teams must demonstrate this design choice explicitly in their prototype.
- **Hospital Variability:** Hospitals differ enormously in scale, specialty mix, and staffing — a workflow that works for a large urban trauma center may not transfer to a small rural emergency department.
- **Clinical Accountability:** Clinical accountability and liability mean any recommendation must remain reviewable and overridable by a licensed clinician, with a clear audit trail and compliance with health-data regulation.
- **System Integration:** Integration with existing hospital systems (patient records, bed management, staff rosters) is rarely simple, and system maturity varies a great deal from one hospital to the next.

## Solutioning Areas You Could Explore
- **Data strategy:** How you'd structure and weigh available inputs (vitals, self-reported symptoms, history, observed cues) despite inconsistent completeness.
- **Decision model:** Rules-based scoring, ML-based risk scoring, or a hybrid, and how you would represent the assistant's own uncertainty.
- **Workflow design:** How a recommendation is surfaced to a nurse in the moment, how overrides are captured, and how the system behaves differently during a surge versus a quiet shift.
- **Safety-first design:** Sensible fail-safe defaults (for example, escalating rather than downgrading when uncertain), and ongoing monitoring of waiting patients for signs of deterioration. The system must monitor patients already in the waiting queue and trigger re-assessment if wait time exceeds safe thresholds for their severity level or if vitals are re-recorded as worsening.
- **Adoption & change management:** How you'd get a fatigued, time-pressured staff to actually trust and use the tool rather than work around it.
- **Patient data protection:** How would the patient data be protected from unfair and unauthorised usage.
- **Scalability:** How the same underlying assistant could flex across hospitals of very different size, specialty mix, and technical maturity.

## Reference Parameters (Illustrative — Adapt Freely)
- Assume emergency departments ranging from roughly 100 to 500+ patient visits per day.
- You may reference standard triage frameworks (e.g., a 5-level severity scale) or propose an alternative.
- Assume mixed data availability — roughly half of arriving patients have some prior health record on file, half do not.
- State your assumed regulatory jurisdiction (e.g., HIPAA in the US, GDPR + national health law in the EU, or a named equivalent). This affects your audit trail design, data retention policy, consent model, and what a clinician override must legally record.

*These parameters are directional, not a fixed dataset — you're encouraged to make your own reasonable assumptions, state them clearly, and design a solution that would generalize for broader adoption.*

## Minimum Prototype Expectations (Illustrative):
- Demonstrate triage scoring on at least 15–20 simulated patient records.
- Include at least one ambiguous presentation, one pediatric/geriatric case, and one zero-history (first-time) patient.
- Show how the system behaves under a simulated surge (e.g., 3× normal volume).
- Surface uncertainty explicitly — the prototype must not return a score without a confidence indicator.
- Capture at least one clinician override and show what the system logs.
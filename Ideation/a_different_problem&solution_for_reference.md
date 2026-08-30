# Reference Problem & Solution: GE HealthCare Precision Care Challenge 2026

**Problem Statement (PS):** Hospitality: Holistic Optimization System for Policy-Integrated Admission & Treatment Intelligence  
**Core Themes:** Insurance policy + Patient Triage (ABHA, NHCX, hospital Gipsa, PPN)

## Roles
- **Hospital Site:** Handling patient surge, patient data, end-to-end tracking of patient’s care journey, easing out discharge process, providing updates to doctors/nurses from the vitals of patient, triage.
- **Patient Site:** Vitals entry, basic analysis and suggestion to select hospital, end-to-end care journey for the caretakers.
- **Management Site/Reception:** Hospital mapping, supply vs demand analysis and mapping, number of beds, doctors, distribution.
- **Insurance Site:** Decisions on insurance coverage, hospital-linked insurance, treatment care finances.

---

## 1. Solution Vision
A patient/caregiver-facing decision-support platform that turns a person's insurance coverage into a live, plain-language filter over hospital, room, and treatment choices — from the moment they're deciding where to go, through every stage of the hospital journey — without ever making a diagnosis or a binding insurance decision.

Think of it as **"Google Maps for insurance-constrained hospital care"**: you tell it where you are and what coverage you hold, and at every step it shows you the eligible routes, the cost of deviating, and what's coming next — but the human always drives.

## 2. Solution Architecture
This architecture is mapped into four distinct modules:

### Module 1: Insurance & User Data Ingestion Engine
- **Function:** User uploads or manually enters policy details (insurer, policy type, sum insured, room eligibility, exclusions, sub-limits, scheme membership — private/ESI/PM-JAY/state scheme).
- **AI Role:** An LLM-based document parser (RAG over the uploaded policy PDF/mock data) extracts structured fields (sum insured, room-rent cap, co-pay %, waiting periods, exclusions, network status) into a standardized internal schema. This is modeled loosely on the FHIR-style claims/coverage resources NHCX already uses, making the system architecturally ready to plug into NHCX later.
- **For Synthetic Data:** Build ~15-20 mock policy templates spanning private insurers, ESI profiles, PM-JAY profiles, and state schemes (e.g., Yeshasvini) to demonstrate handling of scheme-fragmentation.

### Module 2: Hospital & Care Option Mapping Engine
- **Data Source:** Simulated/public hospital dataset including location, specialties, room categories + indicative tariffs, network/empanelment status per scheme.
- **Constraint-Matching Engine (Not a diagnostic recommender):** Given the user's coverage profile + a stated need, filter and rank hospitals/rooms by:
  - **Network fit:** In-network vs. Cashless Everywhere-eligible vs. out-of-network/reimbursement-only.
  - **Room-eligibility fit:** Projected proportionate-deduction exposure if the user selects above their cap (targeting the 20–65% claim-shortfall problem).
  - **Distance/specialty match:** Using consumer app signals (e.g., Practo-style specialty search).
- **Explainability:** Every ranked suggestion carries a plain-language explanation (e.g., *"This hospital is in-network for your PM-JAY entry, but the private ward exceeds your ₹5,000/day cap — expect roughly a 40% reduction on room-linked charges"*).

### Module 3: Care Journey Tracker (With Insurance-Aware Nudges)
- **State Machine:** Admission → Investigation → Procedure → Recovery → Discharge.
- **Stage-Relevant Guidance:** Surfaces guidance at each transition:
  - *At admission:* Expected pre-auth requirements and real regulatory SLAs (e.g., cashless pre-authorization within 1 hour, final approval within 3 hours).
  - *Mid-stay:* Alerts if a room transfer or procedure add-on pushes the patient outside their eligible package.
  - *Discharge:* A plain-language summary of what should and shouldn't be subject to proportionate deduction (citing IRDAI protections).
- **Holistic Companion:** This tracker makes the system a genuine companion through the journey, fulfilling the "holistic" requirement of the PS.

### Module 4: User-Facing Web Experience
- **Insurance Summary Card:** Plain-language summary (no legalese) highlighting key constraints.
- **Ranked Suggestions:** Hospital/room suggestions with the "why" always visible.
- **Timeline View:** Journey timeline with informational prompts at each stage.
- **Caregiver-First Design:** Built for a family member acting on someone else's behalf, under stress, on a phone.

## 3. Innovation & Differentiation

### Novel AI Usage
- **Fusing Three Data Types:** Normalizes insurance coverage, hospital/room/cost data, and real-time journey stage into one continuously-updated decision surface.
- **Proportionate-Deduction Forecasting:** Turns IRDAI's published circulars into a real-time calculator for claim shortfalls, a highly demo-able AI+rules feature.
- **Guardrailed GenAI:** A structured output schema constrains the LLM to only return matched hospitals, coverage text, confidence scores, and disclaimers. A lightweight classifier intercepts clinical queries and redirects them, enforcing the "Decide vs. Recommend" governance boundary.
- **Grounded AI (RAG):** Every generated suggestion is anchored to the user's uploaded policy text and hospital dataset.
- **Sits on Top of NHCX:** Positioned as the missing consumer-facing application layer (like PhonePe/GPay for UPI) rather than reinventing the B2B claims rail.

### Differentiation vs. Existing Players
| Player | Their Layer | Your Differentiation |
| :--- | :--- | :--- |
| **Practo / 1mg / mfine** | Doctor/hospital discovery, symptom triage | Adds insurance-constraint-aware ranking and financial-exposure forecasting. |
| **Policybazaar / Turtlemint** | Pre-purchase policy comparison | Operates at admission-time (post-purchase) when the policy is locked in. |
| **Insurer-side RAG Chatbots** | Fast answers for agents/insurer staff | Patient/caregiver-facing, on the opposite side of the table. |
| **GE HealthCare Command Center** | Hospital-side capacity orchestration | The patient-facing counterpart GE's portfolio doesn't yet have. |
| **NHCX** | B2B claims/pre-auth data rail (FHIR) | The missing consumer application built *on* that rail. |

## 4. Potential Healthcare Impact
- **Reduces Room-Rent Shock:** Addresses the documented 20-65% claim-shortfall mechanism, preventing unexpected out-of-pocket costs.
- **Bridges the Comprehension Gap:** Converts complex policy documents into situation-specific guidance.
- **Serves the "Missing Middle":** Helps PM-JAY/ESI beneficiaries find active empanelled hospitals, not just private insurance holders.
- **Reduces Decision Paralysis:** Aids caregivers during high-stress moments at admission time.
- **Complements National Infrastructure:** Aligns with NHCX's data model, demonstrating a genuine pathway to implementation.

---

## Research, Validation & Precedents

### Group A: Regulatory Infrastructure & Interoperability
1. **IRDAI "Cashless Everywhere" Circular (23 Jan 2024)**
   - [IRDAI Official Site](https://irdai.gov.in) | [Plain-English Guide](https://nyvo.in/health-insurance/cashless-everywhere-guide)
   - *Relevance:* Justifies the "network vs. non-network coverage exposure" feature by proving cashless treatment is available at any registered hospital.
2. **IRDAI Master Circular on Health Insurance Business (29 May 2024)**
   - [Consolidated Rules](https://nyvo.in/health-insurance/irdai-master-circular-2024) | [SLA Deep-Dive](https://www.oquilia.com/news/irdai-health-master-circular-2024-cashless-moratorium-rules)
   - *Relevance:* Provides exact regulatory SLAs (1-hour pre-auth, 3-hour discharge) to cite in the Care Journey Tracker.
3. **National Health Claims Exchange (NHCX)**
   - [Official System](https://hcxbeta.nha.gov.in/) | [NHA-IRDAI Press Release](https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=1976957&reg=48&lang=2)
   - *Relevance:* Proves the foundational B2B rail (FHIR-standardized) already exists, validating the implementation pathway.

### Group B: Algorithmic / AI Validation
4. **LayoutLMv3 (Document AI)**
   - [arXiv Paper](https://arxiv.org/abs/2204.08387) | [Official Model](https://huggingface.co/microsoft/layoutlmv3-large)
   - *Relevance:* Backs Module 1. LayoutLMv3 is the state-of-the-art architecture for extracting structured fields from un-templated PDFs/scans.
5. **Bed Assignment Under Uncertainty (Albedran et al., 2025)**
   - [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S095219762501365X)
   - *Relevance:* Validates the constraint-matching methodology used in Module 2.
6. **Discharge/LOS Prediction (Wei et al., 2024)**
   - [Communications Medicine (Nature)](https://www.nature.com/articles/s43856-024-00673-x)
   - *Relevance:* Shows that stage-based, event-triggered prediction is a mature ML technique, serving as a precedent for Module 3.

### Group C: Governance & Precedents
7. **"Artificial Intelligence for Patient Flow" (CADTH Horizon Scan, 2024)**
   - [PubMed](https://pubmed.ncbi.nlm.nih.gov/38985917/) | [Full Text](https://www.ncbi.nlm.nih.gov/books/NBK604824/)
   - *Relevance:* Recommends the "Decide-vs-Recommend" governance boundary, proving the system's human-in-the-loop design follows recognized best practices.
8. **Fragmented Public Capacity Dashboards**
   - *Relevance:* Shows that raw capacity transparency fails without financial/coverage mapping—highlighting the exact gap this solution fills.
9. **LeanTaaS / Hospital IQ Acquisition**
   - [Healthcare IT News](https://www.healthcareitnews.com/news/leantaas-acquires-hospital-iq)
   - *Relevance:* Validates the >$1B enterprise appetite for hospital-ops AI, arguing that the patient/insurance-facing counterpart is an unexploited whitespace.
10. **MIT Solve — "Bed Space Tracker", Nigeria**
    - [MIT Solve](https://solve.mit.edu/challenges/maternal-and-newborn-health/solutions/31582)
    - *Relevance:* Demonstrates that "supply-blindness at the point of referral" is a globally recognized failure mode.

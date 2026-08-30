# Jurisdiction and Compliance Framework

## Assumed Deployment Jurisdiction
**India**

## Governing Legal and Regulatory Frameworks
This prototype (PatientTriage.ai) operates under the assumption of deployment within the Indian healthcare system and is designed to comply with the following primary frameworks:

1.  **Digital Personal Data Protection (DPDP) Act 2023**
    *   **Data Minimization & Purpose Limitation:** The system strictly captures only the physiological and demographic data necessary for acute triage scoring.
    *   **Consent Model:** Under the DPDP Act's emergency-care carve-out provisions (Sections regarding medical emergencies and threat to life/health), the system relies on **deemed consent** for the immediate intake and triage phase. Informed consent is captured retroactively once the patient is stabilized or via authorized family representatives.
    *   **Right to Erasure:** Ephemeral shadow-records ("Trauma-Male-35") can be instantly wiped or merged once patient identity and stability are established, ensuring minimal permanent footprint for unverified individuals.

2.  **Ayushman Bharat Digital Mission (ABDM) Health Data Management Policy**
    *   **Health Data Specifically:** Alignment with ABDM's focus on secure, interoperable health data exchange. The system's architecture supports asynchronous FHIR standards for downstream reporting while preserving immediate edge-compute safety.

## Data Retention and Audit Logging
*   **Tamper-Evident Ledgers:** All triage decisions, clinical overrides, and waiting room queue re-sorts are recorded in an append-only audit log.
*   **Retention Period:** Audit logs and triage decision metadata are retained for **7 years**, aligning with standard Indian hospital medico-legal retention practices and regulatory guidance.
*   **Edge Processing:** Raw optical or acoustic intake data (e.g., from camera/mic arrays, if utilized in future hardware expansions) is strictly processed on local edge nodes and wiped from RAM within milliseconds, never transmitting to the cloud.

---
*Disclaimer: This is a hackathon prototype. The above frameworks outline the architectural compliance goals for a production system but do not constitute legal advice or a certified medical device.*

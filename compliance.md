# Jurisdiction and compliance position

## Assumed jurisdiction

This prototype assumes deployment in **India**. It is an educational hackathon system, not a
certified medical device, production privacy programme, or legal opinion.

## Applicable design targets

### Digital Personal Data Protection Act, 2023 and Rules, 2025

The prototype is designed toward the DPDP framework's requirements for clear purpose, necessary
data, safeguards, accuracy, accountability, and deletion when a purpose and legal retention need
end. It does not claim certified compliance.

For a life-threatening medical emergency, section 7(f) identifies processing needed to respond to
the threat as a **certain legitimate use**. This document deliberately does not call that “deemed
consent,” which is not the Act's terminology. Emergency processing must remain limited to the
immediate clinical purpose. Notice and consent should be obtained when required for later,
non-emergency processing or sharing.

The Act has phased commencement. Under the 13 November 2025 notification, sections 3–17—including
sections 7–10—commence 18 months after publication, on **13 May 2027**. The deployment team must
re-check the law, rules, hospital obligations, and state requirements at launch rather than treat
this prototype note as a final compliance determination.

### ABDM Health Data Management Policy

ABDM health-record linking and sharing are consent-driven. A clinical provider retains records in
its own system under its approved retention policy; this prototype does not upload records to ABDM,
create ABHA identities, or represent an ABDM integration.

## Prototype data controls

- Collect only the fields needed for triage, reassessment, clinician review, and the audit trail.
- Keep score, confidence, explanation, clinician action, and queue events in an append-only
  application log. This is not a cryptographically immutable ledger.
- Do not erase or merge an unidentified patient's clinical record merely because identity becomes
  known. Identity reconciliation must preserve provenance and required medico-legal history.
- Protect access with production authentication, role-based authorization, encryption, backups,
  breach response, and an approved retention/deletion schedule; these controls are not implemented
  by this localhost demo.

## Retention assumption

The prototype uses a **three-year minimum retention baseline** for triage and related audit records,
aligned to the currently operative NMC-hosted Code of Medical Ethics rule for inpatient medical
records. A hospital may require a longer period because of state rules, accreditation, insurance,
litigation/legal hold, minors' records, or its approved medico-legal schedule. Legal obligations
override deletion requests while they apply; records should not be retained indefinitely without a
documented purpose.

## Official sources

- [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf)
- [DPDP phased-commencement notification, 13 November 2025](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf)
- [Digital Personal Data Protection Rules, 2025](https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf)
- [ABDM Health Data Management Policy](https://abdm.gov.in/static/media/health_management_policy_bac9429a79.80f74bc3e039c00acd4f.pdf)
- [ABDM FAQ](https://abdm.gov.in/FAQ)
- [NMC-hosted Code of Medical Ethics Regulations, 2002](https://www.nmc.org.in/rules-regulations/code-of-medical-ethics-regulations-2002/1000/)
- [NMC regulations index noting the 2023 professional-conduct regulations are in abeyance](https://www.nmc.org.in/rules-regulations-nmc/)

# Resilicare PatientTriage.ai: Project Guide & Context

Welcome to the Resilicare PatientTriage.ai workspace! This document serves as your compass. Whether you are a developer ready to build the Round 2 prototype, or a strategist preparing for the pitch, use this guide to navigate the project documentation.

## 📖 Recommended Reading Order
If you are new to the project and want the full context, read the documents in this order:
1. `extended_ps.md`
2. `problem_we_discovered_rnd1.md`
3. `proposed_solution_rnd1.md`
4. `ideation.md` & `proven_solutions_research.md`
5. `Patienttriage build checklist.md`

*(Note: `Samosa_Driven_Development_PatientTriage_rnd1_submission.pdf` is our original Round 1 submission and `a_different_problem&solution_for_reference.md` is an external reference document).*

---

## 📑 Document Summaries & Navigation Guide

### 1. The Core Requirements
**If you want to understand exactly what the judges are asking for in Round 2...**
👉 **Read: [`extended_ps.md`](file:///Users/rishit/Projects/Resilicare/extended_ps.md)**
* **Summary:** The official, extended problem statement from Accenture for Round 2. It outlines the real-world complexities (ambiguous symptoms, pediatric vs. adult baselines, zero-history patients) and the strict minimum prototype expectations (15-20 simulated records, surge simulation, explicit uncertainty scoring, and clinician override logs).

### 2. The Problem Space
**If you want to understand the clinical and operational chaos we are trying to solve...**
👉 **Read: [`problem_we_discovered_rnd1.md`](file:///Users/rishit/Projects/Resilicare/problem_we_discovered_rnd1.md)**
* **Summary:** Our deep dive from Round 1 into the high-stakes environment of Emergency Departments. It breaks down the problem into four pillars: Data/Intake, Clinical/Demographic bias, Operational Crowding, and Environmental Chaos (infrastructure/nurse fatigue).

### 3. The Theoretical Architecture
**If you are building the pitch deck or want to understand the "moonshot" vision...**
👉 **Read: [`proposed_solution_rnd1.md`](file:///Users/rishit/Projects/Resilicare/proposed_solution_rnd1.md)**
* **Summary:** The comprehensive framework proposed in Round 1. It structures the solution into four phases (Rapid Intake, Core Processing, Continuous Monitoring, Chaos Mitigation). It also contains a detailed **Feasibility Analysis** linking our proposed systems to real-world datasets (MIMIC-IV, AI4Bharat) and academic research.

### 4. Deep Research & Ideation
**If you need academic backing for a specific edge case or want to see how we mapped problems to solutions...**
👉 **Read: [`ideation.md`](file:///Users/rishit/Projects/Resilicare/ideation.md)** and **[`proven_solutions_research.md`](file:///Users/rishit/Projects/Resilicare/proven_solutions_research.md)**
* **Summary:** These documents map the problems to specific informatics literature. `ideation.md` is a matrix tracking how every single gap is addressed. `proven_solutions_research.md` dives into literature-backed solutions for specific edge cases (e.g., using "Trauma XXX" shadow-records for unconscious patients, handling missing EHR data, and addressing cultural pain bias).

### 5. The Engineering Gameplan (The MVP)
**If you are ready to write code and need to know what to build RIGHT NOW...**
👉 **Read: [`Patienttriage build checklist.md`](file:///Users/rishit/Projects/Resilicare/Patienttriage%20build%20checklist.md)**
* **Summary:** The pragmatic, ruthless hackathon build plan. It breaks the project down into three tiers. It translates the theoretical vision into actionable engineering tasks (e.g., building the simulated dataset, the hard-override rule layer, and the UI surge triggers) while explicitly telling you what *not* to build (Tier 3) to protect the prototype's stability.

### 6. Reference Material
**If you need a reference for structuring solutions or UI/UX inspiration from an adjacent domain...**
👉 **Read: [`a_different_problem&solution_for_reference.md`](file:///Users/rishit/Projects/Resilicare/a_different_problem&solution_for_reference.md)**
* **Summary:** An external reference document solving a different problem (Insurance & Patient Triage). Useful for borrowing structural patterns, differentiation tables, and responsible-AI framing ("Decide vs. Recommend").

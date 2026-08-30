import json
from pathlib import Path

from resilicare import evaluate_safety_rules

root = Path(__file__).parents[1]
patients = json.loads((root / "data" / "simulated_patients.json").read_text(encoding="utf-8"))["patients"]

for patient in patients:
    result = evaluate_safety_rules(patient)
    profile = result["age_adjusted_vitals"]["profile_id"]
    print(patient["patient_id"], profile, result["status"], result["provisional_esi"], result["matched_rule_ids"])

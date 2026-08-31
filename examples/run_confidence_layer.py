import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

from src.core.confidence_scoring import score_with_confidence

base = {
    "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
    "dbp_mmhg": 75, "temp_c": 36.8, "has_prior_history": True,
    "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
    "ambiguity_flag": False,
}

examples = [
    ("clear", base, 2, None),
    ("zero-history", base | {"has_prior_history": False}, 3, None),
    ("close probabilities", base, 2, {1:.15, 2:.36, 3:.34, 4:.10, 5:.05}),
]

for name, patient, proposed_esi, probabilities in examples:
    result = score_with_confidence(patient, proposed_esi, class_probabilities=probabilities)
    print(name, "->", result["badge"], result["uncertainty_reasons"])

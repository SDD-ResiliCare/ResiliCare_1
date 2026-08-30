"""Short patient-specific explanations for confidence-bearing ESI outputs."""

from __future__ import annotations

from typing import Any, Mapping

VITAL_LABELS = {
    "hr_bpm": ("Heart rate", " bpm"),
    "rr_bpm": ("Respiratory rate", " /min"),
    "spo2_pct": ("SpO₂", "%"),
    "sbp_mmhg": ("Systolic BP", " mmHg"),
    "temp_c": ("Temperature", "°C"),
}


def build_score_explanation(
    patient: Mapping[str, Any], result: Mapping[str, Any], safety: Mapping[str, Any]
) -> dict[str, Any]:
    """Return at most two prioritized, independently checkable explanation lines."""
    score, rules = result["display_score"], set(safety.get("matched_rule_ids", []))
    candidates: list[tuple[int, str, str]] = []

    def add(priority: int, rule_id: str, text: str) -> None:
        candidates.append((priority, rule_id, f"{score} — {text}"))

    if "IMMEDIATE.LIFE_SAVING_INTERVENTION" in rules:
        add(1, "IMMEDIATE.LIFE_SAVING_INTERVENTION", "an immediate life-saving intervention is flagged.")
    if "HIGH_RISK.TIME_SENSITIVE_PRESENTATION" in rules and "IMMEDIATE.LIFE_SAVING_INTERVENTION" not in rules:
        add(2, "HIGH_RISK.TIME_SENSITIVE_PRESENTATION", "the presentation is marked high-risk or time-sensitive.")
    if "REVIEW.WORSENING_VITALS" in rules:
        add(3, "REVIEW.WORSENING_VITALS", "repeat vitals are worsening, so urgent clinician re-assessment is required.")
    for index, pathway in enumerate(safety.get("ambiguous_presentations") or []):
        actions = " and ".join(pathway["required_safety_actions"][:2])
        add(4 + index, f"REVIEW.DIFFERENTIAL.{pathway['pathway_id']}", f"{pathway['label']} pathway matched; required safety actions: {actions}.")

    summary = safety.get("age_adjusted_vitals") or {}
    abnormal = []
    for name, vital in (summary.get("values") or {}).items():
        if vital["status"] in {"LOW", "HIGH"}:
            abnormal.append((abs(vital["signed_deviation"]), name, vital))
    for index, (_distance, name, vital) in enumerate(sorted(abnormal, reverse=True)):
        label, unit = VITAL_LABELS[name]
        bound = vital["reference"][0 if vital["status"] == "LOW" else 1]
        direction = "below the age-adjusted reference floor" if vital["status"] == "LOW" else "above the age-adjusted reference ceiling"
        add(10 + index, "REVIEW.BORDERLINE_VITALS", f"{label} {_value(vital['raw'])}{unit} is {direction} of {_value(bound)}{unit}.")

    missing = [name for name in ("hr_bpm", "rr_bpm", "spo2_pct", "sbp_mmhg", "dbp_mmhg", "temp_c") if patient.get(name) in {None, ""}]
    if missing:
        labels = ", ".join(VITAL_LABELS.get(name, ("Diastolic BP", "mmHg"))[0] for name in missing)
        add(20, "REVIEW.MISSING_VITALS", f"required observed vitals are missing: {labels}; confidence is reduced.")
    if "REVIEW.AMBIGUOUS_PRESENTATION" in rules:
        add(21, "REVIEW.AMBIGUOUS_PRESENTATION", "symptoms have competing plausible interpretations and require senior review.")
    if patient.get("has_prior_history") is False:
        add(22, "ZERO_HISTORY", "no prior history is on file; confidence was reduced and uncertainty widened toward higher acuity.")
    if "REVIEW.CONFLICTING_INFORMATION" in rules:
        add(23, "REVIEW.CONFLICTING_INFORMATION", "available clinical information conflicts and requires confirmation.")

    probabilities = result.get("class_probabilities") or {}
    if probabilities and ({"LOW_TOP_CLASS_PROBABILITY", "SMALL_TOP_TWO_GAP"} & set(result.get("uncertainty_reasons", []))):
        ranked = sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))
        add(24, "CLASSIFIER.PROBABILITY_DEFERRAL", f"top model probabilities are close ({ranked[0][1]:.0%} vs {ranked[1][1]:.0%}), so the case is deferred.")

    if not candidates:
        add(99, "NO_HARD_SAFETY_OVERRIDE", "no hard safety override fired; the displayed score comes from the upstream scorer and requires clinician confirmation.")
    chosen = sorted(candidates, key=lambda item: item[0])[:2]
    lines = [item[2] for item in chosen]
    return {
        "explanation_lines": lines,
        "explanation_text": " ".join(lines),
        "explanation_rule_ids": [item[1] for item in chosen],
        "explanation_method": "RULE_TEMPLATE",
    }


def _value(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else f"{number:g}"

"""Set-valued ESI output and transparent selective deferral.

This is conformal-style, not conformal prediction: no coverage claim is made until a
classifier and a separate calibration set exist.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from .explanations import build_score_explanation
from .history import prepare_history_context
from .safety import VITAL_FIELDS, apply_safety_ceiling, evaluate_safety_rules

VALID_ESI = set(range(1, 6))


@lru_cache(maxsize=1)
def load_confidence_config() -> dict[str, Any]:
    return json.loads(Path(__file__).with_name("confidence_config.json").read_text(encoding="utf-8"))


def score_with_confidence(
    patient: dict[str, Any],
    proposed_esi: int,
    *,
    safety_result: dict[str, Any] | None = None,
    class_probabilities: Mapping[int | str, float] | None = None,
    probabilities_calibrated: bool = False,
) -> dict[str, Any]:
    """Return a confidence-bearing ESI set; uncertain cases defer to senior review."""
    if proposed_esi not in VALID_ESI:
        raise ValueError("proposed_esi must be between 1 and 5")
    config = load_confidence_config()
    history_context = prepare_history_context(patient)
    safety = safety_result or evaluate_safety_rules(patient)
    displayed_esi = apply_safety_ceiling(proposed_esi, safety)
    levels, reasons = {displayed_esi}, []

    probabilities = _validate_probabilities(class_probabilities)
    if probabilities:
        ranked = sorted(probabilities, key=lambda level: (-probabilities[level], level))
        if ranked[0] != proposed_esi:
            raise ValueError("proposed_esi must equal the highest-probability class")
        top, second = probabilities[ranked[0]], probabilities[ranked[1]]
        gap, confidence, method = top - second, top, "classifier_selective_deferral"
        if top < config["top_probability_threshold"]:
            reasons.append("LOW_TOP_CLASS_PROBABILITY")
        if gap < config["top_two_gap_threshold"]:
            reasons.append("SMALL_TOP_TWO_GAP")
        if reasons:
            levels.update(range(min(ranked[:2]), max(ranked[:2]) + 1))
    else:
        gap, confidence, method = None, config["deterministic_base_score"], "evidence_completeness_heuristic"

    missing = [name for name in VITAL_FIELDS if patient.get(name) in {None, ""}]
    penalties = config["penalties"]
    evidence = [
        (patient.get("has_prior_history") is False, "ZERO_HISTORY", penalties["zero_history"]),
        (bool(missing), "MISSING_VITALS", min(len(missing) * penalties["missing_vitals_each"], penalties["missing_vitals_cap"])),
        (patient.get("relevant_history_missing") is True, "RELEVANT_HISTORY_MISSING", penalties["relevant_history_missing"]),
        (patient.get("ambiguity_flag") is True or bool(safety.get("ambiguous_presentations")), "AMBIGUOUS_PRESENTATION", penalties["ambiguous_presentation"]),
        (bool(patient.get("conflicting_information")), "CONFLICTING_INFORMATION", penalties["conflicting_information"]),
        ("REVIEW.BORDERLINE_VITALS" in safety.get("matched_rule_ids", []), "AGE_ADJUSTED_VITAL_DEVIATION", penalties["age_adjusted_vital_deviation"]),
    ]
    evidence_penalty = 0.0
    for present, reason, penalty in evidence:
        if present:
            reasons.append(reason)
            confidence -= penalty
            evidence_penalty += penalty

    explicit_range = safety.get("uncertainty_range") or []
    if explicit_range:
        levels.update(explicit_range)
        reasons.append("EXPLICIT_UNCERTAINTY_RANGE")
    if displayed_esi != proposed_esi:
        reasons.append("SAFETY_RULE_SCORER_DISAGREEMENT")

    confidence = round(max(0.0, min(1.0, confidence)), 3)
    defer = bool(reasons) or confidence < config["moderate_confidence_threshold"]
    asymmetric_reasons = {
        "ZERO_HISTORY", "MISSING_VITALS", "RELEVANT_HISTORY_MISSING", "AMBIGUOUS_PRESENTATION",
        "CONFLICTING_INFORMATION", "AGE_ADJUSTED_VITAL_DEVIATION", "SAFETY_RULE_SCORER_DISAGREEMENT",
    }
    if displayed_esi > 1 and asymmetric_reasons.intersection(reasons):
        levels.add(displayed_esi - 1)  # uncertainty is widened only toward higher acuity
    ceiling = safety.get("maximum_allowed_esi")
    if ceiling:
        levels = {level for level in levels if level <= ceiling}
    levels.add(displayed_esi)
    ordered = sorted(levels)
    label = "High" if confidence >= config["high_confidence_threshold"] else (
        "Moderate" if confidence >= config["moderate_confidence_threshold"] else "Low"
    )
    score_text = f"ESI {ordered[0]}" if len(ordered) == 1 else f"ESI {ordered[0]}-{ordered[-1]}"
    badge = f"{score_text} — Escalate for senior nurse review" if defer else f"{score_text} — {label} confidence"
    result = {
        "esi_set": ordered,
        "point_estimate": displayed_esi,
        "display_score": score_text,
        "confidence_score": confidence,
        "confidence_label": label,
        "confidence_method": method,
        "confidence_is_calibrated": bool(
            probabilities and probabilities_calibrated and evidence_penalty == 0 and displayed_esi == proposed_esi
        ),
        "evidence_penalty": round(evidence_penalty, 3),
        "coverage_guarantee": False,
        "class_probabilities": probabilities or None,
        "top_class_probability": max(probabilities.values()) if probabilities else None,
        "top_two_gap": round(gap, 3) if gap is not None else None,
        "defer_to_senior_nurse": defer,
        "review_action": "SENIOR_NURSE_REVIEW" if defer else "STANDARD_CLINICIAN_CONFIRMATION",
        "uncertainty_reasons": list(dict.fromkeys(reasons)),
        "badge": badge,
        "safety_ceiling": ceiling,
        "matched_safety_rules": safety.get("matched_rule_ids", []),
        "history_context": history_context,
        "ui_notices": [history_context["ui_notice"]] if history_context["ui_notice"] else [],
        "ambiguous_presentations": safety.get("ambiguous_presentations", []),
        "mandatory_safety_workup": bool(safety.get("ambiguous_presentations")),
    }
    result.update(build_score_explanation(patient, result, safety))
    return result


def _validate_probabilities(values: Mapping[int | str, float] | None) -> dict[int, float]:
    if values is None:
        return {}
    try:
        probabilities = {int(level): float(value) for level, value in values.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError("class_probabilities must map ESI 1-5 to numeric values") from exc
    if set(probabilities) != VALID_ESI or any(value < 0 or value > 1 for value in probabilities.values()):
        raise ValueError("class_probabilities must contain one value from 0 to 1 for every ESI level")
    if abs(sum(probabilities.values()) - 1.0) > 1e-6:
        raise ValueError("class_probabilities must sum to 1")
    return probabilities

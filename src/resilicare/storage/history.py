"""Missingness-aware preparation of prior-history features."""

from __future__ import annotations

import json
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Any, Mapping


@lru_cache(maxsize=1)
def load_missingness_config() -> dict[str, Any]:
    return json.loads((Path(__file__).parent.parent / "config" / "missingness_config.json").read_text(encoding="utf-8"))


def prepare_history_context(
    patient: Mapping[str, Any], history_features: Mapping[str, float] | None = None
) -> dict[str, Any]:
    """Create scorer-safe history features without guessing unavailable history."""
    has_history = patient.get("has_prior_history")
    if type(has_history) is not bool:
        raise ValueError("has_prior_history must be an explicit boolean")
    supplied = dict(history_features if history_features is not None else patient.get("history_features") or {})
    if not all(isinstance(name, str) and name for name in supplied):
        raise ValueError("history feature names must be non-empty strings")

    if has_history:
        features = {name: _number(value, name) for name, value in supplied.items()}
        weights = load_missingness_config()["history_vital_blend"]["history_available"]
        notice, basis = None, "OBSERVED_VITALS_AND_PRIOR_HISTORY"
    else:
        features = {name: 0.0 for name in supplied}  # discard stale values; never fabricate history
        weights = load_missingness_config()["history_vital_blend"]["zero_history"]
        notice = load_missingness_config()["zero_history_notice"]
        basis = "PRESENTING_VITALS_ONLY"

    return {
        "has_prior_history": has_history,
        "has_prior_history_feature": int(has_history),
        "history_missingness_indicator": int(not has_history),
        "history_feature_mask": int(has_history),
        "history_features": features,
        "history_features_zeroed": not has_history,
        "history_imputation_applied": False,
        "scorer_weights": dict(weights),
        "score_basis": basis,
        "ui_notice": notice,
    }


def weighted_risk_signal(observed_vitals_signal: float, history_signal: float | None, context: Mapping[str, Any]) -> float:
    """Blend scorer signals; a zero-history context makes history_signal irrelevant."""
    vitals = _number(observed_vitals_signal, "observed_vitals_signal")
    weights = context["scorer_weights"]
    if set(weights) != {"observed_vitals", "prior_history"} or any(value < 0 for value in weights.values()):
        raise ValueError("scorer_weights must contain non-negative observed_vitals and prior_history weights")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("scorer_weights must sum to 1")
    if weights["prior_history"] == 0:
        return round(vitals * weights["observed_vitals"], 6)
    history = _number(history_signal, "history_signal")
    return round(vitals * weights["observed_vitals"] + history * weights["prior_history"], 6)


def _number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number

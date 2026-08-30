"""Age-adjusted vital reference lookup and dimensionless deviation calculation."""

from __future__ import annotations

import json
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Any

VITALS = ("hr_bpm", "rr_bpm", "spo2_pct", "sbp_mmhg", "temp_c")


@lru_cache(maxsize=1)
def load_thresholds() -> dict[str, Any]:
    return json.loads(Path(__file__).with_name("vital_thresholds.json").read_text(encoding="utf-8"))


def get_age_profile(age_years: float | int) -> dict[str, Any]:
    """Return the single half-open age profile containing age_years."""
    try:
        age = float(age_years)
    except (TypeError, ValueError) as exc:
        raise ValueError("age_years must be numeric") from exc
    if not isfinite(age) or age < 0 or age >= 130:
        raise ValueError("age_years must be at least 0 and below 130")
    profile = next(item for item in load_thresholds()["profiles"] if item["min_age"] <= age < item["max_age"])
    profile = dict(profile)
    if age < 18:
        profile.update(load_thresholds()["pediatric_shared"])
    return profile


def normalize_vitals(patient: dict[str, Any]) -> dict[str, Any]:
    """Convert raw readings to signed distance outside the age-specific reference band.

    Deviation is zero inside the band. Outside it, distance is divided by band width;
    negative means below range and positive means above range.
    """
    profile = get_age_profile(patient.get("age_years"))
    values = {name: _deviation(patient.get(name), profile[name]) for name in VITALS}
    return {
        "threshold_version": load_thresholds()["version"],
        "profile_id": profile["id"],
        "age_bracket": profile["bracket"],
        "source_anchor": profile["anchor"],
        "requires_baseline_context": profile.get("requires_baseline_context", False),
        "values": values,
    }


def prepare_patient_vitals(patient: dict[str, Any]) -> dict[str, Any]:
    """Copy and enrich a patient so safety rules consume normalized, not raw, cut-offs."""
    prepared = dict(patient)
    summary = normalize_vitals(patient)
    prepared["age_adjusted_vitals"] = summary
    prepared["vital_deviations"] = summary["values"]
    prepared["borderline_vitals"] = bool(patient.get("borderline_vitals")) or any(
        item["status"] in {"LOW", "HIGH"} for item in summary["values"].values()
    )
    return prepared


def _deviation(raw: Any, bounds: list[float]) -> dict[str, Any]:
    if raw is None or raw == "":
        return {"raw": None, "reference": bounds, "status": "MISSING", "signed_deviation": None}
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"vital value {raw!r} must be numeric or missing") from exc
    low, high = bounds
    width = high - low
    if low <= value <= high:
        status, deviation = "WITHIN", 0.0
    elif value < low:
        status, deviation = "LOW", (value - low) / width
    else:
        status, deviation = "HIGH", (value - high) / width
    return {"raw": value, "reference": bounds, "status": status, "signed_deviation": round(deviation, 4)}

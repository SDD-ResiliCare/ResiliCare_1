"""Local prototype storage for stable patients and repeat triage encounters."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import Lock
from typing import Any, Mapping

HISTORY_SCOPE_LABEL = "History from previous ResiliCare visits only"
_LOCK = Lock()


def patient_uid_for_source(source_patient_id: str) -> str:
    """Map a synthetic source record to a stable ResiliCare patient identifier."""
    prefix, separator, number = source_patient_id.strip().partition("-")
    if prefix != "PT" or separator != "-" or not number.isdigit():
        raise ValueError("source_patient_id must use the PT-NNN synthetic format")
    return f"RC-P-{int(number):03d}"


def initialize_history_store(seed_path: str | Path, runtime_path: str | Path) -> Path:
    """Create the mutable local copy once, without overwriting prior demo history."""
    seed, runtime = Path(seed_path), Path(runtime_path)
    with _LOCK:
        if not runtime.exists():
            runtime.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(seed, runtime)
    return runtime


def load_history_store(path: str | Path) -> dict[str, Any]:
    store = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(store.get("patients"), dict) or not isinstance(store.get("encounters"), list):
        raise ValueError("history store must contain patients and encounters")
    return store


def _write_store(path: Path, store: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _vitals(patient: Mapping[str, Any]) -> dict[str, Any]:
    return {key: patient.get(key) for key in (
        "hr_bpm", "rr_bpm", "spo2_pct", "sbp_mmhg", "dbp_mmhg", "temp_c",
    )}


def upsert_current_encounter(
    path: str | Path, *, patient: Mapping[str, Any], ai_result: Mapping[str, Any],
    safety_badge: Mapping[str, Any], encounter_id: str, patient_uid: str,
) -> dict[str, Any]:
    """Persist the current synthetic encounter idempotently; retain clinician decisions."""
    target = Path(path)
    with _LOCK:
        store = load_history_store(target)
        source_id = str(patient.get("source_patient_id") or patient.get("patient_id"))
        store["patients"][patient_uid] = {
            "patient_uid": patient_uid, "source_patient_id": source_id,
            "age_years": patient.get("age_years"), "age_group": patient.get("age_group"),
            "sex_at_birth": patient.get("sex_at_birth"), "scheme": patient.get("scheme"),
            "synthetic": True,
        }
        current = next((x for x in store["encounters"] if x["encounter_id"] == encounter_id), None)
        decision = current.get("final_clinician_decision") if current else None
        encounter = {
            "encounter_id": encounter_id, "patient_uid": patient_uid, "source_patient_id": source_id,
            "occurred_at": patient.get("arrival_timestamp"), "chief_complaint": patient.get("chief_complaint"),
            "vitals": _vitals(patient),
            "suggested_esi": {key: ai_result.get(key) for key in (
                "display_score", "point_estimate", "esi_set", "confidence_score", "confidence_label", "badge",
            )},
            "final_clinician_decision": decision or {"decision": "pending", "final_esi": None},
            "safety_flags": [dict(safety_badge)], "synthetic": True,
        }
        if current:
            store["encounters"][store["encounters"].index(current)] = encounter
        else:
            store["encounters"].append(encounter)
        _write_store(target, store)
        return encounter


def previous_visits(path: str | Path, patient_uid: str, current_encounter_id: str | None = None) -> list[dict[str, Any]]:
    visits = [x for x in load_history_store(path)["encounters"]
              if x.get("patient_uid") == patient_uid and x.get("encounter_id") != current_encounter_id]
    return sorted(visits, key=lambda x: x.get("occurred_at") or "", reverse=True)


def record_history_override(path: str | Path, encounter_id: str, event: Mapping[str, Any]) -> dict[str, Any]:
    """Mirror an append-only override event into the encounter's current final decision."""
    target = Path(path)
    with _LOCK:
        store = load_history_store(target)
        encounter = next((x for x in store["encounters"] if x["encounter_id"] == encounter_id), None)
        if encounter is None:
            raise ValueError("unknown encounter_id in local history")
        encounter["final_clinician_decision"] = {
            "decision": "override", "final_esi": event["overridden_esi"],
            "clinician_id": event["clinician_id"], "decided_at": event["timestamp"],
            "reason": event["reason"], "audit_event_id": event["event_id"],
        }
        _write_store(target, store)
        return encounter


def encounter_with_patient(path: str | Path, encounter_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    store = load_history_store(path)
    encounter = next((x for x in store["encounters"] if x["encounter_id"] == encounter_id), None)
    if encounter is None:
        raise ValueError("unknown encounter_id")
    return store["patients"][encounter["patient_uid"]], encounter

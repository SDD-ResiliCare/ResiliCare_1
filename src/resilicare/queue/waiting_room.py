"""Waiting-room reassessment timer and vital-deterioration queue loop."""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from resilicare.engine.confidence import score_with_confidence
from resilicare.engine.safety import VALID_ESI, VITAL_FIELDS, append_audit_event, evaluate_safety_rules
from resilicare.engine.vitals import VITALS, normalize_vitals

Rescorer = Callable[[dict[str, Any], int], int]


@lru_cache(maxsize=1)
def load_waiting_room_config() -> dict[str, Any]:
    return json.loads((Path(__file__).parent.parent / "config" / "waiting_room_config.json").read_text(encoding="utf-8"))


def create_waiting_entry(patient: Mapping[str, Any], current_esi: int, entered_at: datetime | str) -> dict[str, Any]:
    """Create a serializable waiting-list entry without changing the patient record."""
    if current_esi not in VALID_ESI or not patient.get("patient_id"):
        raise ValueError("a patient_id and ESI level from 1 to 5 are required")
    timestamp = _time(entered_at).isoformat()
    return {
        "patient_id": patient["patient_id"], "patient": dict(patient), "initial_esi": current_esi,
        "current_esi": current_esi, "entered_at": timestamp, "last_assessed_at": timestamp,
        "status": "WAITING", "reassessment_required": False, "reassessment_count": 0,
        "queue_priority_boost": 0, "queue_rank": None,
    }


def tick_waiting_room(
    entries: Iterable[Mapping[str, Any]],
    now: datetime | str,
    *,
    vital_updates: Mapping[str, Mapping[str, Any]] | None = None,
    rescorer: Rescorer | None = None,
    log_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Run one deterministic tick and return the re-ranked waiting list."""
    current_time, updates, pending = _time(now), vital_updates or {}, []
    sources = list(entries)
    patient_ids = [item["patient_id"] for item in sources]
    if len(patient_ids) != len(set(patient_ids)):
        raise ValueError("waiting-room patient_id values must be unique")
    unknown_updates = set(updates) - set(patient_ids)
    if unknown_updates:
        raise ValueError("vital update supplied for unknown patient: " + ", ".join(sorted(unknown_updates)))
    queue = []
    for old_rank, source in enumerate(sources, 1):
        entry, before = dict(source), dict(source["patient"])
        patient_id, current_esi = entry["patient_id"], entry["current_esi"]
        update = dict(updates.get(patient_id, {}))
        invalid = set(update) - set(VITAL_FIELDS)
        if invalid:
            raise ValueError("waiting-room updates may contain vitals only: " + ", ".join(sorted(invalid)))
        after, changes = before | update, detect_vital_deterioration(before, before | update) if update else []
        elapsed = (current_time - _time(entry["last_assessed_at"])).total_seconds() / 60
        if elapsed < 0:
            raise ValueError("now cannot be earlier than last_assessed_at")
        ceiling = _ceiling(current_esi)
        reasons = []
        if current_esi == 1 and not entry.get("reassessment_required"):
            reasons.append("ESI_1_NOT_WAITING_ROOM_ELIGIBLE")
        elif elapsed > ceiling and not entry.get("reassessment_required"):
            reasons.append("REASSESSMENT_INTERVAL_EXCEEDED")
        if changes:
            reasons.append("VITALS_WORSENED")

        entry["patient"] = after
        if update and not changes:
            entry["last_assessed_at"] = current_time.isoformat()
        if reasons:
            after["worsening_vitals"] = bool(changes) or bool(after.get("worsening_vitals"))
            proposed = rescorer(after, current_esi) if rescorer else current_esi
            if proposed not in VALID_ESI:
                raise ValueError("rescorer must return an ESI level from 1 to 5")
            proposed = min(current_esi, proposed)  # waiting-room automation never downgrades acuity
            safety = evaluate_safety_rules(after)
            result = score_with_confidence(after, proposed, safety_result=safety)
            entry.update({
                "patient": after, "current_esi": min(current_esi, result["point_estimate"]),
                "status": "REASSESSMENT_REQUIRED", "reassessment_required": True,
                "reassessment_count": entry.get("reassessment_count", 0) + 1,
                "queue_priority_boost": max(entry.get("queue_priority_boost", 0), 2 if changes else 1),
                "last_alerted_at": current_time.isoformat(), "latest_confidence": result,
                "waiting_room_alert": (
                    "ESI 1 is not eligible to wait — immediate care required."
                    if current_esi == 1 else
                    "Vitals worsened — urgent clinician re-assessment required."
                    if changes else "Re-assessment interval exceeded — move patient forward in queue."
                ),
            })
            pending.append((entry, old_rank, {
                "evaluated_at": current_time.isoformat(),
                "trigger_reasons": reasons, "previous_esi": current_esi, "updated_esi": entry["current_esi"],
                "total_wait_minutes": round((current_time - _time(entry["entered_at"])).total_seconds() / 60, 2),
                "minutes_since_last_assessment": round(elapsed, 2), "reassessment_ceiling_minutes": ceiling,
                "vital_changes": changes, "confidence_badge": result["badge"],
            }))
        queue.append(entry)

    queue.sort(key=lambda item: (item["current_esi"], not item["reassessment_required"], -item["queue_priority_boost"], item["entered_at"]))
    for rank, entry in enumerate(queue, 1):
        entry["queue_rank"] = rank
    for entry, old_rank, event in pending:
        event.update({"previous_queue_rank": old_rank, "new_queue_rank": entry["queue_rank"], "queue_moved_forward": entry["queue_rank"] < old_rank})
        if log_path:
            append_audit_event(log_path, "waiting_room_retriage", entry["patient_id"], event)
    return queue


def complete_reassessment(
    entry: Mapping[str, Any], completed_at: datetime | str, clinician_id: str, *, 
    overridden_esi: int | None = None, log_path: str | Path | None = None
) -> dict[str, Any]:
    """Clear an active alert only after an identified clinician completes reassessment."""
    if not entry.get("reassessment_required") or not clinician_id.strip():
        raise ValueError("an active alert and clinician_id are required")
    timestamp, updated = _time(completed_at), dict(entry)
    if timestamp < _time(updated["last_alerted_at"]):
        raise ValueError("completed_at cannot precede the alert")
        
    if overridden_esi is not None:
        if overridden_esi not in VALID_ESI:
            raise ValueError("ESI must be from 1 to 5")
        updated["current_esi"] = overridden_esi

    updated.update({
        "status": "WAITING", "reassessment_required": False, "queue_priority_boost": 0,
        "last_assessed_at": timestamp.isoformat(), "last_reassessed_by": clinician_id.strip(),
        "waiting_room_alert": None,
    })
    if log_path:
        append_audit_event(log_path, "waiting_room_reassessment_completed", updated["patient_id"], {
            "completed_at": timestamp.isoformat(), "clinician_id": clinician_id.strip(),
            "current_esi": updated["current_esi"], "reassessment_count": updated["reassessment_count"],
        })
    return updated


def detect_vital_deterioration(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Compare age-normalized deviations; raw adult thresholds are never used here."""
    old, new = normalize_vitals(dict(before))["values"], normalize_vitals(dict(after))["values"]
    delta = load_waiting_room_config()["normalized_deterioration_delta"]
    changes = []
    for name in VITALS:
        previous, current = old[name], new[name]
        old_distance = abs(previous["signed_deviation"] or 0)
        new_distance = abs(current["signed_deviation"] or 0)
        worsened = current["status"] == "MISSING" and previous["status"] != "MISSING"
        worsened |= current["status"] in {"LOW", "HIGH"} and (
            previous["status"] == "WITHIN" or new_distance - old_distance >= delta
        )
        if worsened:
            changes.append({
                "vital": name, "previous": previous["raw"], "current": current["raw"],
                "previous_status": previous["status"], "current_status": current["status"],
                "normalized_change": round(new_distance - old_distance, 4),
            })
    return changes


def _ceiling(esi: int) -> float:
    return float(load_waiting_room_config()["reassessment_ceiling_minutes"][str(esi)])


def _time(value: datetime | str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamps must be datetime objects or ISO-8601 strings") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return parsed

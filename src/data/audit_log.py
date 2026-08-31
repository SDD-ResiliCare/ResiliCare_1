"""Append-only audit records for AI suggestions and clinician overrides."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from src.core.safety_rules import append_audit_event

REASON_CODES = {
    "CLINICAL_DETERIORATION": "Clinical deterioration",
    "ADDITIONAL_HISTORY": "Additional history became available",
    "EXAMINATION_FINDINGS": "Clinical examination findings",
    "VITAL_SIGN_CONCERN": "Vital-sign concern",
    "RESOURCE_NEED_CHANGE": "Expected resource need changed",
    "AI_DISAGREEMENT": "Clinician disagrees with AI assessment",
    "OTHER": "Other",
}

CLINICIAN_ROLES = {"RN", "MD"}


def validate_clinician_identity(clinician_id: str, clinician_role: str) -> tuple[str, str]:
    """Validate the lightweight accountability identity used by this local prototype."""
    if not isinstance(clinician_id, str) or not isinstance(clinician_role, str):
        raise ValueError("clinician_id and clinician_role are required")
    clinician_id, clinician_role = clinician_id.strip(), clinician_role.strip().upper()
    if not clinician_id or clinician_role not in CLINICIAN_ROLES:
        raise ValueError("clinician_role must be RN or MD and clinician_id must be non-empty")
    if len(clinician_id) > 80:
        raise ValueError("clinician_id is too long")
    return clinician_id, clinician_role


def record_clinician_override(
    log_path: str | Path,
    *,
    patient_id: str,
    clinician_id: str,
    clinician_role: str,
    original_ai_result: Mapping[str, Any],
    overridden_esi: int,
    reason_code: str,
    reason_text: str,
) -> dict[str, Any]:
    """Validate and append one override; no update/delete operation is exposed."""
    patient_id, reason_text = patient_id.strip(), reason_text.strip()
    clinician_id, clinician_role = validate_clinician_identity(clinician_id, clinician_role)
    point = original_ai_result.get("point_estimate")
    confidence = original_ai_result.get("confidence_score")
    if not patient_id:
        raise ValueError("patient_id is required")
    if type(point) is not int or type(overridden_esi) is not int or point not in range(1, 6) or overridden_esi not in range(1, 6):
        raise ValueError("original and overridden ESI must be between 1 and 5")
    if overridden_esi == point:
        raise ValueError("overridden ESI must differ from the AI point estimate")
    if reason_code not in REASON_CODES or not reason_text:
        raise ValueError("a valid reason_code and free-text reason are required")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise ValueError("original AI confidence is required")
    esi_set = list(original_ai_result.get("esi_set") or [point])
    if not esi_set or any(type(level) is not int or level not in range(1, 6) for level in esi_set):
        raise ValueError("original AI ESI set is invalid")
    if len(reason_text) > 2000:
        raise ValueError("reason_text is too long")

    return append_audit_event(log_path, "clinician_esi_override", patient_id, {
        "clinician_id": clinician_id,
        "clinician_role": clinician_role,
        "decision": "override",
        "original_ai": {
            "display_score": original_ai_result.get("display_score"),
            "point_estimate": point,
            "esi_set": esi_set,
            "confidence_score": confidence,
            "confidence_label": original_ai_result.get("confidence_label"),
            "confidence_method": original_ai_result.get("confidence_method"),
            "badge": original_ai_result.get("badge"),
            "explanation_text": original_ai_result.get("explanation_text"),
            "explanation_rule_ids": list(original_ai_result.get("explanation_rule_ids") or []),
            "matched_safety_rules": list(original_ai_result.get("matched_safety_rules") or []),
            "mandatory_safety_workup": bool(original_ai_result.get("mandatory_safety_workup")),
            "ambiguous_presentations": list(original_ai_result.get("ambiguous_presentations") or []),
        },
        "overridden_esi": overridden_esi,
        "override_direction": "escalation" if overridden_esi < point else "de_escalation",
        "reason": {"code": reason_code, "label": REASON_CODES[reason_code], "free_text": reason_text},
    })


def read_audit_events(
    log_path: str | Path, *, patient_id: str | None = None, event_type: str | None = None
) -> list[dict[str, Any]]:
    """Read, optionally filter, but never alter the JSONL ledger."""
    path = Path(log_path)
    if not path.exists():
        return []
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid audit JSON on line {line_number}") from exc
        if (patient_id is None or event.get("patient_id") == patient_id) and (
            event_type is None or event.get("event_type") == event_type
        ):
            events.append(event)
    return events


def compute_override_rates(
    log_path: str | Path, flag_threshold: float = 0.15, minimum_evaluations: int = 10,
) -> list[dict[str, Any]]:
    """
    Compute a rolling override rate per rule (Task 15).
    Tracks 'escalating' and 'de-escalating' overrides separately.
    If the de-escalating override rate crosses the threshold (e.g., 15%), it is flagged for review.
    """
    if minimum_evaluations < 1:
        raise ValueError("minimum_evaluations must be at least 1")
    rule_evaluations = {}
    rule_escalations = {}
    rule_de_escalations = {}

    events = read_audit_events(log_path)
    for event in events:
        event_type = event.get("event_type")
        
        if event_type == "provisional_safety_result":
            # Count the rules that were triggered in the provisional evaluation
            result = event.get("result", {})
            rule_ids = result.get("matched_safety_rules") or result.get("explanation_rule_ids", [])
            for rule_id in rule_ids:
                rule_evaluations[rule_id] = rule_evaluations.get(rule_id, 0) + 1
                
        elif event_type == "clinician_esi_override":
            # Track the direction of the override against the rules
            original = event.get("original_ai", {})
            rule_ids = original.get("matched_safety_rules") or original.get("explanation_rule_ids", [])
            direction = event.get("override_direction")
            for rule_id in rule_ids:
                if direction == "escalation":
                    rule_escalations[rule_id] = rule_escalations.get(rule_id, 0) + 1
                elif direction == "de_escalation":
                    rule_de_escalations[rule_id] = rule_de_escalations.get(rule_id, 0) + 1

    rates = []
    # Every rule that has ever been evaluated
    all_rules = set(rule_evaluations.keys()) | set(rule_escalations.keys()) | set(rule_de_escalations.keys())
    
    for rule_id in all_rules:
        total_evals = rule_evaluations.get(rule_id, 0)
        # If a rule was overridden but we missed its provisional log, adjust the denominator safely
        total = max(total_evals, rule_escalations.get(rule_id, 0) + rule_de_escalations.get(rule_id, 0))
        
        if total == 0:
            continue
            
        esc_count = rule_escalations.get(rule_id, 0)
        desc_count = rule_de_escalations.get(rule_id, 0)
        
        esc_rate = esc_count / total
        desc_rate = desc_count / total
        
        rates.append({
            "rule_id": rule_id,
            "total_evaluations": total,
            "escalation_count": esc_count,
            "escalation_rate": esc_rate,
            "de_escalation_count": desc_count,
            "de_escalation_rate": desc_rate,
            "minimum_sample_size": minimum_evaluations,
            "minimum_sample_met": total >= minimum_evaluations,
            "flagged_for_review": total >= minimum_evaluations and desc_rate >= flag_threshold,
        })

    # Sort so the highest de-escalation rate (most dangerous) is first
    return sorted(rates, key=lambda x: x["de_escalation_rate"], reverse=True)


def verify_audit_chain(log_path: str | Path) -> dict[str, Any]:
    """Verify the tamper-evident chain added to new audit events.

    Older pre-chain entries are accepted as a legacy prefix. The first chained event is
    anchored to an empty previous hash so a legacy file can be upgraded append-only.
    """
    expected_previous: str | None = None
    chained_events = 0
    for event in read_audit_events(log_path):
        event_hash = event.get("event_hash")
        previous_hash = event.get("previous_event_hash")
        if event_hash is None and previous_hash is None:
            continue
        if not isinstance(event_hash, str) or previous_hash != expected_previous:
            return {"valid": False, "checked_events": chained_events, "error": "invalid hash chain linkage"}
        payload = {key: value for key, value in event.items() if key not in {"event_hash", "previous_event_hash"}}
        digest = _chain_hash(expected_previous, payload)
        if event_hash != digest:
            return {"valid": False, "checked_events": chained_events, "error": "event hash mismatch"}
        expected_previous, chained_events = event_hash, chained_events + 1
    return {"valid": True, "checked_events": chained_events, "last_event_hash": expected_previous}


def redacted_compliance_events(log_path: str | Path) -> dict[str, Any]:
    """Return a purpose-limited view with no free text or direct patient identifiers."""
    entries = []
    for event in read_audit_events(log_path):
        redacted = {
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "timestamp": event["timestamp"],
            "patient_pseudonym": hashlib.sha256(event["patient_id"].encode()).hexdigest()[:12],
            "event_hash": event.get("event_hash"),
            "previous_event_hash": event.get("previous_event_hash"),
        }
        if event.get("clinician_role"):
            redacted["clinician_role"] = event["clinician_role"]
        if event.get("reason", {}).get("code"):
            redacted["reason_code"] = event["reason"]["code"]
        entries.append(redacted)
    return {"scope": "redacted local prototype compliance view", "events": entries, "integrity": verify_audit_chain(log_path)}


def _chain_hash(previous_hash: str | None, event: Mapping[str, Any]) -> str:
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{previous_hash or ''}|{payload}".encode("utf-8")).hexdigest()

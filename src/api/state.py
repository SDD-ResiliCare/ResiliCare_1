"""Server state management."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from src.adapters.clinical_routing import suggest_scheme_route
from src.adapters.hospital_config import assess_hospital_operations, get_hospital_profile
from src.core.safety_rules import log_provisional_result
from src.data.clinical_confirmation import confirmation_status, pending_confirmation
from src.data.history_store import initialize_history_store, upsert_current_encounter
from src.workflows.combat_mode import combat_mode_state
from src.workflows.queue_surge import load_simulated_patients
from src.api.models import build_demo_suggestions, build_queue_snapshot


class ServerState:
    def __init__(self, project_root: Path, log_path: Path, history_path: Path | None, confirmation_timeout_seconds: int):
        self.project_root = project_root
        self.log_path = log_path
        self.history_path = history_path
        self.confirmation_timeout_seconds = confirmation_timeout_seconds
        
        dataset_path = project_root / "data" / "simulated_patients.json"
        self.patient_list = load_simulated_patients(dataset_path)
        self.suggestions = build_demo_suggestions(project_root)
        self.patients = {item["patient_id"]: item for item in self.patient_list}
        
        self.queue_lock = Lock()
        self.queue_holder = {"snapshot": build_queue_snapshot(self.patient_list, 1)}
        self.profile_holder = {"profile_id": "urban_trauma_center"}
        self.confirmation_holder = {"records": {}, "unlocked_encounters": set(), "provisional_keys": set()}
        
        self.history_runtime = initialize_history_store(
            project_root / "data" / "resilicare_history_seed.json",
            history_path or project_root / "data" / "resilicare_history_runtime.json",
        )

        self.refresh_snapshot(self.queue_holder["snapshot"], self.profile_holder["profile_id"])
        self.refresh_suggestions(self.profile_holder["profile_id"], self.queue_holder["snapshot"]["queue_length"])

    def apply_profile(self, items: list[dict], queue_length: int, profile_id: str) -> None:
        for item in items:
            item["hospital_operations"] = assess_hospital_operations(
                item["patient"], item["ai_result"], profile_id, queue_length=queue_length,
            )

    def profile_summary(self, profile_id: str) -> dict:
        profile = get_hospital_profile(profile_id)
        return {"profile_id": profile_id, "display_name": profile["display_name"],
                "facility_type": profile["facility_type"], "combat_mode_queue_threshold": profile["combat_mode_queue_threshold"],
                "simulated": True}

    def persist_items(self, items: list[dict]) -> None:
        for item in items:
            upsert_current_encounter(
                self.history_runtime, patient=item["patient"], ai_result=item["ai_result"],
                safety_badge=item["safety_badge"], encounter_id=item["encounter_id"],
                patient_uid=item["patient_uid"],
            )

    def confirmation_for(self, item: dict, *, now: datetime | None = None) -> dict:
        encounter_id = item["encounter_id"]
        record = self.confirmation_holder["records"].get(encounter_id)
        if record is None:
            issued = now or datetime.now(timezone.utc)
            record = pending_confirmation(encounter_id=encounter_id, now=issued)
            record["expires_at"] = (issued + timedelta(seconds=self.confirmation_timeout_seconds)).isoformat()
            self.confirmation_holder["records"][encounter_id] = record
        current = confirmation_status(record, now=now)
        if current["status"] == "TIMED_OUT_SENIOR_REVIEW" and record.get("status") != "TIMED_OUT_SENIOR_REVIEW":
            log_provisional_result(self.log_path, item["patient_id"], {
                **item["ai_result"], "confirmation_timeout": True, "confirmation": current,
            })
        self.confirmation_holder["records"][encounter_id] = current
        return current

    def route_for(self, item: dict, confirmation: dict) -> dict:
        route = suggest_scheme_route(
            item["patient"], item["ai_result"]["point_estimate"],
            clinician_confirmed=bool(confirmation.get("routing_allowed")),
            confidence_result=item["ai_result"], operational_context=item.get("hospital_operations"),
        )
        route["clinical_confirmation"] = confirmation["status"]
        if confirmation["status"] == "TIMED_OUT_SENIOR_REVIEW":
            route.update({
                "status": "CLINICAL_ROUTING_BLOCKED",
                "message": "Confirmation timed out; retain the safety-capped ESI and obtain senior review before routing.",
                "blockers": list(dict.fromkeys(route["blockers"] + ["CONFIRMATION_TIMED_OUT"])),
            })
        return route

    def attach_runtime_state(self, items: list[dict], queue_length: int, profile_id: str) -> None:
        for item in items:
            confirmation = self.confirmation_for(item)
            item["clinical_confirmation"] = confirmation
            item["routing_assessment"] = self.route_for(item, confirmation)

    def audit_provisional_items(self, items: list[dict]) -> None:
        for item in items:
            fingerprint = json.dumps({"encounter_id": item["encounter_id"], "ai_result": item["ai_result"]}, sort_keys=True)
            if fingerprint not in self.confirmation_holder["provisional_keys"]:
                log_provisional_result(self.log_path, item["patient_id"], item["ai_result"])
                self.confirmation_holder["provisional_keys"].add(fingerprint)

    def refresh_snapshot(self, snapshot: dict, profile_id: str, manually_declared: bool = False) -> dict:
        threshold = get_hospital_profile(profile_id)["combat_mode_queue_threshold"]
        snapshot["combat_mode"] = combat_mode_state(
            snapshot["queue_length"], manually_declared=manually_declared, threshold=threshold,
        )
        self.apply_profile(snapshot["items"], snapshot["queue_length"], profile_id)
        self.attach_runtime_state(snapshot["items"], snapshot["queue_length"], profile_id)
        snapshot["hospital_profile"] = self.profile_summary(profile_id)
        self.persist_items(snapshot["items"])
        self.audit_provisional_items(snapshot["items"])
        return snapshot

    def refresh_suggestions(self, profile_id: str, queue_length: int) -> None:
        suggestions_list = list(self.suggestions.values())
        self.apply_profile(suggestions_list, queue_length, profile_id)
        self.attach_runtime_state(suggestions_list, queue_length, profile_id)
        self.audit_provisional_items(suggestions_list)

    def queue_snapshot(self) -> dict:
        with self.queue_lock:
            return deepcopy(self.queue_holder["snapshot"])

    def replace_queue(self, multiplier: int, manually_declared: bool = False) -> dict:
        with self.queue_lock:
            profile_id = self.profile_holder["profile_id"]
            self.confirmation_holder["records"].clear()
            self.confirmation_holder["unlocked_encounters"].clear()
        threshold = get_hospital_profile(profile_id)["combat_mode_queue_threshold"]
        snapshot = build_queue_snapshot(self.patient_list, multiplier, manually_declared, threshold)
        self.refresh_snapshot(snapshot, profile_id, manually_declared)
        self.refresh_suggestions(profile_id, snapshot["queue_length"])
        with self.queue_lock:
            self.queue_holder["snapshot"] = snapshot
        return self.render_queue_snapshot(snapshot)

    def switch_profile(self, profile_id: str) -> dict:
        self.profile_summary(profile_id)  # validates before mutating state
        with self.queue_lock:
            snapshot = self.queue_holder["snapshot"]
            self.profile_holder["profile_id"] = profile_id
            self.refresh_snapshot(snapshot, profile_id, snapshot["combat_mode"]["trigger"] == "MANUAL")
            self.refresh_suggestions(profile_id, snapshot["queue_length"])
            return self.render_queue_snapshot(snapshot)

    def current_suggestion(self, patient_id: str | None) -> dict | None:
        current = next((item for item in self.queue_snapshot()["items"] if item["patient_id"] == patient_id), None)
        return current or deepcopy(self.suggestions.get(patient_id))

    def compact_combat_item(self, item: dict) -> dict:
        return {
            "patient_id": item["patient_id"], "encounter_id": item["encounter_id"],
            "safety_badge": item["safety_badge"],
            "explanation_clause": (item["ai_result"].get("explanation_lines") or [item["safety_badge"]["reason"]])[0],
            "combat_mode_locked": True,
        }

    def render_queue_snapshot(self, snapshot: dict) -> dict:
        rendered = deepcopy(snapshot)
        for item in rendered["items"]:
            confirmation = self.confirmation_for(item)
            item["clinical_confirmation"] = confirmation
            item["routing_assessment"] = self.route_for(item, confirmation)
        if rendered["combat_mode"]["active"]:
            rendered["items"] = [
                item if item["encounter_id"] in self.confirmation_holder["unlocked_encounters"] else self.compact_combat_item(item)
                for item in rendered["items"]
            ]
        rendered.pop("queue_entries", None)
        return rendered

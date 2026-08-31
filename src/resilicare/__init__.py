from .engine.safety import (
    append_audit_event,
    apply_safety_ceiling,
    evaluate_safety_rules,
    log_clinician_decision,
    log_provisional_result,
)
from .engine.confidence import load_confidence_config, score_with_confidence
from .storage.audit import REASON_CODES, read_audit_events, record_clinician_override
from .engine.explanations import build_score_explanation
from .engine.differentials import load_ambiguous_presentation_table, match_ambiguous_presentations
from .storage.history import load_missingness_config, prepare_history_context, weighted_risk_signal
from .queue.waiting_room import complete_reassessment, create_waiting_entry, detect_vital_deterioration, load_waiting_room_config, tick_waiting_room
from .engine.vitals import get_age_profile, load_thresholds, normalize_vitals, prepare_patient_vitals
from .integrations.routing import VALID_SCHEMES, load_facility_table, suggest_scheme_route
from .queue.surge import BASELINE_ARRIVALS_PER_WINDOW, COMBAT_MODE_QUEUE_THRESHOLD, SURGE_MULTIPLIER, load_simulated_patients, replay_arrivals
from .queue.combat import combat_mode_state, critical_safety_badge, record_combat_acknowledgement
from .storage.history_store import HISTORY_SCOPE_LABEL, encounter_with_patient, initialize_history_store, patient_uid_for_source, previous_visits, record_history_override, upsert_current_encounter
from .integrations.fhir_export import FHIR_SHAPED_DISCLAIMER, build_fhir_shaped_bundle
from .integrations.hospital_config import PROFILE_IDS, assess_hospital_operations, get_hospital_profile, load_hospital_profiles

x = [
    "apply_safety_ceiling",
    "evaluate_safety_rules",
    "log_clinician_decision",
    "log_provisional_result",
    "get_age_profile",
    "load_thresholds",
    "normalize_vitals",
    "prepare_patient_vitals",
    "load_confidence_config",
    "score_with_confidence",
    "load_missingness_config",
    "prepare_history_context",
    "weighted_risk_signal",
    "append_audit_event",
    "create_waiting_entry",
    "detect_vital_deterioration",
    "load_waiting_room_config",
    "tick_waiting_room",
    "complete_reassessment",
    "REASON_CODES",
    "read_audit_events",
    "record_clinician_override",
    "build_score_explanation",
    "load_ambiguous_presentation_table",
    "match_ambiguous_presentations",
    "VALID_SCHEMES",
    "load_facility_table",
    "suggest_scheme_route",
    "BASELINE_ARRIVALS_PER_WINDOW",
    "COMBAT_MODE_QUEUE_THRESHOLD",
    "SURGE_MULTIPLIER",
    "load_simulated_patients",
    "replay_arrivals",
    "combat_mode_state",
    "critical_safety_badge",
    "record_combat_acknowledgement",
    "HISTORY_SCOPE_LABEL",
    "FHIR_SHAPED_DISCLAIMER",
    "patient_uid_for_source",
    "initialize_history_store",
    "upsert_current_encounter",
    "previous_visits",
    "record_history_override",
    "encounter_with_patient",
    "build_fhir_shaped_bundle",
    "PROFILE_IDS",
    "load_hospital_profiles",
    "get_hospital_profile",
    "assess_hospital_operations",
]

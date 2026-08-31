import sys
from pathlib import Path

audit_path = Path("src/resilicare/storage/audit.py")
content = audit_path.read_text(encoding="utf-8")

if "compute_override_rates" not in content:
    content += """

def compute_override_rates(log_path: str | Path, flag_threshold: float = 0.15) -> list[dict[str, Any]]:
    \"\"\"
    Compute a rolling override rate per rule (Task 15).
    Tracks 'escalating' and 'de-escalating' overrides separately.
    If the de-escalating override rate crosses the threshold (e.g., 15%), it is flagged for review.
    \"\"\"
    rule_evaluations = {}
    rule_escalations = {}
    rule_de_escalations = {}

    events = read_audit_events(log_path)
    for event in events:
        event_type = event.get("event_type")
        
        if event_type == "provisional_safety_result":
            # Count the rules that were triggered in the provisional evaluation
            result = event.get("result", {})
            rule_ids = result.get("explanation_rule_ids", [])
            for rule_id in rule_ids:
                rule_evaluations[rule_id] = rule_evaluations.get(rule_id, 0) + 1
                
        elif event_type == "clinician_esi_override":
            # Track the direction of the override against the rules
            rule_ids = event.get("original_ai", {}).get("explanation_rule_ids", [])
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
            "flagged_for_review": desc_rate >= flag_threshold
        })

    # Sort so the highest de-escalation rate (most dangerous) is first
    return sorted(rates, key=lambda x: x["de_escalation_rate"], reverse=True)
"""
    audit_path.write_text(content, encoding="utf-8")
    print("Added compute_override_rates to audit.py")
else:
    print("compute_override_rates already exists")

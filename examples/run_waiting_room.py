import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from resilicare import create_waiting_entry, tick_waiting_room

start = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
base = {
    "age_years": 30, "has_prior_history": True, "hr_bpm": 80, "rr_bpm": 16,
    "spo2_pct": 99, "sbp_mmhg": 120, "dbp_mmhg": 75, "temp_c": 36.8,
    "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
    "ambiguity_flag": False,
}
queue = [
    create_waiting_entry(base | {"patient_id": "PT-STABLE"}, 3, start),
    create_waiting_entry(base | {"patient_id": "PT-WORSE"}, 4, start),
]

with tempfile.TemporaryDirectory() as directory:
    log = Path(directory) / "audit.jsonl"
    queue = tick_waiting_room(
        queue, start + timedelta(minutes=5),
        vital_updates={"PT-WORSE": {"hr_bpm": 125, "spo2_pct": 92}}, log_path=log,
    )
    for entry in queue:
        print(entry["queue_rank"], entry["patient_id"], entry["current_esi"], entry.get("waiting_room_alert"))
    print(json.loads(log.read_text(encoding="utf-8")))

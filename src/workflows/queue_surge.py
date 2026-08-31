"""Deterministic 1x/3x arrival replay used by the surge and Combat Mode demos."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.workflows.waiting_room import create_waiting_entry, tick_waiting_room

BASELINE_ARRIVALS_PER_WINDOW = 7
SURGE_MULTIPLIER = 3
ARRIVAL_WINDOW_MINUTES = 15
COMBAT_MODE_QUEUE_THRESHOLD = 20


def load_simulated_patients(dataset_path: str | Path) -> list[dict[str, Any]]:
    patients = json.loads(Path(dataset_path).read_text(encoding="utf-8"))["patients"]
    if not patients:
        raise ValueError("surge simulation requires at least one patient")
    return patients


def replay_arrivals(
    patients: Iterable[Mapping[str, Any]], *, multiplier: int,
    start_time: datetime | None = None, deteriorate_first_patient: bool = False,
) -> dict[str, Any]:
    """Replay 7 or 21 uniquely identified encounters in the same 15-minute window."""
    if multiplier not in {1, SURGE_MULTIPLIER}:
        raise ValueError("multiplier must be 1 or 3")
    source = [dict(item) for item in patients]
    if not source:
        raise ValueError("patients cannot be empty")
    start = start_time or datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("start_time must include a timezone")

    source.sort(key=lambda item: (-int(item["reference_esi"]), item["patient_id"]))
    count = BASELINE_ARRIVALS_PER_WINDOW * multiplier
    entries = []
    for index in range(count):
        template = source[index % len(source)]
        patient = template | {
            "patient_id": f"Q-{index + 1:03d}",
            "source_patient_id": template["patient_id"],
            "simulation_replay": index >= len(source),
        }
        arrived_at = start + timedelta(minutes=index * ARRIVAL_WINDOW_MINUTES / count)
        entries.append(create_waiting_entry(patient, int(patient["reference_esi"]), arrived_at))

    evaluated_at = start + timedelta(minutes=ARRIVAL_WINDOW_MINUTES)
    before = tick_waiting_room(entries, evaluated_at)
    target_id = entries[0]["patient_id"]
    before_rank = next(item["queue_rank"] for item in before if item["patient_id"] == target_id)
    updates = {target_id: {"hr_bpm": 140, "spo2_pct": 89}} if deteriorate_first_patient else None
    queue = tick_waiting_room(before, evaluated_at, vital_updates=updates)
    after_rank = next(item["queue_rank"] for item in queue if item["patient_id"] == target_id)
    return {
        "scenario": "SURGE_3X" if multiplier == SURGE_MULTIPLIER else "QUIET_1X",
        "load_multiplier": multiplier,
        "arrival_window_minutes": ARRIVAL_WINDOW_MINUTES,
        "baseline_arrivals_per_window": BASELINE_ARRIVALS_PER_WINDOW,
        "arrival_count": count,
        "queue_length": len(queue),
        "combat_mode_threshold": COMBAT_MODE_QUEUE_THRESHOLD,
        "automatic_combat_mode": len(queue) >= COMBAT_MODE_QUEUE_THRESHOLD,
        "deterioration_demo": {
            "patient_id": target_id,
            "source_patient_id": entries[0]["patient"]["source_patient_id"],
            "previous_rank": before_rank,
            "new_rank": after_rank,
            "moved_forward": after_rank < before_rank,
        } if deteriorate_first_patient else None,
        "queue": queue,
    }

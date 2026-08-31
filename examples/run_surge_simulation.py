"""Replay the same 15-minute window at 1x and 3x arrival volume."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))


from pathlib import Path

from src.workflows.queue_surge import load_simulated_patients, replay_arrivals

def main() -> None:
    patients = load_simulated_patients(Path(__file__).parents[1] / "data" / "simulated_patients.json")
    quiet = replay_arrivals(patients, multiplier=1)
    surge = replay_arrivals(patients, multiplier=3, deteriorate_first_patient=True)
    for scenario in (quiet, surge):
        print(
            f"{scenario['scenario']}: {scenario['arrival_count']} arrivals / "
            f"{scenario['arrival_window_minutes']} min, queue={scenario['queue_length']}, "
            f"Combat Mode={'ON' if scenario['automatic_combat_mode'] else 'OFF'}"
        )
    moved = surge["deterioration_demo"]
    print(
        f"Deterioration replay: {moved['patient_id']} ({moved['source_patient_id']}) "
        f"rank {moved['previous_rank']} -> {moved['new_rank']}"
    )

if __name__ == "__main__":
    main()

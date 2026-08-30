import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from resilicare import create_waiting_entry, tick_waiting_room
from resilicare.safety import evaluate_safety_rules

def main():
    # 1. Load the simulated dataset
    data_file = Path(__file__).parent.parent / "data" / "simulated_patients.json"
    if not data_file.exists():
        print(f"Error: Dataset not found at {data_file}")
        return
        
    dataset = json.loads(data_file.read_text(encoding="utf-8"))
    patients = dataset.get("patients", [])
    
    if len(patients) < 10:
        print("Not enough patients in dataset to run surge simulation.")
        return

    start_time = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    queue = []
    
    print("--- BASELINE QUEUE (T=0) ---")
    print("Initializing waiting room with 3 standard patients...")
    # Add a few patients at baseline
    for i in range(3):
        p = patients[i]
        # Use a default ESI of 4 for the baseline if not defined
        esi = p.get("reference_esi", 4)
        queue.append(create_waiting_entry(p, esi, start_time))
    
    # First tick to establish ranks
    queue = tick_waiting_room(queue, start_time)
    print_queue(queue)
    
    print("\n--- SURGE EVENT (T=15 mins) ---")
    print("Simulating a 3x patient influx (Mass casualty event / High volume)...")
    surge_time = start_time + timedelta(minutes=15)
    
    # Inject 9 more patients suddenly
    for i in range(3, 12):
        p = patients[i]
        esi = p.get("reference_esi", 3)
        queue.append(create_waiting_entry(p, esi, surge_time))
        
    # Introduce vital deterioration for one of the baseline patients
    deteriorating_patient_id = patients[1]["patient_id"]
    print(f"\n[!] ALERT: Patient {deteriorating_patient_id} has suddenly deteriorated in the waiting room (HR: 140, SpO2: 89%).")
    vital_updates = {
        deteriorating_patient_id: {"hr_bpm": 140, "spo2_pct": 89}
    }
    
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "surge_audit.jsonl"
        # Tick the room with the surge and the vital updates
        queue = tick_waiting_room(
            queue, 
            surge_time,
            vital_updates=vital_updates,
            log_path=log
        )
        
    print("\n--- QUEUE AFTER SURGE & DETERIORATION ---")
    print_queue(queue)
    print("\n[Surge Test Complete]: Notice how the deteriorated patient bubbled up, and the queue successfully re-sorted the high volume.")

def print_queue(queue):
    print(f"{'Rank':<5} | {'Patient ID':<15} | {'ESI':<5} | {'Alert/Status'}")
    print("-" * 75)
    for entry in queue:
        alert = entry.get('waiting_room_alert') or "WAITING"
        # Truncate alert if it's too long for the console
        if len(alert) > 40:
            alert = alert[:37] + "..."
        print(f"{entry['queue_rank']:<5} | {entry['patient_id']:<15} | {entry['current_esi']:<5} | {alert}")

if __name__ == "__main__":
    main()

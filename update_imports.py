import os
from pathlib import Path

PROJECT_ROOT = Path("/home/garuda/Documents/workspace/ResiliCare_1")

REPLACEMENTS = [
    ("resilicare.engine.confidence", "src.core.confidence_scoring"),
    ("resilicare.engine.differentials", "src.core.clinical_differentials"),
    ("resilicare.engine.explanations", "src.core.score_explanations"),
    ("resilicare.engine.safety", "src.core.safety_rules"),
    ("resilicare.engine.vitals", "src.core.vital_signs"),
    ("resilicare.engine", "src.core"),
    ("resilicare.storage.audit", "src.data.audit_log"),
    ("resilicare.storage.confirmation", "src.data.clinical_confirmation"),
    ("resilicare.storage.history_store", "src.data.history_store"),
    ("resilicare.storage.history", "src.data.patient_history"),
    ("resilicare.storage", "src.data"),
    ("resilicare.integrations.fhir_export", "src.adapters.fhir_exporter"),
    ("resilicare.integrations.hospital_config", "src.adapters.hospital_config"),
    ("resilicare.integrations.routing", "src.adapters.clinical_routing"),
    ("resilicare.integrations", "src.adapters"),
    ("resilicare.queue.combat", "src.workflows.combat_mode"),
    ("resilicare.queue.surge", "src.workflows.queue_surge"),
    ("resilicare.queue.waiting_room", "src.workflows.waiting_room"),
    ("resilicare.queue", "src.workflows"),
    ("resilicare.config", "src.config"),
    ("resilicare.nlp", "src.nlp"),
    ("resilicare", "src"),
]

def update_imports():
    for root, _, files in os.walk(PROJECT_ROOT / "src"):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = Path(root) / file
            content = path.read_text()
            original = content
            for old, new in REPLACEMENTS:
                content = content.replace(f"from {old}", f"from {new}")
                content = content.replace(f"import {old}", f"import {new}")
            
            # also handle relative imports inside src/__init__.py
            if file == "__init__.py" and root.endswith("src"):
                content = content.replace("from .engine.safety", "from .core.safety_rules")
                content = content.replace("from .engine.confidence", "from .core.confidence_scoring")
                content = content.replace("from .engine.explanations", "from .core.score_explanations")
                content = content.replace("from .engine.differentials", "from .core.clinical_differentials")
                content = content.replace("from .engine.vitals", "from .core.vital_signs")
                
                content = content.replace("from .storage.audit", "from .data.audit_log")
                content = content.replace("from .storage.history", "from .data.patient_history")
                content = content.replace("from .storage.history_store", "from .data.history_store")
                content = content.replace("from .storage.confirmation", "from .data.clinical_confirmation")
                
                content = content.replace("from .queue.waiting_room", "from .workflows.waiting_room")
                content = content.replace("from .queue.surge", "from .workflows.queue_surge")
                content = content.replace("from .queue.combat", "from .workflows.combat_mode")
                
                content = content.replace("from .integrations.routing", "from .adapters.clinical_routing")
                content = content.replace("from .integrations.fhir_export", "from .adapters.fhir_exporter")
                content = content.replace("from .integrations.hospital_config", "from .adapters.hospital_config")

            if content != original:
                path.write_text(content)
                print(f"Updated {path}")

if __name__ == "__main__":
    update_imports()

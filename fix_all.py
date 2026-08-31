import os
import re
from pathlib import Path

# Mapping of module name to its subpackage
MODULE_MAP = {
    'vital_thresholds.json': 'config',
    'confidence_config.json': 'config',
    'missingness_config.json': 'config',
    'waiting_room_config.json': 'config',
    'ambiguous_presentations.json': 'config',
    'facilities.json': 'config',
    'hospital_profiles.json': 'config',
    'vitals': 'engine',
    'safety': 'engine',
    'confidence': 'engine',
    'differentials': 'engine',
    'explanations': 'engine',
    'waiting_room': 'queue',
    'surge': 'queue',
    'combat': 'queue',
    'hospital_config': 'integrations',
    'routing': 'integrations',
    'fhir_export': 'integrations',
    'history': 'storage',
    'history_store': 'storage',
    'audit': 'storage'
}

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return

    orig = content

    for mod, sub in MODULE_MAP.items():
        if mod.endswith('.json'):
            continue
        content = re.sub(r'from resilicare\.' + mod + r'\b', f'from resilicare.{sub}.{mod}', content)
        content = re.sub(r'import resilicare\.' + mod + r'\b', f'import resilicare.{sub}.{mod}', content)

    for mod, sub in MODULE_MAP.items():
        if mod.endswith('.json'):
            continue
        content = re.sub(r'from \.' + mod + r'\b', f'from resilicare.{sub}.{mod}', content)

    content = re.sub(r'Path\(__file__\)\.with_name\("([^"]+\.json)"\)', r'(Path(__file__).parent.parent / "config" / "\1")', content)

    if content != orig:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for d in ['src/resilicare', 'tests', 'examples', 'demo']:
    for root, _, files in os.walk(d):
        for f in files:
            if f.endswith('.py'):
                process_file(os.path.join(root, f))

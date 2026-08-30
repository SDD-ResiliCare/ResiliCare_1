"""Deterministic lookup for common ambiguous presentations."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


@lru_cache(maxsize=1)
def load_ambiguous_presentation_table() -> dict[str, Any]:
    table = json.loads(Path(__file__).with_name("ambiguous_presentations.json").read_text(encoding="utf-8"))
    if table.get("schema_version") != 1 or not table.get("entries"):
        raise ValueError("ambiguous-presentation table must contain versioned entries")
    return table


def match_ambiguous_presentations(patient: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return every phrase-matched pathway; matching never diagnoses a condition."""
    searchable = _normalize(str(patient.get("chief_complaint") or ""))
    matches = []
    for entry in load_ambiguous_presentation_table()["entries"]:
        phrase = next((item for item in entry["trigger_phrases"] if _contains(searchable, item)), None)
        if phrase:
            matches.append({
                "pathway_id": entry["id"],
                "label": entry["label"],
                "matched_phrase": phrase,
                "maximum_allowed_esi": entry["maximum_allowed_esi"],
                "mandatory_safety_workup": True,
                "differential_considerations": list(entry["differential_considerations"]),
                "required_safety_actions": list(entry["required_safety_actions"]),
                "source_urls": list(entry["source_urls"]),
            })
    return matches


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?:^| )({re.escape(_normalize(phrase))})(?: |$)", text) is not None

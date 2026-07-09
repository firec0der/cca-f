"""Fixed, versioned input sets. Cases are data; they never call the API."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Case:
    id: str
    inputs: dict[str, Any]
    expected: Any | None = None


def load_cases(name: str, root: Path) -> list[Case]:
    """Load `root/<name>.json` — a JSON array of {id, inputs, expected?}."""
    path = Path(root) / f"{name}.json"
    raw = json.loads(path.read_text())

    cases: list[Case] = []
    seen: set[str] = set()
    for entry in raw:
        case_id = entry["id"]
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        cases.append(Case(id=case_id, inputs=entry["inputs"], expected=entry.get("expected")))
    return cases

"""The only repository-to-Linear seam: emit a table, paste it into a unit note.

Metric values are plain floats to three decimals. A rate is a fraction, not a
percentage — 0.180, never "18%". Formatting it once, here, keeps every unit
note comparable.
"""

from __future__ import annotations

from measure.trials import TrialResults


def to_markdown(results: TrialResults, **metrics: float) -> str:
    lines = ["| Metric | Value |", "| -- | -- |", f"| trials | {len(results)} |"]
    lines.extend(f"| {name} | {value:.3f} |" for name, value in metrics.items())
    return "\n".join(lines) + "\n"

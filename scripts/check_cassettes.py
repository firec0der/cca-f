#!/usr/bin/env python3
"""Fail if any committed cassette contains an Anthropic API key.

`ccakit.cassette` never records request headers, so this should never fire.
It is the second of two defences; the cost of the check is ten lines and the
cost of the failure is a leaked key on a public remote.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]+")


def find_secrets(root: Path) -> list[str]:
    """Scan every *.json at any depth beneath a directory named `cassettes`."""
    findings: list[str] = []
    for path in sorted(root.rglob("*.json")):
        if "cassettes" not in path.relative_to(root).parts:
            continue
        if SECRET.search(path.read_text()):
            findings.append(str(path.relative_to(root)))
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    findings = find_secrets(root)
    for f in findings:
        print(f"SECRET IN CASSETTE: {f}", file=sys.stderr)
    if findings:
        print("\nRotate the key immediately, then re-record.", file=sys.stderr)
        return 1
    print("cassettes OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

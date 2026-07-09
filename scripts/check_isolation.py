#!/usr/bin/env python3
"""Fail if a Tier 2/3 build imports or depends on `measure`.

Tier 1 may import measure; Tier 2/3 may not. Portfolio builds must remain
`git subtree split`-able into standalone repositories.

Import detection walks the AST rather than grepping text, for precision: it
will not flag "measure" appearing in a comment, docstring, or unrelated string
literal. That precision comes with a known, accepted gap: the AST walk only
catches *static* imports (`import measure`, `from measure... import ...`).
Dynamic imports (`importlib.import_module("measure")`, `__import__("measure")`)
are calls, not `Import`/`ImportFrom` nodes, so they are NOT caught. This guard
targets accidental coupling, not deliberate evasion, so that gap is out of
scope by design.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

FORBIDDEN = "measure"
PORTFOLIO_GLOBS = ("projects/s*", "projects/capstone")

# PEP 508: the distribution name is the leading run of name characters.
# Naive `.split("=")[0]` leaves the `>` on `measure>=0.1` and misses the violation.
_DIST_NAME = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?")


def _portfolio_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    for pattern in PORTFOLIO_GLOBS:
        dirs.extend(d for d in root.glob(pattern) if d.is_dir())
    return sorted(dirs)


def _declares_forbidden(deps: list) -> bool:
    """True if any string requirement in `deps` names FORBIDDEN as its distribution."""
    return any(
        isinstance(d, str) and (m := _DIST_NAME.match(d.strip())) and m.group() == FORBIDDEN
        for d in deps
    )


def _imports_forbidden(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == FORBIDDEN or a.name.startswith(f"{FORBIDDEN}.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == FORBIDDEN or module.startswith(f"{FORBIDDEN}."):
                return True
    return False


def find_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for project in _portfolio_dirs(root):
        for py in sorted(project.rglob("*.py")):
            try:
                tree = ast.parse(py.read_text())
            except SyntaxError as exc:
                violations.append(f"{py.relative_to(root)}: syntax error: {exc}")
                continue
            if _imports_forbidden(tree):
                violations.append(f"{py.relative_to(root)}: imports `{FORBIDDEN}`")

        pyproject = project / "pyproject.toml"
        if pyproject.is_file():
            data = tomllib.loads(pyproject.read_text())
            path = pyproject.relative_to(root)

            deps = data.get("project", {}).get("dependencies", [])
            if _declares_forbidden(deps):
                violations.append(f"{path}: pyproject declares `{FORBIDDEN}` as a dependency")

            optional_deps = data.get("project", {}).get("optional-dependencies", {})
            for group, group_deps in optional_deps.items():
                if _declares_forbidden(group_deps):
                    violations.append(
                        f"{path}: pyproject declares `{FORBIDDEN}` in "
                        f"[project.optional-dependencies.{group}]"
                    )

            dependency_groups = data.get("dependency-groups", {})
            for group, group_deps in dependency_groups.items():
                if _declares_forbidden(group_deps):
                    violations.append(
                        f"{path}: pyproject declares `{FORBIDDEN}` in [dependency-groups.{group}]"
                    )
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    violations = find_violations(root)
    for v in violations:
        print(f"ISOLATION VIOLATION: {v}", file=sys.stderr)
    if violations:
        print(
            f"\n{len(violations)} violation(s). Tier 2/3 builds must not depend on {FORBIDDEN}.",
            file=sys.stderr,
        )
        return 1
    print("isolation OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

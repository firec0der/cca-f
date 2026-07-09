import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_isolation import find_violations  # noqa: E402


def _portfolio(tmp_path: Path, name: str) -> Path:
    d = tmp_path / "projects" / name / "src"
    d.mkdir(parents=True)
    return d


def test_clean_tree_has_no_violations(tmp_path):
    src = _portfolio(tmp_path, "s1-support-agent")
    (src / "app.py").write_text("import httpx\n")
    assert find_violations(tmp_path) == []


def test_plain_import_is_a_violation(tmp_path):
    src = _portfolio(tmp_path, "s1-support-agent")
    (src / "app.py").write_text("import ccakit\n")
    assert len(find_violations(tmp_path)) == 1


def test_from_import_of_a_submodule_is_a_violation(tmp_path):
    src = _portfolio(tmp_path, "s3-research-system")
    (src / "app.py").write_text("from ccakit.trials import run_trials\n")
    assert len(find_violations(tmp_path)) == 1


def test_capstone_is_scanned(tmp_path):
    src = _portfolio(tmp_path, "capstone")
    (src / "app.py").write_text("import ccakit.report\n")
    assert len(find_violations(tmp_path)) == 1


def test_tier_one_may_import_ccakit(tmp_path):
    d = tmp_path / "projects" / "p01-agentic-loop-workbench" / "src"
    d.mkdir(parents=True)
    (d / "core.py").write_text("import ccakit\n")
    assert find_violations(tmp_path) == []


def test_a_declared_dependency_is_a_violation_even_with_no_import(tmp_path):
    proj = tmp_path / "projects" / "s6-extraction-service"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "s6"\nversion = "0"\ndependencies = ["ccakit", "httpx"]\n'
    )
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert "pyproject" in violations[0]


@pytest.mark.parametrize(
    "dep",
    [
        "ccakit",
        "ccakit>=0.1",
        "ccakit==0.1.0",
        "ccakit[dev]>=0.1",
        "ccakit ; python_version>='3.12'",
    ],
)
def test_every_pep508_spelling_of_the_dependency_is_caught(tmp_path, dep):
    """`ccakit>=0.1` is the spelling a real pyproject would use."""
    proj = tmp_path / "projects" / "s1-support-agent"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        f'[project]\nname = "s1"\nversion = "0"\ndependencies = ["{dep}"]\n'
    )
    assert len(find_violations(tmp_path)) == 1


def test_a_dependency_merely_prefixed_with_the_name_is_not_a_violation(tmp_path):
    proj = tmp_path / "projects" / "s1-support-agent"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "s1"\nversion = "0"\ndependencies = ["ccakit-extras>=1.0"]\n'
    )
    assert find_violations(tmp_path) == []


def test_a_syntax_error_is_reported_not_swallowed(tmp_path):
    src = _portfolio(tmp_path, "s2-team-workflow")
    (src / "broken.py").write_text("def (:\n")
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert "syntax error" in violations[0]


def test_dependency_group_entry_is_a_violation(tmp_path):
    proj = tmp_path / "projects" / "s1-support-agent"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "s1"\nversion = "0"\n\n[dependency-groups]\ndev = ["ccakit", "pytest"]\n'
    )
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert "dependency-groups.dev" in violations[0]


def test_optional_dependency_entry_is_a_violation(tmp_path):
    proj = tmp_path / "projects" / "s1-support-agent"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "s1"\nversion = "0"\n\n'
        "[project.optional-dependencies]\n"
        'extra = ["ccakit>=0.1"]\n'
    )
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert "optional-dependencies.extra" in violations[0]


def test_dependency_group_include_group_entry_does_not_crash(tmp_path):
    proj = tmp_path / "projects" / "s1-support-agent"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "s1"\nversion = "0"\n\n'
        "[dependency-groups]\n"
        'base = ["pytest"]\n'
        'dev = ["ccakit", {include-group = "base"}]\n'
    )
    violations = find_violations(tmp_path)
    assert len(violations) == 1
    assert "dependency-groups.dev" in violations[0]


def test_dependency_group_without_ccakit_is_not_a_violation(tmp_path):
    proj = tmp_path / "projects" / "s1-support-agent"
    proj.mkdir(parents=True)
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "s1"\nversion = "0"\n\n[dependency-groups]\ndev = ["pytest", "ruff"]\n'
    )
    assert find_violations(tmp_path) == []

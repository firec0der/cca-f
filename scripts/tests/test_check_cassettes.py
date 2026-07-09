import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_cassettes import find_secrets  # noqa: E402


def _cassette(tmp_path: Path, text: str) -> Path:
    d = tmp_path / "projects" / "p01" / "cassettes"
    d.mkdir(parents=True)
    p = d / "run.json"
    p.write_text(text)
    return p


def test_clean_cassette_passes(tmp_path):
    _cassette(tmp_path, '{"version": 1, "interactions": {}}')
    assert find_secrets(tmp_path) == []


def test_an_api_key_anywhere_in_the_file_is_caught(tmp_path):
    _cassette(tmp_path, '{"body": "oops sk-ant-api03-abc123"}')
    assert len(find_secrets(tmp_path)) == 1


def test_json_outside_a_cassettes_dir_is_not_scanned(tmp_path):
    d = tmp_path / "projects" / "p01" / "cases"
    d.mkdir(parents=True)
    (d / "x.json").write_text("sk-ant-whatever")
    assert find_secrets(tmp_path) == []


def test_a_key_nested_below_the_cassettes_dir_is_caught(tmp_path):
    d = tmp_path / "projects" / "p01" / "cassettes" / "antipattern"
    d.mkdir(parents=True)
    (d / "run.json").write_text('{"body": "sk-ant-api03-leaked"}')
    assert len(find_secrets(tmp_path)) == 1

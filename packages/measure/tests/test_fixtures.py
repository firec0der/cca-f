import json

import pytest

from measure.fixtures import Case, load_cases


def test_load_cases_reads_a_json_array(tmp_path):
    (tmp_path / "demo.json").write_text(
        json.dumps(
            [
                {"id": "a", "inputs": {"prompt": "hi"}, "expected": "greeting"},
                {"id": "b", "inputs": {"prompt": "bye"}},
            ]
        )
    )
    cases = load_cases("demo", root=tmp_path)
    assert cases == [
        Case(id="a", inputs={"prompt": "hi"}, expected="greeting"),
        Case(id="b", inputs={"prompt": "bye"}, expected=None),
    ]


def test_load_cases_rejects_duplicate_ids(tmp_path):
    (tmp_path / "dupe.json").write_text(
        json.dumps([{"id": "a", "inputs": {}}, {"id": "a", "inputs": {}}])
    )
    with pytest.raises(ValueError, match="duplicate case id: a"):
        load_cases("dupe", root=tmp_path)


def test_load_cases_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_cases("nope", root=tmp_path)

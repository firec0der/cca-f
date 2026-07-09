import json

import httpx
import pytest

from measure.cassette import (
    CassetteExhausted,
    CassetteMiss,
    CassetteTransport,
    request_key,
)

URL = "https://api.anthropic.com/v1/messages"


def _post(client: httpx.Client, body: dict) -> httpx.Response:
    return client.post(URL, json=body)


def test_request_key_is_stable_and_body_sensitive():
    a = httpx.Request("POST", URL, json={"x": 1})
    b = httpx.Request("POST", URL, json={"x": 1})
    c = httpx.Request("POST", URL, json={"x": 2})
    assert request_key(a) == request_key(b)
    assert request_key(a) != request_key(c)


def test_record_then_replay_preserves_response_order(tmp_path):
    """The property every anti-pattern lab depends on."""
    path = tmp_path / "c.json"
    replies = iter([b'{"n": 1}', b'{"n": 2}', b'{"n": 3}'])
    real = httpx.MockTransport(lambda req: httpx.Response(200, content=next(replies)))

    recorder = CassetteTransport(path, mode="record", real=real)
    with httpx.Client(transport=recorder) as client:
        for _ in range(3):
            _post(client, {"x": 1})
    recorder.save()

    player = CassetteTransport(path, mode="replay")
    with httpx.Client(transport=player) as client:
        seen = [_post(client, {"x": 1}).json()["n"] for _ in range(3)]
    assert seen == [1, 2, 3]


def test_replay_is_deterministic_across_runs(tmp_path):
    path = tmp_path / "c.json"
    replies = iter([b'{"n": 1}', b'{"n": 2}'])
    real = httpx.MockTransport(lambda req: httpx.Response(200, content=next(replies)))
    recorder = CassetteTransport(path, mode="record", real=real)
    with httpx.Client(transport=recorder) as client:
        _post(client, {"x": 1})
        _post(client, {"x": 1})
    recorder.save()

    for _ in range(2):
        player = CassetteTransport(path, mode="replay")
        with httpx.Client(transport=player) as client:
            assert [_post(client, {"x": 1}).json()["n"] for _ in range(2)] == [1, 2]


def test_replaying_more_than_was_recorded_raises(tmp_path):
    path = tmp_path / "c.json"
    real = httpx.MockTransport(lambda req: httpx.Response(200, content=b"{}"))
    recorder = CassetteTransport(path, mode="record", real=real)
    with httpx.Client(transport=recorder) as client:
        _post(client, {"x": 1})
    recorder.save()

    player = CassetteTransport(path, mode="replay")
    with httpx.Client(transport=player) as client:
        _post(client, {"x": 1})
        with pytest.raises(CassetteExhausted):
            _post(client, {"x": 1})


def test_an_unrecorded_request_raises_rather_than_hitting_the_network(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"version": 1, "interactions": {}}))
    player = CassetteTransport(path, mode="replay")
    with httpx.Client(transport=player) as client:
        with pytest.raises(CassetteMiss):
            _post(client, {"x": 1})


def test_no_request_headers_are_ever_written_to_the_cassette(tmp_path):
    path = tmp_path / "c.json"
    real = httpx.MockTransport(lambda req: httpx.Response(200, content=b"{}"))
    recorder = CassetteTransport(path, mode="record", real=real)
    with httpx.Client(transport=recorder, headers={"x-api-key": "sk-ant-SECRET"}) as client:
        _post(client, {"x": 1})
    recorder.save()

    raw = path.read_text()
    assert "sk-ant-SECRET" not in raw
    assert "x-api-key" not in raw.lower()


def test_record_mode_requires_a_real_transport(tmp_path):
    with pytest.raises(ValueError, match="record mode requires"):
        CassetteTransport(tmp_path / "c.json", mode="record")

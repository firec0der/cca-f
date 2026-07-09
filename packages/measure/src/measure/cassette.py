"""Record once against the live API, replay for free thereafter.

Two properties this module exists to guarantee:

1. **Order is preserved per request key.** The same request issued twenty
   times records twenty distinct responses and replays them in the same
   order. Collapsing them to one would turn every measured rate into 0.0
   or 1.0 — reproducible and wrong.

2. **Request headers are never written.** Not filtered after the fact:
   never captured. Cassettes are committed to a repository with a public
   remote, and `x-api-key` lives in a request header.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

import httpx

_VERSION = 1


class CassetteMiss(RuntimeError):
    """The request was never recorded."""


class CassetteExhausted(RuntimeError):
    """More replays were requested than were recorded for this request."""


def request_key(request: httpx.Request) -> str:
    payload = f"{request.method} {request.url}\n".encode() + request.content
    return hashlib.sha256(payload).hexdigest()


class CassetteTransport(httpx.BaseTransport):
    def __init__(
        self,
        path: Path,
        *,
        mode: Literal["replay", "record"] = "replay",
        real: httpx.BaseTransport | None = None,
    ) -> None:
        if mode == "record" and real is None:
            raise ValueError("record mode requires a `real` transport to record from")
        self.path = Path(path)
        self.mode = mode
        self._real = real
        self._interactions: dict[str, list[dict]] = defaultdict(list)
        self._cursor: dict[str, int] = defaultdict(int)

        if mode == "replay":
            data = json.loads(self.path.read_text())
            self._interactions = defaultdict(list, data["interactions"])

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        key = request_key(request)
        if self.mode == "record":
            assert self._real is not None
            raw = self._real.handle_request(request)
            raw.read()  # consumes the upstream stream
            self._interactions[key].append(
                {
                    "status": raw.status_code,
                    "headers": {"content-type": raw.headers.get("content-type", "")},
                    "body": raw.content.decode(),
                }
            )
            # Return a fresh, non-streaming Response: `raw`'s stream is now
            # consumed, and handing it back to the Client would raise
            # StreamConsumed on the next read.
            return httpx.Response(
                status_code=raw.status_code,
                headers=raw.headers,
                content=raw.content,
                request=request,
            )

        recorded = self._interactions.get(key)
        if not recorded:
            raise CassetteMiss(f"no recorded interaction for {request.method} {request.url}")

        index = self._cursor[key]
        if index >= len(recorded):
            raise CassetteExhausted(
                f"replayed {index} of {len(recorded)} recorded responses for "
                f"{request.method} {request.url}; re-record with more trials"
            )
        self._cursor[key] = index + 1

        entry = recorded[index]
        return httpx.Response(
            status_code=entry["status"],
            headers=entry["headers"],
            content=entry["body"].encode(),
            request=request,
        )

    def save(self) -> None:
        """Flush recorded interactions. No-op in replay mode."""
        if self.mode != "record":
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"version": _VERSION, "interactions": dict(self._interactions)},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

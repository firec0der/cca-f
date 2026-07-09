"""Status classification. Deliberately does not import `anthropic` —
it duck-types on `status_code`, which every SDK APIStatusError carries.
"""

from __future__ import annotations

RETRYABLE_STATUS = frozenset({429, 529})
FATAL_STATUS = frozenset({400, 401, 403})


def is_retryable(exc: BaseException) -> bool:
    return getattr(exc, "status_code", None) in RETRYABLE_STATUS

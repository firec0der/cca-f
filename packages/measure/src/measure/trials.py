"""Run a fixed case set N times and measure a rate over the outcomes.

The invariant this module exists to protect: an infrastructure failure is
not an experimental result. A 429 retried three times produces ONE trial,
not four, and never appears in a denominator.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from measure.errors import is_retryable
from measure.fixtures import Case
from measure.tokens import SpendTracker


@dataclass(frozen=True)
class Trial:
    case: Case
    value: Any
    attempts: int


@dataclass(frozen=True)
class TrialResults:
    trials: tuple[Trial, ...]

    def __len__(self) -> int:
        return len(self.trials)

    def rate(self, predicate: Callable[[Trial], bool]) -> float:
        """Fraction of trials satisfying `predicate`.

        Raises ZeroDivisionError on an empty result set: a rate over nothing
        is not 0.0, it is undefined, and silently returning 0.0 would make a
        broken run look like a clean one.
        """
        if not self.trials:
            raise ZeroDivisionError("cannot compute a rate over zero trials")
        return sum(1 for t in self.trials if predicate(t)) / len(self.trials)


def run_trials(
    cases: Iterable[Case],
    fn: Callable[[Case], Any],
    n: int = 1,
    *,
    tracker: SpendTracker | None = None,
    max_retries: int = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> TrialResults:
    """Run `fn` over each case `n` times, retrying retryable API errors.

    `sleep` is injected so tests never wait. Construct the Anthropic client
    with `max_retries=0` — two retry layers distort measured rates.
    """
    case_list: Sequence[Case] = list(cases)
    trials: list[Trial] = []

    for case in case_list:
        for _ in range(n):
            if tracker is not None:
                tracker.assert_within_cap()
            value, attempts = _attempt(case, fn, max_retries=max_retries, sleep=sleep)
            trials.append(Trial(case=case, value=value, attempts=attempts))

    return TrialResults(trials=tuple(trials))


def _attempt(
    case: Case,
    fn: Callable[[Case], Any],
    *,
    max_retries: int,
    sleep: Callable[[float], None],
) -> tuple[Any, int]:
    for attempt in range(max_retries + 1):
        try:
            return fn(case), attempt + 1
        except Exception as exc:  # noqa: BLE001 — re-raised unless retryable
            if not is_retryable(exc) or attempt == max_retries:
                raise
            sleep(2.0**attempt)
    raise AssertionError("unreachable")

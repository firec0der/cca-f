import pytest

from measure.fixtures import Case
from measure.tokens import SpendCapExceeded, SpendTracker, Usage
from measure.trials import run_trials


class FakeAPIError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


CASES = [Case(id="a", inputs={}), Case(id="b", inputs={})]


def test_runs_each_case_n_times():
    results = run_trials(CASES, lambda case: case.id, n=3, sleep=lambda _: None)
    assert len(results) == 6
    assert [t.case.id for t in results.trials] == ["a", "a", "a", "b", "b", "b"]


def test_rate_counts_the_predicate_over_all_trials():
    results = run_trials(CASES, lambda case: case.id, n=2, sleep=lambda _: None)
    assert results.rate(lambda t: t.value == "a") == pytest.approx(0.5)


def test_rate_on_an_empty_result_set_raises():
    results = run_trials([], lambda case: None, sleep=lambda _: None)
    with pytest.raises(ZeroDivisionError):
        results.rate(lambda t: True)


def test_a_rate_limit_is_retried_and_never_recorded_as_an_outcome():
    calls: list[str] = []

    def flaky(case: Case) -> str:
        calls.append(case.id)
        if len(calls) < 3:
            raise FakeAPIError(429)
        return "ok"

    results = run_trials([CASES[0]], flaky, n=1, sleep=lambda _: None)
    # Three calls, ONE trial. The two 429s are infrastructure, not outcomes.
    assert len(calls) == 3
    assert len(results) == 1
    assert results.trials[0].value == "ok"
    assert results.trials[0].attempts == 3
    assert results.rate(lambda t: t.value == "ok") == pytest.approx(1.0)


def test_a_fatal_status_aborts_the_run_immediately():
    def fatal(case: Case) -> str:
        raise FakeAPIError(401)

    with pytest.raises(FakeAPIError):
        run_trials(CASES, fatal, n=5, sleep=lambda _: None)


def test_a_non_api_exception_propagates():
    def broken(case: Case) -> str:
        raise ValueError("bug in the lab")

    with pytest.raises(ValueError, match="bug in the lab"):
        run_trials(CASES, broken, sleep=lambda _: None)


def test_retries_are_bounded():
    def always_429(case: Case) -> str:
        raise FakeAPIError(429)

    with pytest.raises(FakeAPIError):
        run_trials([CASES[0]], always_429, max_retries=2, sleep=lambda _: None)


def test_backoff_is_exponential_and_injectable():
    slept: list[float] = []
    calls: list[int] = []

    def flaky(case: Case) -> str:
        calls.append(1)
        if len(calls) < 4:
            raise FakeAPIError(529)
        return "ok"

    run_trials([CASES[0]], flaky, sleep=slept.append)
    assert slept == [1.0, 2.0, 4.0]


def test_the_spend_cap_aborts_between_trials():
    tracker = SpendTracker(max_spend_usd=0.10)

    def spender(case: Case) -> str:
        tracker.record(Usage(input_tokens=100_000), "claude-opus-4-8")  # $0.50 each
        return "ok"

    with pytest.raises(SpendCapExceeded):
        run_trials(CASES, spender, n=5, tracker=tracker, sleep=lambda _: None)

import pytest

from measure.tokens import (
    CACHE_WRITE_MULTIPLIER_1H,
    PRICING,
    SpendCapExceeded,
    SpendTracker,
    Usage,
    cost_usd,
)


def test_cost_of_plain_input_and_output():
    # opus-4-8: $5.00 / Mtok in, $25.00 / Mtok out
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost_usd(usage, "claude-opus-4-8") == pytest.approx(30.00)


def test_cache_read_is_a_tenth_of_input():
    usage = Usage(cache_read_input_tokens=1_000_000)
    assert cost_usd(usage, "claude-opus-4-8") == pytest.approx(0.50)


def test_cache_write_defaults_to_the_five_minute_multiplier():
    usage = Usage(cache_creation_input_tokens=1_000_000)
    assert cost_usd(usage, "claude-opus-4-8") == pytest.approx(6.25)


def test_cache_write_one_hour_multiplier():
    usage = Usage(cache_creation_input_tokens=1_000_000)
    cost = cost_usd(usage, "claude-opus-4-8", cache_write_multiplier=CACHE_WRITE_MULTIPLIER_1H)
    assert cost == pytest.approx(10.00)


def test_unknown_model_raises_rather_than_guessing():
    with pytest.raises(KeyError):
        cost_usd(Usage(input_tokens=1), "claude-imaginary-9")


def test_pricing_table_covers_the_models_we_use():
    assert set(PRICING) >= {"claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"}


def test_tracker_accumulates_without_raising_below_the_cap():
    tracker = SpendTracker(max_spend_usd=1.00)
    tracker.record(Usage(input_tokens=100_000), "claude-opus-4-8")  # $0.50
    assert tracker.spent_usd == pytest.approx(0.50)
    tracker.assert_within_cap()


def test_tracker_raises_when_the_cap_is_crossed():
    tracker = SpendTracker(max_spend_usd=1.00)
    tracker.record(Usage(input_tokens=100_000), "claude-opus-4-8")  # $0.50
    with pytest.raises(SpendCapExceeded) as exc:
        tracker.record(Usage(input_tokens=200_000), "claude-opus-4-8")  # → $1.50
    assert exc.value.cap_usd == 1.00
    assert exc.value.spent_usd == pytest.approx(1.50)
    # The spend is recorded even though it raised — the tokens were really bought.
    assert tracker.spent_usd == pytest.approx(1.50)


def test_assert_within_cap_raises_after_an_overrun():
    tracker = SpendTracker(max_spend_usd=0.10)
    with pytest.raises(SpendCapExceeded):
        tracker.record(Usage(input_tokens=1_000_000), "claude-opus-4-8")
    with pytest.raises(SpendCapExceeded):
        tracker.assert_within_cap()

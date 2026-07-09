"""Usage accounting and a hard per-run spend cap.

Pricing is $/Mtok, taken from the official model table. Cache rates are
multiplicative against the input rate, not independent numbers:
reads are 0.10x, writes 1.25x (5-minute TTL) or 2.00x (1-hour TTL).
"""

from __future__ import annotations

from dataclasses import dataclass

CACHE_READ_MULTIPLIER = 0.10
CACHE_WRITE_MULTIPLIER_5M = 1.25
CACHE_WRITE_MULTIPLIER_1H = 2.00

_PER_MTOK = 1_000_000


@dataclass(frozen=True)
class Usage:
    """Mirrors the SDK's `response.usage` field names exactly."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float
    output_per_mtok: float


PRICING: dict[str, Pricing] = {
    "claude-fable-5": Pricing(10.00, 50.00),
    "claude-opus-4-8": Pricing(5.00, 25.00),
    "claude-opus-4-7": Pricing(5.00, 25.00),
    "claude-sonnet-5": Pricing(3.00, 15.00),
    "claude-haiku-4-5": Pricing(1.00, 5.00),
}


class SpendCapExceeded(RuntimeError):
    def __init__(self, spent_usd: float, cap_usd: float) -> None:
        super().__init__(f"spend cap exceeded: ${spent_usd:.4f} > ${cap_usd:.2f}")
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd


def cost_usd(
    usage: Usage,
    model: str,
    *,
    cache_write_multiplier: float = CACHE_WRITE_MULTIPLIER_5M,
) -> float:
    """Cost of one response. Raises KeyError on an unknown model rather than guessing."""
    price = PRICING[model]
    tokens_at_input_rate = (
        usage.input_tokens
        + usage.cache_creation_input_tokens * cache_write_multiplier
        + usage.cache_read_input_tokens * CACHE_READ_MULTIPLIER
    )
    return (
        tokens_at_input_rate * price.input_per_mtok + usage.output_tokens * price.output_per_mtok
    ) / _PER_MTOK


class SpendTracker:
    """Accumulates spend and raises the moment a run crosses its cap.

    `record` raises *after* accumulating: the tokens were really bought, so
    `spent_usd` must reflect them even on the call that trips the cap.
    """

    def __init__(self, max_spend_usd: float = 2.00) -> None:
        self.max_spend_usd = max_spend_usd
        self.spent_usd = 0.0

    def record(
        self,
        usage: Usage,
        model: str,
        *,
        cache_write_multiplier: float = CACHE_WRITE_MULTIPLIER_5M,
    ) -> None:
        self.spent_usd += cost_usd(usage, model, cache_write_multiplier=cache_write_multiplier)
        self.assert_within_cap()

    def assert_within_cap(self) -> None:
        if self.spent_usd > self.max_spend_usd:
            raise SpendCapExceeded(self.spent_usd, self.max_spend_usd)

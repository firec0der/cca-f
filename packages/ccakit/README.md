# ccakit

Measurement scaffolding for the CCA Tier 1 labs.

**ccakit is the lab bench, not the experiment.** Every Tier 1 project (`projects/p01`–`p10`) exists to build one thing correctly and then measure how the *wrong* version fails. ccakit is what they measure *with* — fixed input sets, a trial runner, a cost cap, a record/replay transport, a report table. It deliberately contains none of the learning objectives themselves, and it deliberately does **not** depend on the `anthropic` SDK — it manipulates the SDK's transport, never its types.

## What lives here

| Module | Responsibility |
| -- | -- |
| `ccakit.fixtures` | `Case`, `load_cases` — fixed, versioned input sets. Cases are data; they never call the API. |
| `ccakit.tokens` | `Usage`, `Pricing`, `cost_usd`, `SpendTracker`, `SpendCapExceeded` — usage accounting and a hard per-run spend cap. (The `PRICING` table is reachable as `ccakit.tokens.PRICING`.) |
| `ccakit.errors` | `is_retryable` — status classification (429/529 retryable) with no SDK import. |
| `ccakit.trials` | `Trial`, `TrialResults`, `run_trials` — run a fixed case set N times and measure a rate over the outcomes. |
| `ccakit.cassette` | `CassetteTransport`, `request_key`, `CassetteMiss`, `CassetteExhausted` — record once against the live API, replay for free. |
| `ccakit.report` | `to_markdown` — render a metrics table to paste into a Linear unit note. |

## The rate primitive

The four measuring labs (p02, p03, p06, p08) all ask the same question: run a fixed case set many times, count how often some predicate holds.

```python
from ccakit.fixtures import load_cases
from ccakit.trials import run_trials

cases = load_cases("p03/refund-probes", root=Path("cases"))
results = run_trials(cases, guard_fn, n=20)

bypass_rate = results.rate(lambda t: t.value == "bypassed")
```

**A rate limit is not a trial outcome.** A `429` retried three times produces one trial, not four, and never enters a denominator. Counting a rate limit as a failed trial would leave the denominator right and the numerator wrong — a plausible, reproducible, wrong number. `run_trials` retries retryable errors *inside* a single trial; `is_retryable` decides which errors those are (429, 529). Fatal statuses (400, 401, 403) and any non-API exception propagate immediately.

`TrialResults.rate` raises `ZeroDivisionError` on an empty result set: a rate over zero trials is undefined, not `0.0`.

## The spend cap

`run_trials` motivating incident: a prior workflow exhausted its API spend limit mid-run and died. Pass a `SpendTracker` and the run aborts the moment it crosses the cap.

```python
from ccakit.tokens import SpendTracker, Usage

tracker = SpendTracker(max_spend_usd=2.00)   # every lab overrides this explicitly
results = run_trials(cases, fn, n=20, tracker=tracker)
# inside fn, after each API call:
tracker.record(response_usage, "claude-opus-4-8")
```

`Usage` mirrors the SDK's `response.usage` field names exactly, so each field copies across without renaming — `Usage(input_tokens=r.usage.input_tokens, …)`. (Don't splat `**r.usage.model_dump()`: the SDK object carries extra fields `Usage` doesn't declare.) Cache rates are multiplicative against the input rate: read `0.10×`, write `1.25×` (5-minute TTL) or `2.00×` (1-hour TTL). `cost_usd` raises `KeyError` on an unknown model rather than guessing a price.

## The repo→Linear seam

`report.to_markdown(results, **metrics)` renders a two-column table — `trials` first, then each metric to three decimals (a rate is a fraction, `0.180`, not `18%`). A human pastes it into the matching unit note. This is the only crossing between the repository and Linear: code emits the table, the repository stores no result, Linear stores no code.

```python
from ccakit.report import to_markdown

print(to_markdown(results, bypass_rate=0.18, baseline_rate=0.0))
# | Metric | Value |
# | -- | -- |
# | trials | 20 |
# | bypass_rate | 0.180 |
# | baseline_rate | 0.000 |
```

## Determinism

Where reproducibility matters, it comes from recorded responses (the `cassette` layer), not from `temperature=0` — that does not make the model deterministic. `run_trials` takes an injectable `sleep` so tests never wait on real backoff.

## Running the tests

From the repository root:

```bash
uv sync --all-packages
uv run pytest packages/ccakit -q
```

A bare `uv sync` uninstalls workspace members; always pass `--all-packages`.

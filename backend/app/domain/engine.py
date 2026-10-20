"""Evaluation engine: bounded concurrency, timeouts, retries, rate limiting, aggregation.

Pure orchestration: no database access. Callers consume outcomes as they complete and
persist them, so partial progress survives a crash.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.domain.providers import Provider, ProviderError, ProviderRequest
from app.domain.scoring import parse_rule, score_output

PASSED, FAILED, ERROR = "passed", "failed", "error"


@dataclass(frozen=True)
class EngineConfig:
    concurrency: int = 4
    timeout_s: float = 30.0
    max_retries: int = 2
    backoff_base_s: float = 0.5
    requests_per_second: float | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.concurrency <= 64:
            raise ValueError("concurrency must be between 1 and 64")
        if not 0 < self.timeout_s <= 300:
            raise ValueError("timeout_s must be in (0, 300]")
        if not 0 <= self.max_retries <= 5:
            raise ValueError("max_retries must be between 0 and 5")
        if not 0 <= self.backoff_base_s <= 30:
            raise ValueError("backoff_base_s must be between 0 and 30")
        if self.requests_per_second is not None and self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")


@dataclass(frozen=True)
class CaseInput:
    key: str
    input: str
    expected: str | None = None
    context: str | None = None
    rules: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseOutcome:
    key: str
    status: str
    output: str | None
    score: float | None
    score_details: dict[str, Any]
    latency_ms: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    attempts: int
    error: str | None


class RateLimiter:
    """Spaces calls at least 1/rps seconds apart across all worker threads."""

    def __init__(
        self,
        rps: float | None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._interval = None if rps is None else 1.0 / rps
        self._clock, self._sleep = clock, sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self._interval is None:
            return
        with self._lock:  # reserve a slot under the lock, wait outside it
            now = self._clock()
            start = max(now, self._next)
            self._next = start + self._interval
            wait = start - now
        if wait > 0:
            self._sleep(wait)


def compute_cost(
    pricing: tuple[float, float] | None, prompt_tokens: int | None, completion_tokens: int | None
) -> float | None:
    """None (unavailable) unless pricing AND both token counts are known."""
    if pricing is None or prompt_tokens is None or completion_tokens is None:
        return None
    return (prompt_tokens * pricing[0] + completion_tokens * pricing[1]) / 1000


def _error_outcome(case: CaseInput, attempts: int, message: str) -> CaseOutcome:
    return CaseOutcome(case.key, ERROR, None, None, {}, None, None, None, None, attempts, message)


def run_case(
    case: CaseInput,
    provider: Provider,
    cfg: EngineConfig,
    limiter: RateLimiter,
    sleep: Callable[[float], None] = time.sleep,
) -> CaseOutcome:
    request = ProviderRequest(prompt=case.input, context=case.context, metadata=case.metadata)
    attempts = 0
    while True:
        attempts += 1
        limiter.acquire()
        started = time.perf_counter()
        try:
            response = provider.generate(request, cfg.timeout_s)
            latency_ms = (time.perf_counter() - started) * 1000
            break
        except ProviderError as exc:
            if exc.retryable and attempts <= cfg.max_retries:
                sleep(cfg.backoff_base_s * 2 ** (attempts - 1))
                continue
            return _error_outcome(case, attempts, f"{type(exc).__name__}: {exc}")
        except Exception as exc:  # adapter bug; never let it kill the run
            return _error_outcome(case, attempts, f"UnexpectedProviderError: {type(exc).__name__}")

    try:
        rules = [parse_rule(r) for r in case.rules]
        scored = score_output(response.output, rules, case.expected)
    except ValueError as exc:
        return _error_outcome(case, attempts, f"ScoringError: {exc}")
    return CaseOutcome(
        key=case.key,
        status=PASSED if scored.passed else FAILED,
        output=response.output,
        score=scored.score,
        score_details=scored.to_dict(),
        latency_ms=latency_ms,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        cost_usd=compute_cost(provider.pricing, response.prompt_tokens, response.completion_tokens),
        attempts=attempts,
        error=None,
    )


def iter_outcomes(
    cases: Sequence[CaseInput],
    provider: Provider,
    cfg: EngineConfig,
    *,
    limiter: RateLimiter | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[CaseOutcome]:
    """Yield outcomes in completion order. Abandoning the iterator cancels queued cases."""
    if not cases:
        return
    limiter = limiter or RateLimiter(cfg.requests_per_second)
    pool = ThreadPoolExecutor(max_workers=min(cfg.concurrency, len(cases)))
    try:
        futures = [pool.submit(run_case, c, provider, cfg, limiter, sleep) for c in cases]
        for future in as_completed(futures):
            yield future.result()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


class _Metrics(Protocol):
    status: str
    latency_ms: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None


@dataclass(frozen=True)
class RunSummary:
    total: int
    passed: int
    failed: int
    errored: int
    pass_rate: float | None
    avg_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    total_tokens: int | None
    total_cost_usd: float | None


def percentile(sorted_values: Sequence[float], pct: float) -> float | None:
    """Nearest-rank percentile; None for empty input."""
    if not sorted_values:
        return None
    rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def summarize(rows: Sequence[_Metrics]) -> RunSummary:
    """Aggregate results. A metric is None when NO row reported it; zero is a measured value."""
    total = len(rows)
    passed = sum(r.status == PASSED for r in rows)
    failed = sum(r.status == FAILED for r in rows)
    errored = sum(r.status == ERROR for r in rows)
    lat = sorted(r.latency_ms for r in rows if r.latency_ms is not None)
    tok = [
        r.prompt_tokens + r.completion_tokens
        for r in rows
        if r.prompt_tokens is not None and r.completion_tokens is not None
    ]
    cost = [r.cost_usd for r in rows if r.cost_usd is not None]
    return RunSummary(
        total=total,
        passed=passed,
        failed=failed,
        errored=errored,
        pass_rate=(passed / total) if total else None,
        avg_latency_ms=(sum(lat) / len(lat)) if lat else None,
        p50_latency_ms=percentile(lat, 50),
        p95_latency_ms=percentile(lat, 95),
        total_tokens=sum(tok) if tok else None,
        total_cost_usd=sum(cost) if cost else None,
    )

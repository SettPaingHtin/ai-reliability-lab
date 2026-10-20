import threading
import time

from app.domain.engine import (
    ERROR,
    FAILED,
    PASSED,
    CaseInput,
    EngineConfig,
    RateLimiter,
    compute_cost,
    iter_outcomes,
    percentile,
    run_case,
    summarize,
)
from app.domain.providers import MockProvider, ProviderError, ProviderResponse


def _raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return True
    return False


def _case(key, expected="ok", **meta):
    return CaseInput(key=key, input=f"q-{key}", expected=expected, metadata={"mock_output": "ok", **meta})


FAST = EngineConfig(concurrency=4, timeout_s=5, max_retries=2, backoff_base_s=0.0)
NO_SLEEP = lambda s: None  # noqa: E731


def test_config_validation():
    for bad in (dict(concurrency=0), dict(concurrency=65), dict(timeout_s=0), dict(max_retries=6),
                dict(backoff_base_s=-1), dict(requests_per_second=0)):
        assert _raises(ValueError, EngineConfig, **bad), bad


def test_pass_fail_and_scores():
    p = MockProvider()
    ok = run_case(_case("a"), p, FAST, RateLimiter(None), NO_SLEEP)
    bad = run_case(_case("b", expected="different"), p, FAST, RateLimiter(None), NO_SLEEP)
    assert ok.status == PASSED and ok.score == 1.0 and ok.attempts == 1 and ok.error is None
    assert bad.status == FAILED and bad.score == 0.0
    assert bad.score_details["rules"][0]["passed"] is False
    assert ok.latency_ms is not None and ok.cost_usd is not None


def test_retry_then_success_uses_backoff():
    sleeps = []
    cfg = EngineConfig(concurrency=1, timeout_s=5, max_retries=2, backoff_base_s=0.5)
    out = run_case(_case("f", mock_error="flaky:2"), MockProvider(), cfg, RateLimiter(None), sleeps.append)
    assert out.status == PASSED and out.attempts == 3
    assert sleeps == [0.5, 1.0]  # exponential


def test_retries_exhausted_becomes_error_not_exception():
    out = run_case(_case("f", mock_error="flaky:9"), MockProvider(), FAST, RateLimiter(None), NO_SLEEP)
    assert out.status == ERROR and out.attempts == 3 and "ProviderUnavailable" in out.error
    assert out.output is None and out.score is None and out.latency_ms is None and out.cost_usd is None


def test_non_retryable_error_is_not_retried():
    out = run_case(_case("e", mock_error="error"), MockProvider(), FAST, RateLimiter(None), NO_SLEEP)
    assert out.status == ERROR and out.attempts == 1


def test_timeout_is_retried_then_reported():
    out = run_case(_case("t", mock_error="timeout"), MockProvider(), FAST, RateLimiter(None), NO_SLEEP)
    assert out.status == ERROR and out.attempts == 3 and "ProviderTimeout" in out.error


def test_unexpected_adapter_exception_is_contained():
    class Broken:
        name, model, pricing = "broken", "b", None

        def generate(self, request, timeout_s):
            raise RuntimeError("secret prompt leak: " + request.prompt)

    out = run_case(_case("x"), Broken(), FAST, RateLimiter(None), NO_SLEEP)
    assert out.status == ERROR and "RuntimeError" in out.error
    assert "secret prompt" not in out.error  # error text must not echo prompts


def test_scoring_failure_is_an_error_outcome():
    case = CaseInput(key="n", input="q", expected=None, rules=())
    out = run_case(case, MockProvider(), FAST, RateLimiter(None), NO_SLEEP)
    assert out.status == ERROR and "ScoringError" in out.error


def test_partial_failures_do_not_stop_the_run():
    cases = [_case(str(i), mock_error="error" if i % 3 == 0 else None) for i in range(30)]
    outs = list(iter_outcomes(cases, MockProvider(), FAST, sleep=NO_SLEEP))
    assert len(outs) == 30 and {o.key for o in outs} == {str(i) for i in range(30)}
    assert sum(o.status == ERROR for o in outs) == 10 and sum(o.status == PASSED for o in outs) == 20


def test_concurrency_is_bounded_and_actually_parallel():
    lock, state = threading.Lock(), {"now": 0, "peak": 0}

    class Slow:
        name, model, pricing = "slow", "s", None

        def generate(self, request, timeout_s):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            time.sleep(0.03)
            with lock:
                state["now"] -= 1
            return ProviderResponse("ok")

    cfg = EngineConfig(concurrency=3, timeout_s=5, max_retries=0, backoff_base_s=0)
    outs = list(iter_outcomes([_case(str(i)) for i in range(12)], Slow(), cfg))
    assert len(outs) == 12 and all(o.status == PASSED for o in outs)
    assert 2 <= state["peak"] <= 3


def test_empty_case_list():
    assert list(iter_outcomes([], MockProvider(), FAST)) == []


def test_abandoning_iterator_cancels_remaining_work():
    calls = []

    class Counting:
        name, model, pricing = "c", "c", None

        def generate(self, request, timeout_s):
            calls.append(request.prompt)
            time.sleep(0.01)
            return ProviderResponse("ok")

    cfg = EngineConfig(concurrency=1, timeout_s=5, max_retries=0, backoff_base_s=0)
    it = iter_outcomes([_case(str(i)) for i in range(50)], Counting(), cfg)
    next(it)
    it.close()
    assert len(calls) < 50


def test_rate_limiter_spaces_calls():
    waits = []
    limiter = RateLimiter(2.0, clock=lambda: 0.0, sleep=waits.append)
    for _ in range(3):
        limiter.acquire()
    assert waits == [0.5, 1.0]  # first call free, then 0.5s slots


def test_rate_limiter_disabled():
    waits = []
    RateLimiter(None, sleep=waits.append).acquire()
    assert waits == []


def test_cost_unavailable_vs_zero():
    assert compute_cost(None, 10, 10) is None
    assert compute_cost((1.0, 1.0), None, 10) is None
    assert compute_cost((1.0, 1.0), 0, 0) == 0.0  # measured zero


def test_summary_distinguishes_unavailable_from_zero():
    class Row:
        def __init__(self, status, lat=None, pt=None, ct=None, cost=None):
            self.status, self.latency_ms, self.prompt_tokens, self.completion_tokens, self.cost_usd = status, lat, pt, ct, cost

    nothing = summarize([Row(ERROR), Row(ERROR)])
    assert nothing.pass_rate == 0.0 and nothing.errored == 2
    assert nothing.avg_latency_ms is None and nothing.total_tokens is None and nothing.total_cost_usd is None

    zeros = summarize([Row(PASSED, 0.0, 0, 0, 0.0)])
    assert zeros.avg_latency_ms == 0.0 and zeros.total_tokens == 0 and zeros.total_cost_usd == 0.0

    assert summarize([]).pass_rate is None


def test_summary_aggregates():
    class Row:
        def __init__(self, status, lat, pt, ct, cost):
            self.status, self.latency_ms, self.prompt_tokens, self.completion_tokens, self.cost_usd = status, lat, pt, ct, cost

    rows = [Row(PASSED, 10.0, 1, 2, 0.1), Row(FAILED, 30.0, 3, 4, 0.2), Row(PASSED, 20.0, None, None, None)]
    s = summarize(rows)
    assert (s.total, s.passed, s.failed, s.errored) == (3, 2, 1, 0)
    assert abs(s.pass_rate - 2 / 3) < 1e-9 and s.avg_latency_ms == 20.0
    assert s.total_tokens == 10 and abs(s.total_cost_usd - 0.3) < 1e-9


def test_percentile_nearest_rank():
    vals = list(range(1, 101))
    assert percentile(vals, 50) == 50 and percentile(vals, 95) == 95 and percentile(vals, 100) == 100
    assert percentile([], 50) is None and percentile([7], 95) == 7

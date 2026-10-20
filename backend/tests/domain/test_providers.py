from app.domain.providers import (
    MockProvider,
    ProviderError,
    ProviderRequest,
    ProviderTimeout,
    ProviderUnavailable,
    build_provider,
    provider_names,
)


def _raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    return False


def test_mock_is_deterministic():
    p = MockProvider()
    a = p.generate(ProviderRequest("hello"), 30)
    b = p.generate(ProviderRequest("hello"), 30)
    assert a == b and a.output.startswith("mock-response-")
    assert p.generate(ProviderRequest("other"), 30).output != a.output


def test_mock_output_override_and_usage():
    r = MockProvider().generate(ProviderRequest("q", metadata={"mock_output": "Paris"}), 30)
    assert r.output == "Paris" and r.prompt_tokens == 1 and r.completion_tokens == 2


def test_usage_can_be_unavailable_not_zero():
    r = MockProvider().generate(ProviderRequest("q", metadata={"mock_report_usage": False}), 30)
    assert r.prompt_tokens is None and r.completion_tokens is None


def test_timeout_when_simulated_latency_exceeds_budget():
    assert _raises(ProviderTimeout, MockProvider().generate, ProviderRequest("q", metadata={"mock_latency_ms": 5000}), 1)
    assert _raises(ProviderTimeout, MockProvider().generate, ProviderRequest("q", metadata={"mock_error": "timeout"}), 30)


def test_error_modes():
    assert _raises(ProviderError, MockProvider().generate, ProviderRequest("q", metadata={"mock_error": "error"}), 30)


def test_flaky_fails_n_times_then_succeeds():
    p = MockProvider()
    req = ProviderRequest("q", metadata={"mock_error": "flaky:2"})
    assert _raises(ProviderUnavailable, p.generate, req, 30)
    assert _raises(ProviderUnavailable, p.generate, req, 30)
    assert p.generate(req, 30).output.startswith("mock-response-")


def test_hostile_metadata_is_ignored_safely():
    meta = {"mock_latency_ms": "slow", "mock_output": {"x": 1}, "mock_error": 7}
    assert MockProvider().generate(ProviderRequest("q", metadata=meta), 30).output.startswith("mock-response-")


def test_simulated_latency_uses_injected_sleep():
    slept = []
    MockProvider(simulate_latency=True, sleep=slept.append).generate(ProviderRequest("q", metadata={"mock_latency_ms": 40}), 30)
    assert slept == [0.04]


def test_registry():
    assert "mock" in provider_names()
    assert build_provider("mock", "m").model == "m"
    assert _raises(ValueError, build_provider, "nope", "m")

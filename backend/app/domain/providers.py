"""Provider abstraction and the deterministic mock provider.

Providers receive dataset content strictly as *data*. The platform never interprets
prompts, contexts, or model outputs as instructions.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class ProviderError(Exception):
    """Non-retryable provider failure."""

    retryable = False


class ProviderTimeout(ProviderError):
    retryable = True


class ProviderRateLimited(ProviderError):
    retryable = True


class ProviderUnavailable(ProviderError):
    retryable = True


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    context: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    output: str
    prompt_tokens: int | None = None  # None means "not reported", never "zero"
    completion_tokens: int | None = None


class Provider(Protocol):
    name: str
    model: str
    # (usd per 1k input tokens, usd per 1k output tokens), or None if pricing is unknown
    pricing: tuple[float, float] | None

    def generate(self, request: ProviderRequest, timeout_s: float) -> ProviderResponse: ...


def _num(value: Any, default: float, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return min(max(float(value), lo), hi)


class MockProvider:
    """Deterministic provider for development, tests, and demos (no API key, no network).

    Behaviour is controlled by optional test-case metadata keys:
      mock_output        -> exact text to return (otherwise a stable hash-derived string)
      mock_latency_ms    -> simulated latency (otherwise derived from a hash, 20-99 ms)
      mock_error         -> "error" | "timeout" | "rate_limited" | "flaky:N" (fail N attempts)
      mock_report_usage  -> false to simulate a provider that reports no token usage
    mock_output, mock_latency_ms and mock_error may also be an object keyed by model name
    (e.g. {"mock-1": "Paris", "mock-2": "Lyon"}) so one dataset can simulate different models.
    A model missing from such an object gets the default behaviour.
    Pricing is illustrative only and is NOT real provider pricing.
    """

    name = "mock"
    pricing: tuple[float, float] | None = (0.0005, 0.0015)

    def __init__(
        self,
        model: str = "mock-1",
        simulate_latency: bool = False,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self._simulate_latency = simulate_latency
        self._sleep = sleep
        self._attempts: dict[str, int] = {}
        self._lock = threading.Lock()

    def _for_model(self, value: Any) -> Any:
        """Resolve a per-model object ({"mock-1": ...}) to this model's value, else pass through."""
        return value.get(self.model) if isinstance(value, dict) else value

    def generate(self, request: ProviderRequest, timeout_s: float) -> ProviderResponse:
        meta = request.metadata
        digest = hashlib.sha256(
            f"{self.model}\x00{request.prompt}\x00{request.context or ''}".encode()
        ).hexdigest()
        latency_ms = _num(
            self._for_model(meta.get("mock_latency_ms")), 20 + int(digest[:4], 16) % 80, 0, 600_000
        )
        mode = self._for_model(meta.get("mock_error"))

        if mode == "timeout" or latency_ms / 1000 > timeout_s:
            raise ProviderTimeout(f"simulated call exceeded {timeout_s}s timeout")
        if self._simulate_latency:
            self._sleep(latency_ms / 1000)
        if mode == "error":
            raise ProviderError("simulated provider failure")
        if mode == "rate_limited":
            raise ProviderRateLimited("simulated rate limit")
        if isinstance(mode, str) and mode.startswith("flaky:"):
            try:
                failures = int(mode.split(":", 1)[1])
            except ValueError:
                failures = 0
            with self._lock:
                seen = self._attempts.get(digest, 0)
                self._attempts[digest] = seen + 1
            if seen < failures:
                raise ProviderUnavailable(f"simulated transient failure {seen + 1}/{failures}")

        output = self._for_model(meta.get("mock_output"))
        output = output[:20_000] if isinstance(output, str) else f"mock-response-{digest[:8]}"
        if meta.get("mock_report_usage", True) is False:
            return ProviderResponse(output)
        prompt_tokens = math.ceil(len(request.prompt + (request.context or "")) / 4)
        return ProviderResponse(output, prompt_tokens, math.ceil(len(output) / 4))


_REGISTRY: dict[str, Callable[..., Provider]] = {"mock": MockProvider}


def provider_names() -> list[str]:
    return sorted(_REGISTRY)


def build_provider(name: str, model: str, *, simulate_latency: bool = False) -> Provider:
    factory = _REGISTRY.get(name)
    if factory is None:
        raise ValueError(f"unknown provider {name!r}; available: {provider_names()}")
    if name == "mock":
        return MockProvider(model=model, simulate_latency=simulate_latency)
    return factory(model=model)

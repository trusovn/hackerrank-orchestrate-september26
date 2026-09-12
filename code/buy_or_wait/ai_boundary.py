"""Provider-neutral primitives for validated model calls.

This module intentionally contains no provider SDK, prompt, or financial logic. Raw
model output must pass an operation-specific validator before downstream code uses it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Mapping, Protocol, Sequence, TypeVar, Union


ValidatedValue = TypeVar("ValidatedValue")


class ProviderError(RuntimeError):
    """A model provider failed before returning a usable response."""


@dataclass(frozen=True)
class ModelRequest:
    """Provider-neutral input for one named model operation."""

    operation: str
    correlation_id: str
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.operation.strip():
            raise ValueError("operation must be non-empty")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty")


@dataclass(frozen=True)
class ModelCallMetadata:
    """Non-secret provider metadata safe to retain after validation."""

    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must be non-empty")
        if not self.model.strip():
            raise ValueError("model must be non-empty")
        for field_name in (
            "input_tokens",
            "output_tokens",
            "latency_ms",
            "retry_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")


@dataclass(frozen=True)
class ModelResponse:
    """Raw, untrusted provider output kept inside the validation boundary."""

    content: str
    metadata: ModelCallMetadata


class ModelProvider(Protocol):
    """Replaceable boundary implemented by real adapters and deterministic fakes."""

    def complete(self, request: ModelRequest) -> ModelResponse:
        """Return raw model output or raise ``ProviderError``."""


class OutputValidator(Protocol[ValidatedValue]):
    """Convert raw model text into a semantically validated operation value."""

    def parse(self, content: str) -> ValidatedValue:
        """Return a validated value or raise ``ValueError``."""


@dataclass(frozen=True)
class ValidatedModelResult(Generic[ValidatedValue]):
    """A validated value paired with provider metadata for tracing and usage."""

    value: ValidatedValue
    metadata: ModelCallMetadata


def invoke_validated(
    provider: ModelProvider,
    validator: OutputValidator[ValidatedValue],
    request: ModelRequest,
) -> ValidatedModelResult[ValidatedValue]:
    """Call a provider and expose its content only through the supplied validator."""

    response = provider.complete(request)
    value = validator.parse(response.content)
    return ValidatedModelResult(value=value, metadata=response.metadata)


FakeOutcome = Union[ModelResponse, Exception]


class FakeModelProvider:
    """Deterministic queued provider for unit tests; it never accesses the network."""

    def __init__(self, outcomes: Sequence[FakeOutcome]) -> None:
        self._outcomes = list(outcomes)
        self._calls: list[ModelRequest] = []

    @property
    def calls(self) -> tuple[ModelRequest, ...]:
        return tuple(self._calls)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self._calls.append(request)
        if not self._outcomes:
            raise AssertionError("FakeModelProvider has no queued outcome")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

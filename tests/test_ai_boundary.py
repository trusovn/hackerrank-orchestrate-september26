import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "code"))

from buy_or_wait.ai_boundary import (  # noqa: E402
    FakeModelProvider,
    ModelCallMetadata,
    ModelRequest,
    ModelResponse,
    ProviderError,
    invoke_validated,
)


class DecisionValidator:
    """Small test-only validator; the real feature schema remains undecided."""

    def parse(self, content: str) -> str:
        value = json.loads(content)
        decision = value.get("decision")
        if decision not in {"accept", "reject"}:
            raise ValueError("unsupported decision")
        return decision


class AiBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = ModelRequest(
            operation="test-decision",
            correlation_id="run-1/request-1",
            payload={"input": "fixture"},
        )

    def test_validates_fake_response_and_preserves_metadata(self) -> None:
        response = ModelResponse(
            content='{"decision": "accept"}',
            metadata=ModelCallMetadata(
                provider="fake",
                model="fixture-v1",
                input_tokens=4,
                output_tokens=3,
            ),
        )
        provider = FakeModelProvider([response])

        result = invoke_validated(provider, DecisionValidator(), self.request)

        self.assertEqual("accept", result.value)
        self.assertEqual(response.metadata, result.metadata)
        self.assertFalse(hasattr(result, "content"))
        self.assertEqual((self.request,), provider.calls)

    def test_rejects_malformed_or_semantically_invalid_output(self) -> None:
        for content in ("", "not-json", "{}", '{"decision": "unknown"}'):
            with self.subTest(content=content):
                provider = FakeModelProvider(
                    [
                        ModelResponse(
                            content=content,
                            metadata=ModelCallMetadata(
                                provider="fake", model="fixture-v1"
                            ),
                        )
                    ]
                )
                with self.assertRaises((json.JSONDecodeError, ValueError)):
                    invoke_validated(provider, DecisionValidator(), self.request)

    def test_propagates_provider_error_without_validation(self) -> None:
        provider = FakeModelProvider([ProviderError("fixture timeout")])

        with self.assertRaisesRegex(ProviderError, "fixture timeout"):
            invoke_validated(provider, DecisionValidator(), self.request)

        self.assertEqual((self.request,), provider.calls)

    def test_fake_fails_loudly_when_outcomes_are_exhausted(self) -> None:
        provider = FakeModelProvider([])

        with self.assertRaisesRegex(AssertionError, "no queued outcome"):
            provider.complete(self.request)


if __name__ == "__main__":
    unittest.main()

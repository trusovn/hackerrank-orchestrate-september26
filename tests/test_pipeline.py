"""WP-09A tests: one-case product composition and trace seam.

WP-09A composes the accepted deterministic stages (evidence -> events ->
forecast -> planning -> output build/validate) behind one pure, single-case
``predict_case`` entry point and records a stable canonical policy ID plus a
compact trace. The fail-first contract is that no ``predict_case`` /
``DecisionPolicy`` / ``PredictionTrace`` symbols exist before this suite, so
this module cannot import ``pipeline`` until WP-09A lands.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from buy_or_wait.domain import (  # noqa: E402
    CurrencyCode, Direction, EventRecord, EventStatus, EventType, Flexibility, PaymentMethod,
    ProfileRecord, RequestCase, RequestRecord, RequestScope, RequestType,
)
from buy_or_wait.forecast import (  # noqa: E402
    DEFAULT_FORECAST_POLICY, ForecastPolicy, HorizonEndpoint, IncomeContinuation,
    RecurrenceTiming, UnknownSameDayOrder, VariableSpending,
)
from buy_or_wait.output import (  # noqa: E402
    OUTPUT_COLUMNS, OutputValidationError, parse_output_row, serialize_output_row,
    validate_output_row,
)
from buy_or_wait.pipeline import (  # noqa: E402
    DEFAULT_DECISION_POLICY, DecisionPolicy, PredictionTrace, SELECTED_DECISION_POLICY, predict_case,
)


def d(value: str) -> date:
    return date.fromisoformat(value)


def money(value: str) -> Decimal:
    return Decimal(value)


def synthetic_case(request_id: str = "request_P", *, requested: str = "900") -> RequestCase:
    return RequestCase(
        request=RequestRecord(request_id, "user_P", d("2026-01-10"), RequestType.PURCHASE,
                              money(requested), d("2026-03-01"), True, RequestScope.SAMPLE),
        profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"),
                              frozenset(), frozenset(), frozenset(), frozenset(),
                              (PaymentMethod.FULL_PAYMENT,), None),
        events=(), payment_options=(), messages=(), images=(), relevant_rates=(),
    )


NON_DEFAULT_FORECAST = ForecastPolicy(
    recurrence_timing=RecurrenceTiming.TOLERANT_2_DAY,
    income_continuation=IncomeContinuation.I1_STRICT_RECENT_HISTORY,
    variable_spending=VariableSpending.V1_MAX_CADENCED_OCCURRENCE,
    horizon_endpoint=HorizonEndpoint.DAY_89_INCLUSIVE,
    same_day_order=UnknownSameDayOrder.CREDIT_DEBIT_PAYMENT,
)


class SingleCasePipelineTests(unittest.TestCase):
    def test_valid_synthetic_case_matches_ids_and_validates_row(self) -> None:
        case = synthetic_case()
        trace = predict_case(case)
        self.assertIsInstance(trace, PredictionTrace)
        self.assertEqual(trace.request_id, "request_P")
        self.assertEqual(trace.baseline.request_id, "request_P")
        self.assertEqual(trace.decision.request_id, "request_P")
        self.assertEqual(trace.output_row.request_id, "request_P")
        self.assertEqual(trace.policy_id, DEFAULT_DECISION_POLICY.id)
        validate_output_row(trace.output_row, case, trace.baseline, trace.decision)

    def test_output_row_canonically_renders_and_reparses(self) -> None:
        trace = predict_case(synthetic_case())
        serialized = serialize_output_row(trace.output_row)
        self.assertEqual(list(serialized), list(OUTPUT_COLUMNS))
        reparsed = parse_output_row(serialized)
        self.assertEqual(reparsed, trace.output_row)

    def test_non_default_forecast_changes_policy_id_only_forecast_path(self) -> None:
        case = synthetic_case()
        default_trace = predict_case(case, DEFAULT_DECISION_POLICY)
        policy = replace(DEFAULT_DECISION_POLICY, forecast=NON_DEFAULT_FORECAST)
        changed_trace = predict_case(case, policy)
        self.assertNotEqual(changed_trace.policy_id, default_trace.policy_id)
        self.assertIn("tolerant_2_day", changed_trace.policy_id)
        self.assertEqual(changed_trace.evidence, default_trace.evidence)
        self.assertEqual(changed_trace.normalization, default_trace.normalization)
        self.assertEqual(changed_trace.output_row.request_id, default_trace.output_row.request_id)

    def test_default_alias_is_used_when_policy_omitted(self) -> None:
        case = synthetic_case()
        explicit = predict_case(case, DEFAULT_DECISION_POLICY)
        implicit = predict_case(case)
        self.assertEqual(explicit.policy_id, implicit.policy_id)

    def test_selected_alias_exists_and_matches_default(self) -> None:
        self.assertIs(SELECTED_DECISION_POLICY, DEFAULT_DECISION_POLICY)
        self.assertEqual(SELECTED_DECISION_POLICY.id, DEFAULT_DECISION_POLICY.id)

    def test_stage_failure_propagates_and_publishes_no_row(self) -> None:
        event = EventRecord("e1", "user_P", EventType.EXPENSE, "x", "cat", Direction.DEBIT,
                            money("10"), CurrencyCode.ZAR, d("2026-01-01"), d("2026-01-01"),
                            EventStatus.SETTLED, None, Flexibility.FIXED, None)
        duplicate_case = replace(synthetic_case(), events=(event, event))
        with self.assertRaises(ValueError):
            predict_case(duplicate_case)


if __name__ == "__main__":
    unittest.main()

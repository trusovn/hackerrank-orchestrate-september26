"""WP-08A tests: typed output row, grounded explanation, canonical field codecs.

WP-08A builds and canonically renders one output row with no file I/O and no
independent financial validation. The fail-first contract is that the domain
model cannot type ``wait`` or ``not_recommended`` and that no canonical codecs
exist before this suite; the tests reference ``RecommendedPaymentMethod`` and
``output`` symbols so the module cannot compile before WP-08A exists.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from buy_or_wait.domain import (  # noqa: E402
    AffordabilityStatus, CurrencyCode, OutputRow, Payment, PaymentMethod, ProfileRecord, RecommendedPaymentMethod,
    RequestCase, RequestRecord, RequestScope, RequestType, SpendingChange, SpendingChangeType,
)
from buy_or_wait.forecast import (  # noqa: E402
    BaselineForecast, Checkpoint, PrimitiveMovement,
)
from buy_or_wait.output import (  # noqa: E402
    OUTPUT_COLUMNS, build_output_row, explain_decision, parse_output_row, serialize_output_row,
)
from buy_or_wait.planning import (  # noqa: E402
    CapacityResult, PlanCandidate, PlanningDecision, RecommendationMethod,
    SafetyReplay,
)


def d(value: str) -> date:
    return date.fromisoformat(value)


def money(value: str) -> Decimal:
    return Decimal(value)


def case() -> RequestCase:
    return RequestCase(
        request=RequestRecord("request_P", "user_P", d("2026-01-10"), RequestType.PURCHASE,
                              money("900"), d("2026-03-01"), True, RequestScope.SAMPLE),
        profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"), frozenset(),
                              frozenset(), frozenset(), frozenset(), (PaymentMethod.FULL_PAYMENT,), None),
        events=(), payment_options=(), messages=(), images=(), relevant_rates=(),
    )


def baseline(*moves: PrimitiveMovement, blocked: bool = False) -> BaselineForecast:
    current_case = case()
    cash, reserved, checkpoints = money("1000"), money("0"), []
    for movement in moves:
        cash += movement.cash_delta
        reserved += movement.reserve_delta
        checkpoints.append(Checkpoint(movement.date, movement.phase, cash, reserved, cash - reserved,
                                      cash - reserved - money("100"), None, None, movement.family_id,
                                      movement.source_event_ids, movement.origin, movement.movement_id))
    return BaselineForecast("request_P", d("2026-01-10"), d("2026-04-10"), money("1000"), money("100"),
                            money("0"), (), (), moves, tuple(checkpoints), (), blocked,
                            None if blocked else min(point.headroom for point in checkpoints))


def move(day: str, phase: str, ident: str, cash: str = "0", reserve: str = "0", *, origin: str = "explicit",
         family: str | None = None, source_amount: str | None = None, source_currency: CurrencyCode | None = None,
         source_ids: tuple[str, ...] = ()) -> PrimitiveMovement:
    return PrimitiveMovement(d(day), phase, ident, money(cash), money(reserve), origin, source_ids, (), family,
                             d(day) if source_amount is not None else None,
                             money(source_amount) if source_amount is not None else None, source_currency,
                             CurrencyCode.ZAR if source_amount is not None else None)


def decision(*, method: RecommendationMethod, status: AffordabilityStatus, safe: str = "0",
             earliest: str | None = None, changes: tuple[SpendingChange, ...] = (),
             payments: tuple[Payment, ...] = (), diagnostics: tuple[str, ...] = (),
             option_id: str | None = None) -> PlanningDecision:
    capacity = CapacityResult("request_P", money(safe), d(earliest) if earliest is not None else None, ())
    replay = SafetyReplay("request_P", True, (), money("100"), None, ())
    candidate = (None if method is RecommendationMethod.NOT_RECOMMENDED else
                 PlanCandidate(method, payments, changes, option_id, replay, money("0")))
    return PlanningDecision("request_P", capacity, candidate, status, method, diagnostics)


class OutputRowBuildAndCodecTests(unittest.TestCase):
    # --- fail-first: wait/not_recommended are typed enums --------------------

    def test_wait_and_not_recommended_are_typed_enums(self) -> None:
        self.assertIs(RecommendedPaymentMethod.WAIT.value, "wait")
        self.assertIs(RecommendedPaymentMethod.NOT_RECOMMENDED.value, "not_recommended")
        row = build_output_row(case(), baseline(move("2026-01-10", "opening", "open")),
                               decision(method=RecommendationMethod.WAIT,
                                        status=AffordabilityStatus.AFFORDABLE_LATER, safe="900",
                                        earliest="2026-01-30",
                                        payments=(Payment(d("2026-01-30"), money("900")),)))
        self.assertIs(row.recommended_payment_method, RecommendedPaymentMethod.WAIT)
        self.assertEqual(serialize_output_row(row)["recommended_payment_method"], "wait")

    def test_full_plan_and_not_recommended_methods_map_to_the_output_enum(self) -> None:
        payments = {
            RecommendationMethod.FULL_PAYMENT: (Payment(d("2026-01-10"), money("900")),),
            RecommendationMethod.PARTIAL_PAYMENT: (Payment(d("2026-01-10"), money("500")),
                                                    Payment(d("2026-01-30"), money("400"))),
            RecommendationMethod.INSTALLMENTS: (Payment(d("2026-01-15"), money("300")),
                                                Payment(d("2026-02-04"), money("300")),
                                                Payment(d("2026-02-24"), money("300"))),
        }
        pairs = (
            (RecommendationMethod.FULL_PAYMENT, RecommendedPaymentMethod.FULL_PAYMENT),
            (RecommendationMethod.PARTIAL_PAYMENT, RecommendedPaymentMethod.PARTIAL_PAYMENT),
            (RecommendationMethod.INSTALLMENTS, RecommendedPaymentMethod.INSTALLMENTS),
            (RecommendationMethod.NOT_RECOMMENDED, RecommendedPaymentMethod.NOT_RECOMMENDED),
        )
        for source, expected in pairs:
            with self.subTest(source=source):
                row = build_output_row(
                    case(), baseline(move("2026-01-10", "opening", "open")),
                    decision(method=source, payments=payments.get(source, ()),
                             status=(AffordabilityStatus.AFFORDABLE_WITH_PLAN
                                     if source is RecommendationMethod.NOT_RECOMMENDED
                                     else AffordabilityStatus.AFFORDABLE_NOW)))
                self.assertIs(row.recommended_payment_method, expected)

    # --- canonical lexical rules: scalar and plan amounts -------------------

    def test_scalar_safe_amount_is_plain_trimmed_decimal(self) -> None:
        cases = {
            "620.40": "620.4",
            "500.00": "500",
            "0": "0",
            "0.5": "0.5",
            "900": "900",
            "0.00": "0",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                row = OutputRow("request_P", money(source), AffordabilityStatus.AFFORDABLE_NOW,
                                RecommendedPaymentMethod.FULL_PAYMENT, (), None, (), "explain")
                self.assertEqual(serialize_output_row(row)["amount_safe_to_pay"], expected)

    def test_plan_amount_keeps_two_or_more_fractional_digits_and_integers_omit_decimal(self) -> None:
        row = OutputRow(
            "request_P", money("500"), AffordabilityStatus.AFFORDABLE_WITH_PLAN,
            RecommendedPaymentMethod.INSTALLMENTS,
            (Payment(d("2026-01-10"), money("620.4")), Payment(d("2026-02-10"), money("1.2340"))),
            None, (), "explain")
        self.assertEqual(serialize_output_row(row)["payment_plan"],
                         "2026-01-10:620.40|2026-02-10:1.2340")

    def test_plan_and_actions_never_round_or_use_exponent(self) -> None:
        row = OutputRow(
            "request_P", money("0"), AffordabilityStatus.AFFORDABLE_WITH_PLAN,
            RecommendedPaymentMethod.FULL_PAYMENT,
            (Payment(d("2026-01-10"), money("900")),), None,
            (SpendingChange(SpendingChangeType.REDUCE_TO, "ev1", money("1.2340")),), "explain")
        serialized = serialize_output_row(row)
        self.assertEqual(serialized["payment_plan"], "2026-01-10:900")
        self.assertEqual(serialized["spending_changes_needed"], "reduce_to:ev1:1.2340")

    def test_integer_valued_plan_and_reduce_to_omit_decimal(self) -> None:
        # F-01: Decimal("300.00") / Decimal("10.00") must render as 300 / 10,
        # not 300.00 / 10.00, for plan and reduce_to amounts.
        row = OutputRow(
            "request_P", money("0"), AffordabilityStatus.AFFORDABLE_WITH_PLAN,
            RecommendedPaymentMethod.INSTALLMENTS,
            (Payment(d("2026-01-15"), money("300.00")),
             Payment(d("2026-02-04"), money("300")),
             Payment(d("2026-02-24"), money("300.00"))), None,
            (SpendingChange(SpendingChangeType.REDUCE_TO, "ev1", money("10.00")),), "explain")
        serialized = serialize_output_row(row)
        self.assertEqual(serialized["payment_plan"], "2026-01-15:300|2026-02-04:300|2026-02-24:300")
        self.assertEqual(serialized["spending_changes_needed"], "reduce_to:ev1:10")

    def test_negative_zero_normalizes_to_zero_for_plan_and_reduce_to(self) -> None:
        # F-02: Decimal("-0") and Decimal("-0.00") must not render with a sign.
        # Plan amounts must be positive, so zero reaches the renderer only through
        # reduce_to (zero is a valid reduce_to amount); both paths normalize.
        row = OutputRow(
            "request_P", money("0"), AffordabilityStatus.AFFORDABLE_WITH_PLAN,
            RecommendedPaymentMethod.FULL_PAYMENT,
            (Payment(d("2026-01-15"), money("300")),), None,
            (SpendingChange(SpendingChangeType.REDUCE_TO, "ev1", money("-0")),
             SpendingChange(SpendingChangeType.REDUCE_TO, "ev2", money("-0.00"))), "explain")
        serialized = serialize_output_row(row)
        self.assertEqual(serialized["payment_plan"], "2026-01-15:300")
        self.assertEqual(serialized["spending_changes_needed"], "reduce_to:ev1:0|reduce_to:ev2:0")

    # --- canonical lexical rules: plan/action syntax and ordering ------------

    def test_none_and_empty_earliest_have_only_authorized_meanings(self) -> None:
        row = OutputRow("request_P", money("0"), AffordabilityStatus.NOT_AFFORDABLE,
                        RecommendedPaymentMethod.NOT_RECOMMENDED, (), None, (), "explain")
        serialized = serialize_output_row(row)
        self.assertEqual(serialized["payment_plan"], "none")
        self.assertEqual(serialized["spending_changes_needed"], "none")
        self.assertEqual(serialized["earliest_date_for_full_payment"], "")

    def test_actions_serialize_in_wp07b_canonical_order(self) -> None:
        # Order by (event_id, change_type.value, canonical new amount).
        changes = (
            SpendingChange(SpendingChangeType.STOP, "ev2"),
            SpendingChange(SpendingChangeType.REDUCE_TO, "ev1", money("10")),
        )
        row = OutputRow("request_P", money("0"), AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                        RecommendedPaymentMethod.FULL_PAYMENT,
                        (Payment(d("2026-01-10"), money("900")),), None, changes, "explain")
        self.assertEqual(serialize_output_row(row)["spending_changes_needed"],
                         "reduce_to:ev1:10|stop:ev2")

    # --- encode/decode/encode round trips ------------------------------------

    def test_encode_decode_encode_preserves_typed_values(self) -> None:
        changes = (
            SpendingChange(SpendingChangeType.STOP, "ev_a"),
            SpendingChange(SpendingChangeType.REDUCE_TO, "ev_b", money("10")),
        )
        source = OutputRow("request_P", money("620.40"), AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                           RecommendedPaymentMethod.INSTALLMENTS,
                           (Payment(d("2026-01-15"), money("300")), Payment(d("2026-02-04"), money("300")),
                            Payment(d("2026-02-24"), money("300"))), d("2026-01-30"), changes,
                           "Pay in 3 installments totaling 900 from 2026-01-15 to 2026-02-24; 100 is protected.")
        first = serialize_output_row(source)
        reparsed = parse_output_row(first)
        second = serialize_output_row(reparsed)
        self.assertEqual(first, second)
        self.assertEqual(reparsed.amount_safe_to_pay, money("620.4"))
        self.assertEqual(reparsed.payment_plan, source.payment_plan)
        self.assertEqual(reparsed.spending_changes_needed, source.spending_changes_needed)
        self.assertIs(reparsed.recommended_payment_method, RecommendedPaymentMethod.INSTALLMENTS)
        self.assertEqual(reparsed.earliest_date_for_full_payment, d("2026-01-30"))

    def test_csv_sensitive_explanation_round_trips_unchanged(self) -> None:
        explanation = "comma, quote \" inside, newline\nand more."
        source = OutputRow("request_P", money("0"), AffordabilityStatus.NOT_AFFORDABLE,
                           RecommendedPaymentMethod.NOT_RECOMMENDED, (), None, (), explanation)
        reparsed = parse_output_row(serialize_output_row(source))
        self.assertEqual(reparsed.decision_explanation, explanation)

    def test_columns_are_exactly_the_required_eight(self) -> None:
        self.assertEqual(OUTPUT_COLUMNS, (
            "request_id", "amount_safe_to_pay", "affordability_status", "recommended_payment_method",
            "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed",
            "decision_explanation",
        ))

    # --- malformed text is rejected -------------------------------------------

    def test_parse_rejects_noncanonical_and_invalid_fields(self) -> None:
        good = {
            "request_id": "request_P",
            "amount_safe_to_pay": "620.4",
            "affordability_status": "affordable_with_plan",
            "recommended_payment_method": "installments",
            "payment_plan": "2026-01-15:300|2026-02-04:300|2026-02-24:300",
            "earliest_date_for_full_payment": "2026-01-30",
            "spending_changes_needed": "none",
            "decision_explanation": "explain",
        }
        corruptions: dict[str, dict[str, str]] = {
            "exponent": {**good, "amount_safe_to_pay": "6.2e1"},
            "grouping": {**good, "amount_safe_to_pay": "6,20.4"},
            "padding": {**good, "amount_safe_to_pay": " 620.4"},
            "trailing_zero_scalar": {**good, "amount_safe_to_pay": "620.40"},
            "plan_amount_short": {**good, "payment_plan": "2026-01-15:300.5"},
            "nonchronological": {**good, "payment_plan": "2026-02-04:300|2026-01-15:300"},
            "nonpositive_payment": {**good, "payment_plan": "2026-01-15:0"},
            "bad_date": {**good, "payment_plan": "2026-1-15:300"},
            "bad_enum_status": {**good, "affordability_status": "bogus"},
            "bad_enum_method": {**good, "recommended_payment_method": "bogus"},
            "duplicate_action": {**good, "spending_changes_needed": "stop:ev1|stop:ev1"},
            "malformed_action": {**good, "spending_changes_needed": "stop:ev1:extra"},
            "invalid_change_type": {**good, "spending_changes_needed": "bogus:ev1"},
            "actions_not_canonical": {**good, "spending_changes_needed": "stop:ev2|reduce_to:ev1:10"},
        }
        for label, fields in corruptions.items():
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    parse_output_row(fields)

    # --- explanation classes --------------------------------------------------

    def test_explain_full_now_is_grounded_and_protects_minimum(self) -> None:
        text = explain_decision(case(), baseline(move("2026-01-10", "opening", "open")),
                                decision(method=RecommendationMethod.FULL_PAYMENT,
                                         status=AffordabilityStatus.AFFORDABLE_NOW, safe="900",
                                         payments=(Payment(d("2026-01-10"), money("900")),)))
        self.assertIn("900", text)
        self.assertIn("2026-01-10", text)
        self.assertIn("100 is protected", text)

    def test_explain_full_with_changes_serializes_actions(self) -> None:
        text = explain_decision(
            case(), baseline(move("2026-01-10", "opening", "open")),
            decision(method=RecommendationMethod.FULL_PAYMENT, status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                     safe="900", changes=(SpendingChange(SpendingChangeType.STOP, "dip_event"),),
                     payments=(Payment(d("2026-01-10"), money("900")),)))
        self.assertIn("stop:dip_event", text)
        self.assertIn("100 is protected", text)

    def test_explain_partial_has_both_amounts_and_dates(self) -> None:
        text = explain_decision(
            case(), baseline(move("2026-01-10", "opening", "open")),
            decision(method=RecommendationMethod.PARTIAL_PAYMENT, status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                     safe="500", earliest="2026-01-30",
                     payments=(Payment(d("2026-01-10"), money("500")), Payment(d("2026-01-30"), money("400")))))
        self.assertIn("500", text)
        self.assertIn("400", text)
        self.assertIn("2026-01-10", text)
        self.assertIn("2026-01-30", text)
        self.assertIn("100 is protected", text)

    def test_explain_installments_has_count_total_and_dates(self) -> None:
        payments = (Payment(d("2026-01-15"), money("300")), Payment(d("2026-02-04"), money("300")),
                    Payment(d("2026-02-24"), money("300")))
        text = explain_decision(case(), baseline(move("2026-01-10", "opening", "open")),
                               decision(method=RecommendationMethod.INSTALLMENTS,
                                        status=AffordabilityStatus.AFFORDABLE_WITH_PLAN, safe="0",
                                        payments=payments, option_id="payment_option_02"))
        self.assertIn("3 installments", text)
        self.assertIn("900", text)
        self.assertIn("2026-01-15", text)
        self.assertIn("2026-02-24", text)
        self.assertIn("100 is protected", text)
        # No claim of zero financing cost appears without a supplied zero fee.
        self.assertNotIn("financing", text.lower())

    def test_explain_unchanged_wait_uses_baseline_earliest_date(self) -> None:
        text = explain_decision(case(), baseline(move("2026-01-10", "opening", "open")),
                                decision(method=RecommendationMethod.WAIT,
                                         status=AffordabilityStatus.AFFORDABLE_LATER, safe="0",
                                         earliest="2026-01-30",
                                         payments=(Payment(d("2026-01-30"), money("900")),)))
        self.assertIn("2026-01-30", text)
        self.assertIn("900", text)
        self.assertIn("100 is protected", text)

    def test_explain_changed_wait_does_not_call_date_the_baseline_earliest(self) -> None:
        changed_date = d("2026-01-20")
        text = explain_decision(
            case(), baseline(move("2026-01-10", "opening", "open")),
            decision(method=RecommendationMethod.WAIT, status=AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                     safe="0", earliest="2026-01-30",
                     changes=(SpendingChange(SpendingChangeType.STOP, "dip_event"),),
                     payments=(Payment(changed_date, money("900")),)))
        self.assertIn("2026-01-20", text)
        self.assertIn("stop:dip_event", text)
        self.assertNotIn("baseline", text.lower())

    def test_explain_fallback_reason_classes_are_distinct(self) -> None:
        reasons = {
            "fallback_baseline_uncertified": "unbounded required debit",
            "fallback_possible_after_deadline": "first safe date after deadline",
            "fallback_no_accepted_method": "no accepted eligible method or option",
            "fallback_no_safe_candidate": "no safe complete plan",
        }
        seen: set[str] = set()
        for diagnostic, fragment in reasons.items():
            with self.subTest(diagnostic=diagnostic):
                text = explain_decision(
                    case(), baseline(move("2026-01-10", "opening", "open")),
                    decision(method=RecommendationMethod.NOT_RECOMMENDED,
                             status=AffordabilityStatus.NOT_AFFORDABLE, diagnostics=(diagnostic,)))
                self.assertIn(fragment, text)
                seen.add(text)
        self.assertEqual(len(seen), 4)


if __name__ == "__main__":
    unittest.main()

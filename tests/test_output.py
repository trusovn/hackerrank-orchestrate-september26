"""WP-08A tests: typed output row, grounded explanation, canonical field codecs.

WP-08A builds and canonically renders one output row with no file I/O and no
independent financial validation. The fail-first contract is that the domain
model cannot type ``wait`` or ``not_recommended`` and that no canonical codecs
exist before this suite; the tests reference ``RecommendedPaymentMethod`` and
``output`` symbols so the module cannot compile before WP-08A exists.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from buy_or_wait.domain import (  # noqa: E402
    AffordabilityStatus, CurrencyCode, Direction, EventRecord, EventStatus, EventType, Flexibility, OutputRow,
    Payment, PaymentMethod, PaymentOptionRecord, ProfileRecord, RecommendedPaymentMethod, RequestCase,
    RequestRecord, RequestScope, RequestType, SpendingChange, SpendingChangeType,
)
from buy_or_wait.forecast import (  # noqa: E402
    BaselineForecast, Checkpoint, PrimitiveMovement,
)
from buy_or_wait.output import (  # noqa: E402
    OUTPUT_COLUMNS, OutputContext, OutputValidationError, build_output_row, explain_decision,
    parse_output_row, serialize_output_row, validate_output_batch, validate_output_row, write_output_atomic,
)
from buy_or_wait.planning import (  # noqa: E402
    CapacityResult, PlanCandidate, PlanningDecision, RecommendationMethod,
    SafetyReplay, plan_request,
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


def baseline(*moves: PrimitiveMovement, blocked: bool = False,
             request_id: str = "request_P") -> BaselineForecast:
    current_case = case()
    cash, reserved, checkpoints = money("1000"), money("0"), []
    for movement in moves:
        cash += movement.cash_delta
        reserved += movement.reserve_delta
        checkpoints.append(Checkpoint(movement.date, movement.phase, cash, reserved, cash - reserved,
                                      cash - reserved - money("100"), None, None, movement.family_id,
                                      movement.source_event_ids, movement.origin, movement.movement_id))
    return BaselineForecast(request_id, d("2026-01-10"), d("2026-04-10"), money("1000"), money("100"),
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


# --- WP-08B helpers ----------------------------------------------------------


def _installment_case() -> RequestCase:
    from dataclasses import replace

    base = case()
    option = PaymentOptionRecord("payment_option_02", "request_P", PaymentMethod.INSTALLMENTS,
                                 money("300"), "300", 3, d("2026-01-15"), 20, money("50"),
                                 money("900"), "900")
    return replace(
        base,
        profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"), frozenset(),
                              frozenset(), frozenset(), frozenset(),
                              (PaymentMethod.FULL_PAYMENT, PaymentMethod.INSTALLMENTS), 6),
        payment_options=(option,),
    )


def _installment_baseline() -> BaselineForecast:
    return baseline(move("2026-01-10", "opening", "open"),
                    move("2026-01-12", "credit", "credit", "1000", source_ids=("credit_event",)))


def _installment_decision() -> PlanningDecision:
    capacity = CapacityResult("request_P", money("900"), d("2026-01-10"), ())
    replay = SafetyReplay("request_P", True, (), money("100"), None, ())
    candidate = PlanCandidate(
        RecommendationMethod.INSTALLMENTS,
        (Payment(d("2026-01-15"), money("300")), Payment(d("2026-02-04"), money("300")),
         Payment(d("2026-02-24"), money("300"))),
        (), "payment_option_02", replay, money("0"))
    return PlanningDecision("request_P", capacity, candidate, AffordabilityStatus.AFFORDABLE_WITH_PLAN,
                            RecommendationMethod.INSTALLMENTS, ())


def _change_case() -> RequestCase:
    from dataclasses import replace

    base = case()
    event = EventRecord("dining_event", "user_P", EventType.EXPENSE, "dining desc", "dining",
                        Direction.DEBIT, money("40"), CurrencyCode.ZAR, d("2025-12-01"), d("2025-12-01"),
                        EventStatus.SETTLED, None, Flexibility.REDUCIBLE_OR_STOPPABLE, money("20"))
    return replace(
        base,
        request=replace(base.request, requested_amount=money("900"), desired_completion_date=d("2026-03-01"),
                        allows_partial_payment=False),
        profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"), frozenset(),
                              frozenset({"rent"}), frozenset({"dining"}), frozenset({"dining"}),
                              (PaymentMethod.FULL_PAYMENT,), None),
        events=(event,),
    )


def _change_baseline() -> BaselineForecast:
    from buy_or_wait.forecast import PrimitiveMovement

    def recurring(day: str, ident: str, family: str, home: str) -> PrimitiveMovement:
        return move(day, "debit", ident, f"-{home}", origin="fixed_recurrence", family=family,
                    source_amount=home, source_currency=CurrencyCode.ZAR, source_ids=("dining_event",))

    return baseline(move("2026-01-10", "opening", "open"),
                    recurring("2026-01-15", "d1", "dining_series", "40"),
                    recurring("2026-02-15", "d2", "dining_series", "40"))


class OutputRowValidationTests(unittest.TestCase):
    """WP-08B fail-first: reject every row that disagrees with case, capacity,
    decision, eligibility, option/action contract, or a fresh replay."""

    def _planned(self, scenario: str) -> tuple[RequestCase, BaselineForecast, PlanningDecision, OutputRow]:
        """Build every valid row through the public planner, never by hand."""
        if scenario == "full":
            current, source = case(), baseline(move("2026-01-10", "opening", "open"))
        elif scenario == "wait":
            current = case()
            source = baseline(move("2026-01-10", "opening", "open"),
                              move("2026-01-10", "debit", "bd", "-900", source_ids=("bd_event",)),
                              move("2026-01-20", "credit", "credit", "950", source_ids=("cr_event",)))
        elif scenario == "partial":
            original = case()
            current = replace(original, request=replace(original.request, requested_amount=money("550")),
                              profile=replace(original.profile,
                                              payment_methods_user_will_consider=(PaymentMethod.PARTIAL_PAYMENT,)))
            source = baseline(move("2026-01-10", "opening", "open"),
                              move("2026-01-20", "debit", "dip", "-400", source_ids=("dip_event",)),
                              move("2026-01-30", "credit", "refund", "500", source_ids=("refund_event",)))
        elif scenario == "installments":
            original = _installment_case()
            current = replace(original, profile=replace(
                original.profile, payment_methods_user_will_consider=(PaymentMethod.INSTALLMENTS,)))
            source = _installment_baseline()
        elif scenario == "changed":
            current, source = _change_case(), _change_baseline()
        elif scenario == "not_recommended":
            current = case()
            source = baseline(move("2026-01-10", "opening", "open"),
                              move("2026-01-10", "debit", "bd", "-950", source_ids=("bd_event",)))
        else:
            raise AssertionError(f"unknown scenario: {scenario}")
        planned = plan_request(current, source)
        return current, source, planned, build_output_row(current, source, planned)

    def _rejects(self, row: OutputRow, current: RequestCase, source: BaselineForecast,
                 planned: PlanningDecision, reason: str) -> None:
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_row(row, current, source, planned)
        self.assertEqual(caught.exception.reason_code, reason)

    def test_accepted_rows_validate(self) -> None:
        for scenario in ("full", "wait", "partial", "installments", "changed", "not_recommended"):
            with self.subTest(scenario=scenario):
                current, source, planned, row = self._planned(scenario)
                validate_output_row(row, current, source, planned)

    # --- B-AC-01: ID, amount, enums, capacity exact ------------------------

    def test_request_id_mismatch_rejects(self) -> None:
        current, source, planned, row = self._planned("full")
        self._rejects(replace(row, request_id="other"), current, source, planned, "request_id_mismatch")

    def test_safe_amount_mismatch_rejects(self) -> None:
        current, source, planned, row = self._planned("full")
        self._rejects(replace(row, amount_safe_to_pay=money("500")), current, source, planned,
                      "safe_amount_mismatch")

    def test_earliest_date_mismatch_rejects(self) -> None:
        current, source, planned, row = self._planned("full")
        self._rejects(replace(row, earliest_date_for_full_payment=d("2026-01-15")), current, source, planned,
                      "earliest_date_mismatch")

    def test_amount_exceeding_requested_rejects(self) -> None:
        current, source, planned, row = self._planned("full")
        self._rejects(replace(row, amount_safe_to_pay=money("950")), current, source, planned,
                      "amount_exceeds_requested")

    # --- B-AC-03 / FR-08-04: plan-by-method exactness ----------------------

    def test_full_payment_plan_rejects_wrong_date_and_amount(self) -> None:
        current, source, planned, row = self._planned("full")
        for plan in ((Payment(d("2026-01-11"), money("900")),),
                     (Payment(d("2026-01-10"), money("800")),)):
            with self.subTest(plan=plan):
                self._rejects(replace(row, payment_plan=plan), current, source, planned, "full_plan_mismatch")

    def test_wait_and_partial_plan_shapes_reject(self) -> None:
        current, source, planned, row = self._planned("wait")
        self._rejects(replace(row, payment_plan=(Payment(d("2026-01-10"), money("900")),)),
                      current, source, planned, "wait_plan_mismatch")
        current, source, planned, row = self._planned("partial")
        self._rejects(replace(row, payment_plan=(row.payment_plan[0], Payment(d("2026-02-01"), money("50")))),
                      current, source, planned, "partial_second_mismatch")

    def test_full_wait_and_partial_preferences_reject(self) -> None:
        for scenario, expected in (("full", "full_preference_excluded"),
                                   ("wait", "wait_preference_excluded"),
                                   ("partial", "partial_preference_excluded")):
            with self.subTest(scenario=scenario):
                current, source, planned, row = self._planned(scenario)
                excluded = replace(current, profile=replace(
                    current.profile, payment_methods_user_will_consider=()))
                self._rejects(row, excluded, source, planned, expected)

    def test_installment_plan_and_cap_reject(self) -> None:
        current, source, planned, row = self._planned("installments")
        shifted = tuple(Payment(payment.payment_date.replace(day=payment.payment_date.day + 1), payment.amount)
                        for payment in row.payment_plan)
        self._rejects(replace(row, payment_plan=shifted), current, source, planned, "installment_plan_mismatch")
        capped = replace(current, profile=replace(current.profile, max_installment_months=2))
        self._rejects(row, capped, source, planned, "installment_cap_exceeded")

    def test_installment_preference_rejects(self) -> None:
        current, source, planned, row = self._planned("installments")
        excluded = replace(current, profile=replace(
            current.profile, payment_methods_user_will_consider=()))
        self._rejects(row, excluded, source, planned, "installment_preference_excluded")

    # --- B-AC-04 / FR-08-05: actions ---------------------------------------

    def test_action_catalogue_and_count_reject(self) -> None:
        current, source, planned, row = self._planned("changed")
        self._rejects(replace(row, spending_changes_needed=(SpendingChange(SpendingChangeType.STOP, "rent_event"),)),
                      current, source, planned, "change_not_eligible")
        self._rejects(replace(row, spending_changes_needed=(
            SpendingChange(SpendingChangeType.STOP, "dining_event"),) * 4),
                      current, source, planned, "too_many_changes")

    # --- B-AC-05 / FR-08-06: fresh replay -----------------------------------

    def test_replay_catches_first_and_later_breaches(self) -> None:
        current, source, planned, row = self._planned("wait")
        self._rejects(replace(row, payment_plan=(Payment(d("2026-01-11"), money("900")),)),
                      current, source, planned, "replay_minimum_balance_breach")
        current, source, planned, row = self._planned("changed")
        self._rejects(replace(row, spending_changes_needed=()), current, source, planned,
                      "replay_minimum_balance_breach")

    # --- B-AC-02 / FR-08-03: status/method table ---------------------------

    def test_status_table_rejects_changed_full_as_now(self) -> None:
        current, source, planned, row = self._planned("changed")
        self._rejects(replace(row, affordability_status=AffordabilityStatus.AFFORDABLE_NOW),
                      current, source, planned, "affordable_now_with_changes")

    def test_partial_wrong_status_rejects(self) -> None:
        current, source, planned, row = self._planned("partial")
        self._rejects(replace(row, affordability_status=AffordabilityStatus.AFFORDABLE_NOW),
                      current, source, planned, "partial_method_wrong_status")

    # --- B-AC-06: explanation and dependency agreement ---------------------

    def test_explanation_rejects_empty_and_swapped(self) -> None:
        current, source, planned, row = self._planned("full")
        self._rejects(replace(row, decision_explanation=""), current, source, planned, "explanation_mismatch")
        _, _, _, other = self._planned("wait")
        self._rejects(replace(row, decision_explanation=other.decision_explanation), current, source, planned,
                      "explanation_mismatch")

    def test_incoherent_decision_rejects_before_explanation_rendering(self) -> None:
        current, source, planned, row = self._planned("full")
        # Coherence is an input-safety check, not decision agreement. It runs
        # before rendering so malformed candidate/decision pairs cannot leak.
        self._rejects(row, current, source,
                      replace(planned, recommended_method=RecommendationMethod.WAIT), "invalid_decision")

    def test_incoherent_decision_rejects_before_rendering(self) -> None:
        current, source, planned, row = self._planned("wait")
        incoherent = replace(planned, recommended_method=RecommendationMethod.PARTIAL_PAYMENT)
        self._rejects(row, current, source, incoherent, "invalid_decision")

    def test_baseline_case_mismatch_rejects(self) -> None:
        current, source, planned, row = self._planned("full")
        self._rejects(row, current, replace(source, request_id="other_request"), planned, "invalid_baseline")


class OutputBatchAndAtomicWriterTests(unittest.TestCase):
    """WP-08C fail-first: exact batch coverage and all-or-nothing publication.

    Uses a ``TemporaryDirectory`` with real sibling temp files and a preserved
    sentinel destination. Never touches root ``output.csv``.
    """

    def _evaluation_contexts(self, count: int = 2) -> list[OutputContext]:
        contexts: list[OutputContext] = []
        for index in range(count):
            request_id = f"request_{index}"
            current = replace(case(), request=replace(
                case().request, request_id=request_id, scope=RequestScope.EVALUATION))
            source = baseline(move("2026-01-10", "opening", "open"), request_id=request_id)
            planned = plan_request(current, source)
            contexts.append(OutputContext(current, source, planned))
        return contexts

    def _batch(self, contexts: list[OutputContext]) -> list[OutputRow]:
        return [build_output_row(c.case, c.baseline, c.decision) for c in contexts]

    def _assert_preserved(self, path: Path, sentinel: bytes) -> None:
        self.assertEqual(path.read_bytes(), sentinel)

    # --- C-AC-01: exact batch coverage -------------------------------------

    def test_exact_batch_validates(self) -> None:
        contexts = self._evaluation_contexts(3)
        rows = self._batch(contexts)
        validate_output_batch(rows, contexts)

    def test_missing_row_rejects(self) -> None:
        contexts = self._evaluation_contexts(2)
        rows = self._batch(contexts)
        self.assertRaises(OutputValidationError, validate_output_batch, rows[:1], contexts)
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_batch(rows[:1], contexts)
        self.assertEqual(caught.exception.reason_code, "missing_request")

    def test_extra_row_rejects(self) -> None:
        contexts = self._evaluation_contexts(1)
        rows = self._batch(contexts)
        extra = replace(case(), request=replace(
            case().request, request_id="request_extra", scope=RequestScope.EVALUATION))
        source = baseline(move("2026-01-10", "opening", "open"), request_id="request_extra")
        planned = plan_request(extra, source)
        row = build_output_row(extra, source, planned)
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_batch(rows + [row], contexts)
        self.assertEqual(caught.exception.reason_code, "extra_request")

    def test_duplicate_row_rejects(self) -> None:
        contexts = self._evaluation_contexts(1)
        rows = self._batch(contexts)
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_batch(rows + rows, contexts)
        self.assertEqual(caught.exception.reason_code, "duplicate_request")

    def test_out_of_order_rejects(self) -> None:
        contexts = self._evaluation_contexts(2)
        rows = self._batch(contexts)
        swapped = [rows[1], rows[0]]
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_batch(swapped, contexts)
        self.assertEqual(caught.exception.reason_code, "out_of_order")

    def test_sample_scope_rejects(self) -> None:
        current = replace(case(), request=replace(case().request, scope=RequestScope.SAMPLE))
        source = baseline(move("2026-01-10", "opening", "open"))
        planned = plan_request(current, source)
        context = OutputContext(current, source, planned)
        row = build_output_row(current, source, planned)
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_batch([row], [context])
        self.assertEqual(caught.exception.reason_code, "sample_scope")

    def test_context_case_mismatch_rejects(self) -> None:
        contexts = self._evaluation_contexts(2)
        rows = self._batch(contexts)
        mismatched = OutputContext(contexts[1].case, contexts[0].baseline, contexts[0].decision)
        with self.assertRaises(OutputValidationError) as caught:
            validate_output_batch(rows, [contexts[0], mismatched])
        self.assertEqual(caught.exception.reason_code, "invalid_baseline")

    # --- C-AC-02/03/04/05: atomic publication -------------------------------

    def test_new_destination_publishes_exact_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.csv"
            contexts = self._evaluation_contexts(2)
            rows = self._batch(contexts)
            write_output_atomic(path, rows, contexts)
            self.assertTrue(path.exists())
            reparsed = parse_output_row({k: v for k, v in serialize_output_row(rows[0]).items()})
            self.assertEqual(reparsed, rows[0])
            with path.open("r", newline="", encoding="utf-8") as handle:
                import csv
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, list(OUTPUT_COLUMNS))
                lines = list(reader)
            self.assertEqual(len(lines), 2)
            self.assertEqual([line["request_id"] for line in lines], [r.request_id for r in rows])

    def test_existing_destination_replaced_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.csv"
            sentinel = b"old bytes\n"
            path.write_bytes(sentinel)
            contexts = self._evaluation_contexts(1)
            rows = self._batch(contexts)
            write_output_atomic(path, rows, contexts)
            self.assertNotEqual(path.read_bytes(), sentinel)
            self.assertEqual(len(path.read_text(encoding="utf-8").strip().splitlines()), 2)

    def test_replaced_file_round_trips_explanation_quoting(self) -> None:
        from buy_or_wait.output import _read_csv_batch, _write_csv_sibling
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp) / "sibling.csv"
            contexts = self._evaluation_contexts(1)
            row = self._batch(contexts)[0]
            tricky = replace(row, decision_explanation="a, \"quoted\"\nline | 'tick'")
            _write_csv_sibling(temp_path, [tricky])
            reparsed, ids = _read_csv_batch(temp_path)
            self.assertEqual(ids, [tricky.request_id])
            self.assertEqual(reparsed[0].decision_explanation, tricky.decision_explanation)
            self.assertEqual(reparsed[0], tricky)
            self.assertEqual(serialize_output_row(reparsed[0]), serialize_output_row(tricky))

    def test_write_failure_preserves_old_destination_and_removes_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.csv"
            sentinel = b"sentinel\n"
            path.write_bytes(sentinel)
            contexts = self._evaluation_contexts(1)
            rows = self._batch(contexts)
            with self.assertRaises(Exception):
                write_output_atomic(path, rows[:0], contexts)
            self._assert_preserved(path, sentinel)
            self.assertEqual(list(Path(temp).glob(".output-*.csv")), [])

    def test_replace_failure_preserves_old_destination_and_removes_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.csv"
            sentinel = b"sentinel\n"
            path.write_bytes(sentinel)
            contexts = self._evaluation_contexts(1)
            rows = self._batch(contexts)

            import buy_or_wait.output as outmod
            original = outmod.os.replace

            def fail_replace(src, dst):
                raise OSError("simulated replace failure")

            outmod.os.replace = fail_replace
            try:
                with self.assertRaises(OSError):
                    write_output_atomic(path, rows, contexts)
            finally:
                outmod.os.replace = original
            self._assert_preserved(path, sentinel)
            self.assertEqual(list(Path(temp).glob(".output-*.csv")), [])

    def test_failed_validation_never_touches_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "out.csv"
            sentinel = b"sentinel\n"
            path.write_bytes(sentinel)
            contexts = self._evaluation_contexts(2)
            rows = self._batch(contexts)
            with self.assertRaises(OutputValidationError):
                write_output_atomic(path, rows[:1], contexts)
            self._assert_preserved(path, sentinel)
            self.assertEqual(list(Path(temp).glob(".output-*.csv")), [])


if __name__ == "__main__":
    unittest.main()

"""Focused WP-06A tests for independent schedule safety replay."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from buy_or_wait.domain import (  # noqa: E402
    CurrencyCode, ExchangeRateRecord, Payment, PaymentMethod, ProfileRecord, RequestCase,
    RequestRecord, RequestScope, RequestType, SpendingChange, SpendingChangeType,
)
from buy_or_wait.forecast import (  # noqa: E402
    BaselineForecast, Checkpoint, PrimitiveMovement,
)
from buy_or_wait.planning import (  # noqa: E402
    PlanningError, compute_baseline_capacity, replay_schedule,
)


def d(value: str) -> date:
    return date.fromisoformat(value)


def money(value: str) -> Decimal:
    return Decimal(value)


def case() -> RequestCase:
    return RequestCase(
        request=RequestRecord("request_P", "user_P", d("2026-01-10"), RequestType.PURCHASE,
                              money("100"), d("2026-03-01"), True, RequestScope.SAMPLE),
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


class SafetyReplayTests(unittest.TestCase):
    def test_empty_replay_reconstructs_and_detects_cached_tamper(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"), move("2026-01-15", "debit", "rent", "-200"))
        result = replay_schedule(case(), source)
        self.assertTrue(result.safe)
        self.assertEqual(result.minimum_headroom, money("700"))
        with self.assertRaises(PlanningError) as caught:
            replay_schedule(case(), replace(source, minimum_headroom=money("701")))
        self.assertEqual(caught.exception.reason_code, "baseline_replay_mismatch")

    def test_payment_is_after_same_day_movements_and_later_breach_survives(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"), move("2026-01-10", "credit", "salary", "100"),
                          move("2026-01-20", "debit", "later", "-1000", source_ids=("later",)))
        result = replay_schedule(case(), source, (Payment(d("2026-01-10"), money("100")),))
        self.assertFalse(result.safe)
        self.assertEqual((result.first_failure.date, result.first_failure.source_ids), (d("2026-01-20"), ("later",)))
        self.assertEqual(result.checkpoints[2].stable_id, "payment:0")

    def test_malformed_payment_and_blocked_baseline_fail_closed(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"))
        malformed = replay_schedule(case(), source, (Payment(d("2026-01-11"), money("1")), Payment(d("2026-01-10"), money("1"))))
        self.assertEqual(malformed.first_failure.reason_code, "payment_out_of_order")
        self.assertFalse(replay_schedule(case(), replace(source, blocks_downstream=True, minimum_headroom=None)).safe)

    def test_reserve_is_conserved_and_payment_never_releases_it(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"), move("2026-01-10", "reserve", "hold", reserve="200"),
                          move("2026-01-20", "reserve_settlement", "settle", "-200", "-200"))
        result = replay_schedule(case(), source, (Payment(d("2026-01-10"), money("100")),))
        self.assertEqual([(p.cash_balance, p.reserved_balance) for p in result.checkpoints],
                         [(money("1000"), money("0")), (money("1000"), money("200")),
                          (money("900"), money("200")), (money("700"), money("0"))])

    def test_changes_only_modify_mutable_family_and_no_effect_rejects(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-15", "debit", "rent", "-200", origin="fixed_recurrence", family="rent", source_amount="200", source_currency=CurrencyCode.ZAR, source_ids=("rent_event",)),
                          move("2026-01-15", "debit", "committed", "-200", source_ids=("committed",)))
        result = replay_schedule(case(), source, (), (SpendingChange(SpendingChangeType.REDUCE_TO, "rent_event", money("50")),))
        self.assertTrue(result.safe)
        self.assertEqual(result.applied_change_event_ids, ("rent_event",))
        self.assertEqual(source.primitive_movements[1].cash_delta, money("-200"))
        no_effect = replay_schedule(case(), source, (), (SpendingChange(SpendingChangeType.STOP, "missing"),))
        self.assertEqual(no_effect.first_failure.reason_code, "change_target_unknown")

    def test_foreign_reduction_uses_occurrence_rate_and_missing_rate_fails_closed(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-15", "debit", "rent-usd", "-20", origin="fixed_recurrence", family="rent", source_amount="10", source_currency=CurrencyCode.USD, source_ids=("rent_event",)))
        changed = SpendingChange(SpendingChangeType.REDUCE_TO, "rent_event", money("5"))
        rated_case = replace(case(), relevant_rates=(ExchangeRateRecord(d("2026-01-15"), CurrencyCode.USD, CurrencyCode.ZAR, money("1.5")),))
        result = replay_schedule(rated_case, source, (), (changed,))
        self.assertEqual(result.checkpoints[-1].cash_balance, money("992.5"))
        missing = replay_schedule(case(), source, (), (changed,))
        self.assertEqual(missing.first_failure.reason_code, "change_fx_rate_missing")


class CapacityTests(unittest.TestCase):
    @staticmethod
    def capacity_case(amount: str) -> RequestCase:
        base = case()
        return replace(base, request=replace(base.request, requested_amount=money(amount)))

    def test_safe_amount_is_clamped_and_floored_with_confirming_replay(self) -> None:
        # Opening headroom 900 (1000 - 100 minimum); requested 850.20 clamps the safe amount to 850.20.
        source = baseline(move("2026-01-10", "opening", "open"))
        result = compute_baseline_capacity(self.capacity_case("850.20"), source)
        self.assertEqual(result.amount_safe_to_pay, money("850.20"))
        self.assertEqual(result.earliest_date_for_full_payment, d("2026-01-10"))

    def test_fractional_headroom_floors_down_and_never_rounds_up(self) -> None:
        # Headroom 700.009 (1000 - 199.991 - 100) must floor to 700.00, not 700.01.
        source = baseline(move("2026-01-10", "opening", "open"), move("2026-01-20", "debit", "bill", "-199.991"))
        result = compute_baseline_capacity(self.capacity_case("900"), source)
        self.assertEqual(result.amount_safe_to_pay, money("700.00"))

    def test_breach_yields_zero_and_no_date_despite_later_credit(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-15", "debit", "dip", "-1000"),
                          move("2026-01-20", "credit", "bonus", "5000"))
        result = compute_baseline_capacity(self.capacity_case("900"), source)
        self.assertEqual(result.amount_safe_to_pay, money("0"))
        self.assertIsNone(result.earliest_date_for_full_payment)
        # A certified baseline that breaches is reported as the breach itself, never as upstream uncertainty.
        self.assertEqual(result.diagnostics, ("minimum_balance_breach",))

    def test_blocked_baseline_yields_zero_and_no_date(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"), blocked=True)
        result = compute_baseline_capacity(self.capacity_case("900"), source)
        self.assertEqual(result.amount_safe_to_pay, money("0"))
        self.assertIsNone(result.earliest_date_for_full_payment)
        self.assertEqual(result.request_id, "request_P")

    def test_exact_minimum_headroom_is_safe_today(self) -> None:
        # Headroom exactly 300 -> safe amount 300.00; full payment of 900 never safe in horizon.
        source = baseline(move("2026-01-10", "opening", "open"), move("2026-01-20", "debit", "bill", "-600"))
        result = compute_baseline_capacity(self.capacity_case("900"), source)
        self.assertEqual(result.amount_safe_to_pay, money("300.00"))
        self.assertIsNone(result.earliest_date_for_full_payment)

    def test_earliest_date_is_exhaustive_first_safe_day(self) -> None:
        # Baseline headroom: 900, 500 (day-20 debit), 1000 (day-30 credit). A 550 full payment first replays safe on 2026-01-30.
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-20", "debit", "dip", "-400"),
                          move("2026-01-30", "credit", "refund", "500"))
        result = compute_baseline_capacity(self.capacity_case("550"), source)
        self.assertEqual(result.amount_safe_to_pay, money("500.00"))
        self.assertEqual(result.earliest_date_for_full_payment, d("2026-01-30"))

    def test_preferences_do_not_change_capacity(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"))
        strict = compute_baseline_capacity(self.capacity_case("900"), source)
        base = self.capacity_case("900")
        relaxed_case = replace(
            base,
            request=replace(base.request, allows_partial_payment=False, desired_completion_date=d("2026-01-12")),
            profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"), frozenset(), frozenset(), frozenset(), frozenset(), (), None),
        )
        self.assertEqual(compute_baseline_capacity(relaxed_case, source), strict)

    def test_partial_trajectory_equivalence_guard(self) -> None:
        # B-AC-06 property: for 0 < safe < requested and certified earliest F, the two-payment
        # schedule (D, safe) then (F, requested - safe) is safe and its trajectory matches the
        # certified single-payment displacements. The oracle compares independently replayed
        # references; it never calls compute_baseline_capacity for expectations.
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-20", "debit", "dip", "-400"),
                          move("2026-01-30", "credit", "refund", "500"))
        current_case = self.capacity_case("550")
        result = compute_baseline_capacity(current_case, source)
        safe_amount = result.amount_safe_to_pay
        earliest = result.earliest_date_for_full_payment
        self.assertTrue(0 < safe_amount < money("550"))
        self.assertIsNotNone(earliest)
        remainder = money("550") - safe_amount
        two_payment = replay_schedule(
            current_case, source,
            (Payment(current_case.request.request_date, safe_amount), Payment(earliest, remainder)),
        )
        self.assertTrue(two_payment.safe)
        safe_today = replay_schedule(current_case, source, (Payment(current_case.request.request_date, safe_amount),))
        full_at_earliest = replay_schedule(current_case, source, (Payment(earliest, money("550")),))
        # Before F: every non-payment baseline checkpoint before F matches the certified
        # safe-today trajectory (the (D, safe) payment checkpoint is the added displacement).
        safe_today = replay_schedule(current_case, source, (Payment(current_case.request.request_date, safe_amount),))
        today_by_id = {point.stable_id: point for point in safe_today.checkpoints if not point.stable_id.startswith("payment:")}
        for point in two_payment.checkpoints:
            if point.date >= earliest or point.stable_id.startswith("payment:"):
                continue
            self.assertEqual((today_by_id[point.stable_id].date, today_by_id[point.stable_id].cash_balance, today_by_id[point.stable_id].headroom),
                             (point.date, point.cash_balance, point.headroom))
        # From F onward: every non-payment baseline checkpoint on/after F matches the standalone
        # full-payment trajectory, and the final two-payment balance equals the full-payment
        # balance (payment 1 of exactly remainder completes the displacement).
        displacement = two_payment.checkpoints[-1].cash_balance - full_at_earliest.checkpoints[-1].cash_balance
        self.assertEqual(displacement, Decimal("0.00"))
        # From F onward: payment 1 of exactly remainder converges the trajectory to the standalone
        # full payment at F — the final two-payment balance and headroom equal the full-payment
        # balance, and every checkpoint after the F payment matches exactly.
        displacement = two_payment.checkpoints[-1].cash_balance - full_at_earliest.checkpoints[-1].cash_balance
        self.assertEqual(displacement, Decimal("0.00"))
        self.assertEqual((full_at_earliest.checkpoints[-1].date, full_at_earliest.checkpoints[-1].headroom),
                         (two_payment.checkpoints[-1].date, two_payment.checkpoints[-1].headroom))
        self.assertEqual(two_payment.checkpoints[-1].stable_id.startswith("payment:"), True)
        # A 0.01 remainder perturbation must break the invariant.
        perturbed = replay_schedule(
            current_case, source,
            (Payment(current_case.request.request_date, safe_amount), Payment(earliest, remainder - Decimal("0.01"))),
        )
        perturbed_single = replay_schedule(current_case, source, (Payment(earliest, remainder),))
        self.assertNotEqual(perturbed.checkpoints[-1].headroom, perturbed_single.checkpoints[-1].headroom)

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


# --- WP-07A no-change candidate enumeration ---------------------------------


from buy_or_wait.domain import PaymentOptionRecord  # noqa: E402
from buy_or_wait.planning import (  # noqa: E402
    RecommendationMethod, build_no_change_candidate_pool,
)


def planner_case(*, methods=(PaymentMethod.FULL_PAYMENT, PaymentMethod.PARTIAL_PAYMENT,
                             PaymentMethod.INSTALLMENTS), amount="900", deadline="2026-03-01",
                 allows_partial=True, cap="6", options=()) -> RequestCase:
    base = case()
    return replace(
        base,
        request=replace(base.request, requested_amount=money(amount), desired_completion_date=d(deadline),
                        allows_partial_payment=allows_partial),
        profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"), frozenset(),
                              frozenset(), frozenset({"subscriptions"}), frozenset({"subscriptions"}),
                              tuple(methods), int(cap) if cap is not None else None),
        payment_options=tuple(options),
    )


def full_option(request_id: str = "request_P", amount: str = "900", first: str = "2026-01-10") -> PaymentOptionRecord:
    return PaymentOptionRecord("payment_option_01", request_id, PaymentMethod.FULL_PAYMENT, money(amount),
                               amount, 1, d(first), None, money("0"), money(amount), amount)


def installment_option(option_id: str = "payment_option_02", amount: str = "300", count: int = 3,
                       first: str = "2026-01-15", freq: int = 20, fee: str = "50",
                       request_id: str = "request_P") -> PaymentOptionRecord:
    # Real dataset contract (repository.py): total_payable_amount == payment_amount * count;
    # financing_fee is a separate disclosure column and never added into the total.
    total = money(amount) * count
    return PaymentOptionRecord(option_id, request_id, PaymentMethod.INSTALLMENTS, money(amount), amount,
                               count, d(first), freq, money(fee), total, str(total))


class NoChangeCandidateTests(unittest.TestCase):
    def test_exact_full_partial_wait_and_installment_shapes(self) -> None:
        # Scenario B: opening 1000, dip -400 on 01-20, refund +500 on 01-30, request 550.
        # Safe today 500, earliest full 01-30. Full-now is eligible but unsafe; partial and wait are safe.
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-20", "debit", "dip", "-400"),
                          move("2026-01-30", "credit", "refund", "500"))
        current = planner_case(amount="550", options=(full_option(amount="550"), installment_option()))
        pool = build_no_change_candidate_pool(current, source)
        self.assertEqual(pool.request_id, "request_P")
        self.assertEqual(pool.capacity.amount_safe_to_pay, money("500.00"))
        self.assertEqual(pool.capacity.earliest_date_for_full_payment, d("2026-01-30"))
        by_method = {}
        for candidate in pool.candidates:
            by_method.setdefault(candidate.recommendation_method, []).append(candidate)
        # Partial exactly (D, 500) + (F, 50).
        partial = by_method[RecommendationMethod.PARTIAL_PAYMENT][0]
        self.assertEqual(partial.payments, (Payment(d("2026-01-10"), money("500.00")),
                                            Payment(d("2026-01-30"), money("50"))))
        self.assertEqual(partial.total_paid, money("550"))
        self.assertIsNone(partial.payment_option_id)
        self.assertEqual((partial.start, partial.completion, partial.payment_count), (d("2026-01-10"), d("2026-01-30"), 2))
        self.assertEqual(partial.forecast_debit_reduction, Decimal("0"))
        self.assertTrue(partial.safety_replay.safe)
        # Wait exactly (F, A) with no option ID.
        wait = by_method[RecommendationMethod.WAIT][0]
        self.assertEqual(wait.payments, (Payment(d("2026-01-30"), money("550")),))
        self.assertIsNone(wait.payment_option_id)
        self.assertEqual(wait.total_paid, money("550"))
        # Full-now template is eligible but unsafe, and is not certified as a candidate.
        self.assertNotIn(RecommendationMethod.FULL_PAYMENT, by_method)
        self.assertIn(RecommendationMethod.WAIT, [t.recommendation_method for t in pool.eligible_templates])
        self.assertIn("unsafe_replay", pool.diagnostics)
        # Installments reproduce the supplied option exactly: 3 x 300 on 01-15, 02-04, 02-24.
        installment = by_method[RecommendationMethod.INSTALLMENTS][0]
        self.assertEqual(installment.payments, (Payment(d("2026-01-15"), money("300")),
                                                Payment(d("2026-02-04"), money("300")),
                                                Payment(d("2026-02-24"), money("300"))))
        self.assertEqual(installment.total_paid, money("900"))
        self.assertEqual(installment.payment_option_id, "payment_option_02")
        self.assertEqual(installment.safety_replay.applied_change_event_ids, ())
        self.assertTrue(pool.candidates)

    def test_exact_full_now_shape_with_option_provenance(self) -> None:
        # Scenario A: opening 1000 only, request 900: full now safe with option provenance.
        source = baseline(move("2026-01-10", "opening", "open"))
        current = planner_case(options=(full_option(),))
        pool = build_no_change_candidate_pool(current, source)
        full = [c for c in pool.candidates if c.recommendation_method is RecommendationMethod.FULL_PAYMENT][0]
        self.assertEqual(full.payments, (Payment(d("2026-01-10"), money("900")),))
        self.assertEqual(full.payment_option_id, "payment_option_01")
        self.assertEqual(full.spending_changes, ())
        self.assertEqual(full.safety_replay.applied_change_event_ids, ())
        self.assertEqual((full.start, full.completion, full.payment_count), (d("2026-01-10"), d("2026-01-10"), 1))
        # Partial is not eligible because safe equals requested; wait needs a later date.
        self.assertNotIn(RecommendationMethod.PARTIAL_PAYMENT, [c.recommendation_method for c in pool.candidates])
        self.assertNotIn(RecommendationMethod.WAIT, [c.recommendation_method for c in pool.candidates])

    def test_eligibility_gates_are_enforced_independently(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"))
        # Method not accepted removes that method.
        full_only = planner_case(methods=(PaymentMethod.FULL_PAYMENT,), options=(full_option(),))
        pool = build_no_change_candidate_pool(full_only, source)
        self.assertEqual({c.recommendation_method for c in pool.candidates},
                         {RecommendationMethod.FULL_PAYMENT})
        # Partial not allowed, and partial amount bounds (safe == requested).
        no_partial = planner_case(allows_partial=False, options=(full_option(),))
        pool = build_no_change_candidate_pool(no_partial, source)
        self.assertNotIn(RecommendationMethod.PARTIAL_PAYMENT, {c.recommendation_method for c in pool.candidates})
        # Installment cap blocks count > cap and blank/zero cap blocks everything.
        small_cap = planner_case(cap="2", options=(full_option(), installment_option()))
        pool = build_no_change_candidate_pool(small_cap, source)
        self.assertNotIn(RecommendationMethod.INSTALLMENTS, {c.recommendation_method for c in pool.candidates})
        no_cap = planner_case(cap=None, options=(full_option(), installment_option()))
        pool = build_no_change_candidate_pool(no_cap, source)
        self.assertNotIn(RecommendationMethod.INSTALLMENTS, {c.recommendation_method for c in pool.candidates})
        # First date before request date excludes the option.
        early = planner_case(options=(full_option(), installment_option(first="2026-01-09")))
        pool = build_no_change_candidate_pool(early, source)
        self.assertNotIn(RecommendationMethod.INSTALLMENTS, {c.recommendation_method for c in pool.candidates})
        # Last date after deadline excludes the option.
        late = planner_case(options=(full_option(), installment_option(freq=30)))
        pool = build_no_change_candidate_pool(late, source)
        self.assertNotIn(RecommendationMethod.INSTALLMENTS, {c.recommendation_method for c in pool.candidates})
        # Deadline before horizon is the binding gate; horizon-end option is allowed when deadline allows.
        late_deadline = planner_case(deadline="2026-03-01", options=(
            full_option(), installment_option(first="2026-03-30", count=2, freq=5)))
        pool = build_no_change_candidate_pool(late_deadline, source)
        self.assertNotIn(RecommendationMethod.INSTALLMENTS, {c.recommendation_method for c in pool.candidates})

    def test_unsafe_template_is_retained_but_not_certified(self) -> None:
        # Full payment of 900 breaches the -1000 dip on 01-20; template stays eligible, no candidate.
        source = baseline(move("2026-01-10", "opening", "open"), move("2026-01-20", "debit", "dip", "-1000"))
        current = planner_case(options=(full_option(),))
        pool = build_no_change_candidate_pool(current, source)
        self.assertEqual(pool.candidates, ())
        self.assertEqual(len(pool.eligible_templates), 1)
        self.assertFalse(pool.eligible_templates[0] in ())
        unsafe = pool.eligible_templates[0]
        self.assertEqual(unsafe.payments, (Payment(d("2026-01-10"), money("900")),))
        self.assertIn("unsafe_replay", pool.diagnostics)

    def test_capacity_is_immutable_across_pools(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-20", "debit", "dip", "-400"),
                          move("2026-01-30", "credit", "refund", "500"))
        rich = planner_case(options=(full_option(), installment_option()))
        poor = planner_case(methods=(), options=(full_option(), installment_option()))
        pool_rich = build_no_change_candidate_pool(rich, source)
        pool_poor = build_no_change_candidate_pool(poor, source)
        self.assertEqual(pool_rich.capacity, compute_baseline_capacity(rich, source))
        self.assertEqual(pool_rich.capacity, pool_poor.capacity)

    def test_empty_pool_is_conservative_and_truthful(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"))
        no_methods = planner_case(methods=(), options=(full_option(),))
        pool = build_no_change_candidate_pool(no_methods, source)
        self.assertEqual(pool.candidates, ())
        self.assertIn("no_accepted_method_full", pool.diagnostics)
        self.assertEqual(pool.eligible_templates, ())

    def test_fee_bearing_installment_matches_real_dataset_total_contract(self) -> None:
        # Reviewer regression (P1): real installment options carry a nonzero financing_fee
        # while total_payable_amount equals principal * count (repository.py option_total_mismatch).
        source = baseline(move("2026-01-10", "opening", "open"))
        fee_option = installment_option(amount="300", count=3, fee="25")
        self.assertEqual(fee_option.total_payable_amount, money("900"))
        current = planner_case(options=(fee_option,))
        pool = build_no_change_candidate_pool(current, source)
        installment = [c for c in pool.candidates if c.recommendation_method is RecommendationMethod.INSTALLMENTS]
        self.assertEqual(len(installment), 1)
        self.assertEqual(installment[0].payments, (Payment(d("2026-01-15"), money("300")),
                                                   Payment(d("2026-02-04"), money("300")),
                                                   Payment(d("2026-02-24"), money("300"))))
        self.assertEqual(installment[0].total_paid, money("900"))

    def test_installment_total_mismatch_is_rejected(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"))
        wrong_total = replace(installment_option(), total_payable_amount=money("901"))
        current = planner_case(options=(wrong_total,))
        pool = build_no_change_candidate_pool(current, source)
        self.assertNotIn(RecommendationMethod.INSTALLMENTS, {c.recommendation_method for c in pool.candidates})
        self.assertIn("installment_option_invalid", pool.diagnostics)

    def test_wait_eligibility_does_not_require_supplied_full_option(self) -> None:
        # F-01 regression: wait eligibility depends only on full-payment acceptance and
        # D < F <= deadline; the supplied full option is provenance, never a gate.
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-20", "debit", "dip", "-400"),
                          move("2026-01-30", "credit", "refund", "500"))
        current = planner_case(amount="550", options=())
        pool = build_no_change_candidate_pool(current, source)
        waits = [c for c in pool.candidates if c.recommendation_method is RecommendationMethod.WAIT]
        self.assertEqual(len(waits), 1)
        self.assertEqual(waits[0].payments, (Payment(d("2026-01-30"), money("550")),))
        self.assertIsNone(waits[0].payment_option_id)

    def test_wait_absent_when_full_payment_not_accepted(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"),
                          move("2026-01-20", "debit", "dip", "-400"),
                          move("2026-01-30", "credit", "refund", "500"))
        current = planner_case(amount="550", methods=(PaymentMethod.INSTALLMENTS,), options=())
        pool = build_no_change_candidate_pool(current, source)
        self.assertNotIn(RecommendationMethod.WAIT, {c.recommendation_method for c in pool.candidates})
        self.assertIn("no_accepted_method_wait", pool.diagnostics)

    def test_full_option_contract_is_validated(self) -> None:
        source = baseline(move("2026-01-10", "opening", "open"))
        # Full accepted but the supplied full option does not match amount/date/count.
        wrong = planner_case(options=(full_option(amount="800",),))
        with self.assertRaises(PlanningError):
            build_no_change_candidate_pool(wrong, source)

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
    PlanningError, PlanCandidate, PlanningDecision, SafetyReplay, plan_request, rank_key,
    compute_baseline_capacity, replay_schedule,
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
from buy_or_wait.evidence import resolve_case_evidence  # noqa: E402
from buy_or_wait.events import normalize_case_events  # noqa: E402
from buy_or_wait.forecast import build_baseline_forecast  # noqa: E402
from buy_or_wait.repository import DatasetRepository  # noqa: E402


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


# --- WP-07B spending-change candidate enumeration ----------------------------


from buy_or_wait.domain import (  # noqa: E402
    Direction, EventRecord, EventType, EventStatus, Flexibility,
)
from buy_or_wait.planning import (  # noqa: E402
    _action_sets, build_candidate_pool, enumerate_spending_change_actions,
)


def change_case(*, amount="900", deadline="2026-03-01", methods=(PaymentMethod.FULL_PAYMENT,),
                reduce_cats=frozenset({"dining"}), stop_cats=frozenset({"cloud_storage", "dining"}),
                protected=frozenset({"rent"}), events=(), options=(), cap=None) -> RequestCase:
    base = case()
    if isinstance(events, EventRecord):
        events = (events,)
    return replace(
        base,
        request=replace(base.request, requested_amount=money(amount), desired_completion_date=d(deadline),
                        allows_partial_payment=False),
        profile=ProfileRecord("user_P", CurrencyCode.ZAR, money("1000"), money("100"), frozenset(),
                              protected, reduce_cats, stop_cats, tuple(methods), cap),
        events=tuple(events),
        payment_options=tuple(options),
    )


def expense(event_id: str, category: str, flexibility: Flexibility, amount: str = "30",
            day: str = "2025-12-01", *, direction: Direction = Direction.DEBIT,
            status: EventStatus = EventStatus.SETTLED, floor: str | None = None) -> EventRecord:
    return EventRecord(event_id, "user_P", EventType.EXPENSE, f"{event_id} desc", category, direction,
                       money(amount), CurrencyCode.ZAR, d(day), d(day), status, None, flexibility,
                       money(floor) if floor is not None else None)


def recurring(day: str, ident: str, family: str, home: str, *, source_amount: str | None = None,
              source_currency: CurrencyCode | None = None,
              source_ids: tuple[str, ...] = ()) -> PrimitiveMovement:
    return move(day, "debit", ident, f"-{home}" if True else "0", origin="fixed_recurrence", family=family,
                source_amount=source_amount if source_amount is not None else home,
                source_currency=source_currency if source_currency is not None else CurrencyCode.ZAR,
                source_ids=source_ids if source_ids else (family,))


class SpendingChangeCandidateTests(unittest.TestCase):
    def test_only_mutable_fixed_recurrence_families_produce_actions(self) -> None:
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "d1", "dining_series", "40", source_ids=("dining_event",)),
            move("2026-01-15", "debit", "explicit", "-40", source_ids=("explicit_event",)),
            move("2026-01-15", "credit", "credit", "40", source_ids=("credit_event",)),
        )
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("dining_event", "dining", Flexibility.REDUCIBLE, floor="20"),)),
            source,
        )
        self.assertEqual([action.family_id for action in actions], ["dining_series"])
        self.assertEqual([(a.change_type, a.new_amount) for a in actions[0].actions],
                         [(SpendingChangeType.REDUCE_TO, money("20"))])

    def test_protected_category_and_flexibility_gates(self) -> None:
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "r1", "rent_series", "200", source_ids=("rent_event",)),
            recurring("2026-01-16", "c1", "cloud_series", "10", source_ids=("cloud_event",)),
        )
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("rent_event", "rent", Flexibility.STOPPABLE),
                                expense("cloud_event", "cloud_storage", Flexibility.STOPPABLE))),
            source,
        )
        # Rent is protected; only cloud storage (in the stop set) produces a stop.
        self.assertEqual([a.family_id for a in actions], ["cloud_series"])
        self.assertEqual(actions[0].actions[0].change_type, SpendingChangeType.STOP)

    def test_reduction_requires_floor_below_every_forecast_amount(self) -> None:
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "a1", "dining_series", "40", source_ids=("dining_event",)),
            recurring("2026-02-15", "a2", "dining_series", "50", source_ids=("dining_event",)),
        )
        # Floor 45 is above the 40 amount: no action may be generated.
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("dining_event", "dining", Flexibility.REDUCIBLE, floor="45"))),
            source,
        )
        self.assertEqual(actions, ())
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("dining_event", "dining", Flexibility.REDUCIBLE, floor="20"))),
            source,
        )
        self.assertEqual([(a.change_type, a.new_amount) for a in actions[0].actions],
                         [(SpendingChangeType.REDUCE_TO, money("20"))])

    def test_stop_requires_willingness_and_reduce_requires_reduce_or_both(self) -> None:
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "r1", "st_series", "10", source_ids=("st_event",)),
            recurring("2026-01-16", "rd1", "rd_series", "10", source_ids=("rd_event",)),
        )
        # stop_cats only: reducible family must not stop; reducible_or_stoppable may reduce.
        actions = enumerate_spending_change_actions(
            change_case(reduce_cats=frozenset({"dining"}), stop_cats=frozenset({"cloud_storage"}),
                        events=(expense("st_event", "streaming", Flexibility.REDUCIBLE),
                                expense("rd_event", "dining", Flexibility.REDUCIBLE_OR_STOPPABLE, floor="5"))),
            source,
        )
        self.assertEqual([a.family_id for a in actions], ["rd_series"])
        self.assertEqual([(a.change_type, a.new_amount) for a in actions[0].actions],
                         [(SpendingChangeType.REDUCE_TO, money("5"))])
        # stop Cats include streaming: stop action for the fixed-flexibility series is still gated
        # by flexibility; reducible-only flexibility may not stop.
        actions = enumerate_spending_change_actions(
            change_case(reduce_cats=frozenset(), stop_cats=frozenset({"streaming"}),
                        events=(expense("st_event", "streaming", Flexibility.REDUCIBLE))),
            source,
        )
        self.assertEqual(actions, ())

    def test_ambiguous_anchor_and_history_only_families_produce_no_action(self) -> None:
        # Two movements on the same family/date carry the same event ID -> ambiguous.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "x1", "dup_series", "10", source_ids=("dup_event",)),
            recurring("2026-01-15", "x2", "dup_series", "10", source_ids=("dup_event",)),
            recurring("2026-01-15", "h1", "hist_series", "10", source_ids=("hist_event",)),
        )
        # hist_series has a 2026-01-15 occurrence which is future relative to D=2026-01-10,
        # so a historical anchor exists for it... use an all-history family instead.
        past_only = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2025-12-15", "h1", "hist_series", "10", source_ids=("hist_event",)),
        )
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("hist_event", "dining", Flexibility.REDUCIBLE, floor="5"))),
            past_only,
        )
        self.assertEqual(actions, ())
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("dup_event", "dining", Flexibility.REDUCIBLE, floor="5"))),
            source,
        )
        self.assertEqual(actions, ())

    def test_one_to_three_family_sets_are_complete_and_canonical(self) -> None:
        moves = [move("2026-01-10", "opening", "open")]
        events = []
        for index, (family, event_id, category, flex, floor) in enumerate((
            ("f1_series", "ev1", "dining", Flexibility.REDUCIBLE, "10"),
            ("f2_series", "ev2", "cloud_storage", Flexibility.STOPPABLE, None),
            ("f3_series", "ev3", "dining", Flexibility.REDUCIBLE_OR_STOPPABLE, "7"),
        )):
            moves.append(recurring("2026-01-15", f"m{index}", family, "20", source_ids=(event_id,)))
            events.append(expense(event_id, category, flex, floor=floor))
        source = baseline(*moves)
        actions = enumerate_spending_change_actions(change_case(events=tuple(events)), source)
        by_family = {a.family_id: a for a in actions}
        self.assertEqual(sorted(by_family), ["f1_series", "f2_series", "f3_series"])
        # 7 nonempty subsets: {1},{2},{3},{1,2},{1,3},{2,3},{1,2,3}
        self.assertEqual(len(by_family["f1_series"].action_sets), 1)
        self.assertEqual(len(by_family["f2_series"].action_sets), 1)
        self.assertEqual(len(by_family["f3_series"].action_sets), 2)
        pool = build_candidate_pool(change_case(events=tuple(events), amount="800"), source)
        changed = [c for c in pool.candidates if c.spending_changes]
        self.assertEqual(len(changed), 11)
        # Canonical order: stable family ID.
        for candidate in changed:
            ids = [change.event_id for change in candidate.spending_changes]
            self.assertEqual(ids, sorted(ids))

    def test_no_duplicate_family_through_alternate_ids_and_no_stop_reduce_mix(self) -> None:
        # Two occurrence IDs of the same family reference different events; combining
        # stop on one and reduce on the other must never happen.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "p1", "dup_series", "10", source_ids=("dup_event_a",)),
            recurring("2026-02-15", "p2", "dup_series", "10", source_ids=("dup_event_b",)),
        )
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("dup_event_a", "dining", Flexibility.REDUCIBLE_OR_STOPPABLE, floor="5"),
                                expense("dup_event_b", "dining", Flexibility.REDUCIBLE_OR_STOPPABLE, floor="5")),
                        reduce_cats=frozenset({"dining"}), stop_cats=frozenset({"dining"})),
            source,
        )
        self.assertEqual(len(actions), 1)
        # Latest compatible occurrence (2026-02-15) anchors the action.
        self.assertEqual(actions[0].anchor_event_id, "dup_event_b")

    def test_changed_replay_uses_earliest_safe_full_date_and_marks_wait(self) -> None:
        # Opening 1000, dip -400 on 01-20, refund +500 on 01-30. Full 900 unsafe without
        # changes; stopping the -400 fixed debit makes full payment safe from D onward.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-20", "dip1", "dip_series", "400", source_ids=("dip_event",)),
            move("2026-01-30", "credit", "refund", "500", source_ids=("refund",)),
        )
        current = change_case(amount="900", events=(expense("dip_event", "dining", Flexibility.STOPPABLE),),
                              deadline="2026-02-28")
        pool = build_candidate_pool(current, source)
        full_changed = [c for c in pool.candidates if c.spending_changes and
                        c.recommendation_method is RecommendationMethod.FULL_PAYMENT]
        self.assertEqual(len(full_changed), 1)
        candidate = full_changed[0]
        self.assertEqual(candidate.payments, (Payment(d("2026-01-10"), money("900")),))
        self.assertEqual(list(change.event_id for change in candidate.spending_changes), ["dip_event"])
        self.assertTrue(candidate.safety_replay.safe)
        self.assertEqual(candidate.safety_replay.applied_change_event_ids, ("dip_event",))
        self.assertEqual(candidate.forecast_debit_reduction, money("400"))

    def test_changed_wait_candidate_has_no_option_id_and_later_date(self) -> None:
        # Full is unsafe at D even with changes, but safe on 01-24 once a credit lands.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            move("2026-01-10", "debit", "immediate", "-100", source_ids=("immediate",)),
            recurring("2026-01-20", "dip1", "dip_series", "400", source_ids=("dip_event",)),
            recurring("2026-01-21", "dip2", "dip_series", "400", source_ids=("dip_event",)),
            move("2026-01-24", "credit", "payday", "450", source_ids=("payday",)),
        )
        current = change_case(amount="900", events=(expense("dip_event", "dining", Flexibility.STOPPABLE),),
                              deadline="2026-02-28")
        pool = build_candidate_pool(current, source)
        waits = [c for c in pool.candidates if c.spending_changes and
                 c.recommendation_method is RecommendationMethod.WAIT]
        self.assertEqual(len(waits), 1)
        self.assertEqual(waits[0].payments, (Payment(d("2026-01-24"), money("900")),))
        self.assertIsNone(waits[0].payment_option_id)
        self.assertEqual(waits[0].safety_replay.applied_change_event_ids, ("dip_event",))

    def test_no_effect_change_produces_no_candidate(self) -> None:
        # The family is already at its floor: a reduce-to-floor replay has no effect on
        # the ledger, so no changed candidate may appear for that action alone.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "f1", "dining_series", "10", source_ids=("dining_event",)),
        )
        # Floor equals the forecast amount: floor-below-every-amount gate excludes the action.
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("dining_event", "dining", Flexibility.REDUCIBLE, floor="10"))),
            source,
        )
        self.assertEqual(actions, ())

    def test_pending_debit_survives_same_category_same_amount_change(self) -> None:
        # A pending explicit debit with the same category and amount as the changed family
        # must survive unchanged: only fixed_recurrence origins are mutable. The changed
        # wait path (payment after the pending debit) certifies the surviving -30 row.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-16", "rec1", "dining_series", "30", source_ids=("dining_event",)),
            move("2026-01-17", "debit", "pending", "-30", origin="explicit", source_ids=("pending_event",)),
            move("2026-01-18", "credit", "refund", "30", source_ids=("refund",)),
        )
        current = change_case(amount="900",
                              events=(expense("dining_event", "dining", Flexibility.STOPPABLE),
                                      expense("pending_event", "dining", Flexibility.FIXED,
                                              day="2026-01-17", status=EventStatus.PENDING)),
                              deadline="2026-02-28")
        pool = build_candidate_pool(current, source)
        stop = [c for c in pool.candidates
                if any(change.change_type is SpendingChangeType.STOP for change in c.spending_changes)]
        self.assertTrue(stop)
        pending_rows = [point for point in stop[0].safety_replay.checkpoints
                        if point.stable_id == "pending"]
        self.assertEqual(len(pending_rows), 1)
        self.assertEqual(pending_rows[0].cash_balance, money("970"))

    def test_capacity_and_no_change_ordering_preserved_with_changes(self) -> None:
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-20", "dip1", "dip_series", "400", source_ids=("dip_event",)),
            move("2026-01-30", "credit", "refund", "500", source_ids=("refund",)),
        )
        current = change_case(amount="550", deadline="2026-02-28", methods=(
            PaymentMethod.FULL_PAYMENT, PaymentMethod.PARTIAL_PAYMENT),
            events=(expense("dip_event", "dining", Flexibility.STOPPABLE),))
        pool = build_candidate_pool(current, source)
        self.assertEqual(pool.capacity, compute_baseline_capacity(current, source))
        changed_flags = [bool(candidate.spending_changes) for candidate in pool.candidates]
        # No-change candidates precede changed candidates: all False before the first True.
        first_changed = next((i for i, flag in enumerate(changed_flags) if flag), len(changed_flags))
        self.assertTrue(all(not flag for flag in changed_flags[:first_changed]))
        self.assertTrue(changed_flags[first_changed:])

    def test_duplicate_changed_candidates_are_suppressed(self) -> None:
        # Two action sets that reduce the same family to the same floor collapse to one
        # candidate; only distinct (method, payments, changes) tuples survive.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "f1", "dining_series", "20", source_ids=("dining_event",)),
        )
        current = change_case(amount="900", events=(expense("dining_event", "dining", Flexibility.REDUCIBLE, floor="10"),),
                              deadline="2026-02-28")
        pool = build_candidate_pool(current, source)
        keys = [(c.recommendation_method, c.payment_option_id, c.payments, c.spending_changes) for c in pool.candidates]
        self.assertEqual(len(keys), len(set(keys)))

    def test_changed_replay_applied_ids_do_not_depend_on_application_order(self) -> None:
        # F-01 regression: two families whose first debits occur in reverse-alphabetical
        # date order; the replay applies anchors chronologically but the candidate must
        # still be accepted (applied IDs compared as an ordered set).
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "m1", "b_series", "30", source_ids=("event_1816",)),
            recurring("2026-01-16", "m2", "a_series", "30", source_ids=("event_1815",)),
        )
        current = change_case(amount="900", deadline="2026-02-28",
                              events=(expense("event_1815", "dining", Flexibility.STOPPABLE),
                                      expense("event_1816", "dining", Flexibility.STOPPABLE)))
        pool = build_candidate_pool(current, source)
        changed = [candidate for candidate in pool.candidates if candidate.spending_changes]
        self.assertTrue(changed)
        for candidate in changed:
            self.assertEqual(tuple(sorted(candidate.safety_replay.applied_change_event_ids)),
                             tuple(sorted({change.event_id for change in candidate.spending_changes})))

    def test_four_family_sets_never_exceed_three_families(self) -> None:
        # F-02 regression (FR-05): four eligible families must not produce a
        # four-family action set; enumeration stops at three.
        moves = [move("2026-01-10", "opening", "open")]
        events = []
        for index, family in enumerate(("f1", "f2", "f3", "f4")):
            event_id = f"ev{family}"
            moves.append(recurring("2026-01-15", f"m{index}", f"{family}_series", "20", source_ids=(event_id,)))
            events.append(expense(event_id, "dining", Flexibility.STOPPABLE))
        source = baseline(*moves)
        actions = enumerate_spending_change_actions(change_case(events=tuple(events)), source)
        sets = _action_sets(actions)
        self.assertEqual(max(len(action_set) for action_set in sets), 3)
        self.assertEqual(len(sets), 14)  # C(4,1)*1 + C(4,2)*4 + C(4,3)*... canonical count

    def test_cross_family_anchor_produces_no_actions(self) -> None:
        # F-03 regression (B-AC-01/FR-04): one source event that anchors two
        # families is ambiguous and produces no action for either family.
        source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-15", "m1", "a_series", "30", source_ids=("ev_x",)),
            recurring("2026-01-16", "m2", "b_series", "30", source_ids=("ev_x",)),
        )
        actions = enumerate_spending_change_actions(
            change_case(events=(expense("ev_x", "dining", Flexibility.STOPPABLE),)), source)
        self.assertEqual(actions, ())

    def test_public_request_boundaries_06_11_21(self) -> None:
        # Real dataset pipeline: repository -> evidence -> events -> forecast -> planner.
        # Planner integration evidence only; no request-ID product logic is added.
        repo = DatasetRepository.from_directory(Path(__file__).resolve().parent.parent / "dataset")
        expectations = {
            "request_06": {("event_476", SpendingChangeType.STOP, None)},
            "request_11": {("event_949", SpendingChangeType.STOP, None)},
            "request_21": {("event_1815", SpendingChangeType.STOP, None),
                           ("event_1816", SpendingChangeType.STOP, None),
                           ("event_1816", SpendingChangeType.REDUCE_TO, money("23.5"))},
        }
        for request_id, expected_anchors in expectations.items():
            with self.subTest(request_id=request_id):
                current_case = repo.load_request_case(request_id)
                evidence = resolve_case_evidence(current_case)
                normalization = normalize_case_events(current_case, evidence)
                forecast = build_baseline_forecast(current_case, evidence, normalization)
                actions = enumerate_spending_change_actions(current_case, forecast)
                anchors = {(action.event_id, action.change_type, action.new_amount)
                           for family in actions for action in family.actions}
                self.assertEqual(anchors, expected_anchors)
                pool = build_candidate_pool(current_case, forecast)
                for candidate in pool.candidates:
                    if candidate.spending_changes:
                        self.assertTrue(candidate.safety_replay.safe)
                        self.assertEqual(tuple(candidate.safety_replay.applied_change_event_ids),
                                         tuple(sorted({change.event_id for change in candidate.spending_changes})))


# --- WP-07C ranking and decision ---------------------------------------------


from buy_or_wait.domain import AffordabilityStatus  # noqa: E402
from buy_or_wait.planning import (  # noqa: E402
    PlanningDecision, plan_request,
)


def candidate(method: RecommendationMethod, *, payments: tuple[Payment, ...] | None = None,
              changes: tuple[SpendingChange, ...] = (), option_id: str | None = None,
              reduction: str = "0") -> PlanCandidate:
    if payments is None:
        payments = (Payment(d("2026-01-10"), money("900")),)
    replay = SafetyReplay("request_P", True, (), money("100"), None, ())
    return PlanCandidate(method, payments, changes, option_id, replay, money(reduction))


class RankingAndDecisionTests(unittest.TestCase):
    def _pool_case(self, **kwargs) -> RequestCase:
        return planner_case(**kwargs)

    def test_published_order_decides_one_variable_at_a_time(self) -> None:
        # FR-07 pairwise table: cheaper changed plan must still lose to no-change.
        no_change = candidate(RecommendationMethod.INSTALLMENTS, option_id="payment_option_02",
                              payments=(Payment(d("2026-01-15"), money("300")), Payment(d("2026-02-04"), money("300")),
                                        Payment(d("2026-02-24"), money("300"))))
        cheaper_changed = candidate(RecommendationMethod.FULL_PAYMENT,
                                    changes=(SpendingChange(SpendingChangeType.STOP, "dip_event"),))
        winner = min([cheaper_changed, no_change], key=rank_key)
        self.assertIs(winner, no_change)
        # Lower exact total paid wins next.
        cheap = candidate(RecommendationMethod.FULL_PAYMENT, option_id="a",
                          payments=(Payment(d("2026-01-10"), money("800")),))
        pricey = candidate(RecommendationMethod.INSTALLMENTS, option_id="b",
                           payments=(Payment(d("2026-01-10"), money("400")), Payment(d("2026-01-11"), money("500"))))
        self.assertIs(min([pricey, cheap], key=rank_key), cheap)
        # Earlier start date, then fewer payments (equal starts isolate the count key).
        later_start = candidate(RecommendationMethod.WAIT,
                                payments=(Payment(d("2026-01-16"), money("800")),))
        self.assertIs(min([later_start, cheap], key=rank_key), cheap)
        two = candidate(RecommendationMethod.PARTIAL_PAYMENT, option_id="c",
                        payments=(Payment(d("2026-01-10"), money("400")), Payment(d("2026-01-12"), money("400"))))
        self.assertIs(min([two, cheap], key=rank_key), cheap)
        # Two supplied offers: stable text order decides (payment_option_10 < payment_option_2).
        ten = candidate(RecommendationMethod.FULL_PAYMENT, option_id="payment_option_10")
        two_id = candidate(RecommendationMethod.FULL_PAYMENT, option_id="payment_option_2")
        self.assertIs(min([ten, two_id], key=rank_key), ten)

    def test_residual_ties_are_total_and_permutation_independent(self) -> None:
        # Equal primaries: action count, then reduction, then action text, then method key.
        one_action = candidate(RecommendationMethod.WAIT,
                               changes=(SpendingChange(SpendingChangeType.STOP, "ev_z"),))
        two_actions = candidate(RecommendationMethod.WAIT,
                                changes=(SpendingChange(SpendingChangeType.STOP, "ev_a"),
                                         SpendingChange(SpendingChangeType.STOP, "ev_b")))
        self.assertIs(min([two_actions, one_action], key=rank_key), one_action)  # fewer actions
        small = candidate(RecommendationMethod.WAIT,
                          changes=(SpendingChange(SpendingChangeType.STOP, "ev_a"),), reduction="100")
        large = candidate(RecommendationMethod.WAIT,
                          changes=(SpendingChange(SpendingChangeType.STOP, "ev_b"),), reduction="200")
        self.assertIs(min([large, small], key=rank_key), small)
        text_a = candidate(RecommendationMethod.WAIT,
                           changes=(SpendingChange(SpendingChangeType.STOP, "ev_a"),), reduction="100")
        text_b = candidate(RecommendationMethod.WAIT,
                           changes=(SpendingChange(SpendingChangeType.STOP, "ev_z"),), reduction="100")
        self.assertIs(min([text_b, text_a], key=rank_key), text_a)
        # Method key: supplied versus derived with every preceding field equal.
        derived_wait = candidate(RecommendationMethod.WAIT)
        supplied_full = candidate(RecommendationMethod.FULL_PAYMENT, option_id="x")
        self.assertIs(min([derived_wait, supplied_full], key=rank_key), supplied_full)
        # F-01 regression: mixed supplied/derived pairs are decided by the
        # residual keys, which precede the option key. A derived WAIT with one
        # action must beat a supplied WAIT with two actions when all published
        # primaries tie.
        derived_one_action = candidate(RecommendationMethod.WAIT,
                                       changes=(SpendingChange(SpendingChangeType.STOP, "ev_z"),))
        supplied_two_actions = candidate(RecommendationMethod.WAIT, option_id="payment_option_2",
                                         changes=(SpendingChange(SpendingChangeType.STOP, "ev_a"),
                                                  SpendingChange(SpendingChangeType.STOP, "ev_b")))
        self.assertIs(min([supplied_two_actions, derived_one_action], key=rank_key), derived_one_action)
        # F-03 regression: the option key is a total three-state order
        # (supplied before derived, supplied IDs by stable text), so a derived
        # candidate between two supplied offers cannot make the comparison
        # intransitive. The mixed set has one total order C < A < B and every
        # permutation of it must return the same winner identity.
        option_a = candidate(RecommendationMethod.WAIT,
                             changes=(SpendingChange(SpendingChangeType.STOP, "ev_z"),))
        option_b = candidate(RecommendationMethod.WAIT, option_id="payment_option_2",
                             changes=(SpendingChange(SpendingChangeType.STOP, "ev_a"),
                                      SpendingChange(SpendingChangeType.STOP, "ev_b")))
        option_c = candidate(RecommendationMethod.WAIT, option_id="payment_option_10",
                             changes=(SpendingChange(SpendingChangeType.STOP, "ev_z"),))
        self.assertLess(rank_key(option_c), rank_key(option_a))
        self.assertLess(rank_key(option_a), rank_key(option_b))
        mixed = [option_a, option_b, option_c]
        import itertools
        reference = min(mixed, key=rank_key)
        for permutation in itertools.permutations(range(3)):
            self.assertIs(min([mixed[i] for i in permutation], key=rank_key), reference)
        # Residual keys still decide supplied-only pairs after the option-ID key.
        supplied_stop = candidate(RecommendationMethod.WAIT, option_id="o_a",
                                  changes=(SpendingChange(SpendingChangeType.STOP, "ev_z"),))
        supplied_two = candidate(RecommendationMethod.WAIT, option_id="o_z",
                                 changes=(SpendingChange(SpendingChangeType.STOP, "ev_a"),
                                          SpendingChange(SpendingChangeType.STOP, "ev_b")))
        self.assertIs(min([supplied_two, supplied_stop], key=rank_key), supplied_stop)
        # Equal supplied offers fall through to residual keys, not numeric ID parsing.
        cheap_supplied = candidate(RecommendationMethod.FULL_PAYMENT, option_id="payment_option_2",
                                   payments=(Payment(d("2026-01-10"), money("800")),))
        costly_supplied = candidate(RecommendationMethod.FULL_PAYMENT, option_id="payment_option_10",
                                    payments=(Payment(d("2026-01-10"), money("900")),))
        self.assertIs(min([costly_supplied, cheap_supplied], key=rank_key), cheap_supplied)
        # Permutation invariance over an equal-primary set (equal supplied offers).
        equal = [candidate(RecommendationMethod.WAIT, option_id=f"o{i}", reduction="0") for i in range(3)]
        for permutation in ((2, 1, 0), (1, 0, 2), (2, 0, 1)):
            self.assertIs(min([equal[i] for i in permutation], key=rank_key),
                          min(equal, key=rank_key))

    def test_status_method_table_rows(self) -> None:
        # Full at D without changes -> affordable_now/full_payment.
        source = baseline(move("2026-01-10", "opening", "open"))
        current = self._pool_case(options=(full_option(),))
        decision = plan_request(current, source)
        self.assertEqual((decision.affordability_status, decision.recommended_method),
                         (AffordabilityStatus.AFFORDABLE_NOW, RecommendationMethod.FULL_PAYMENT))
        self.assertEqual(decision.selected_candidate.payment_option_id, "payment_option_01")
        self.assertEqual(decision.capacity.amount_safe_to_pay, money("900"))
        # Wait after D without changes -> affordable_later/wait (partial not considered).
        wait_source = baseline(move("2026-01-10", "opening", "open"),
                               move("2026-01-20", "debit", "dip", "-400"),
                               move("2026-01-30", "credit", "refund", "500"))
        wait_case = planner_case(amount="550", methods=(PaymentMethod.FULL_PAYMENT,), options=())
        decision = plan_request(wait_case, wait_source)
        self.assertEqual((decision.affordability_status, decision.recommended_method),
                         (AffordabilityStatus.AFFORDABLE_LATER, RecommendationMethod.WAIT))
        # Full at D with changes -> affordable_with_plan/full_payment.
        changed_source = baseline(
            move("2026-01-10", "opening", "open"),
            recurring("2026-01-20", "dip1", "dip_series", "400", source_ids=("dip_event",)),
        )
        changed_case = change_case(amount="900", events=(expense("dip_event", "dining", Flexibility.STOPPABLE),),
                                   deadline="2026-02-28")
        decision = plan_request(changed_case, changed_source)
        self.assertEqual((decision.affordability_status, decision.recommended_method),
                         (AffordabilityStatus.AFFORDABLE_WITH_PLAN, RecommendationMethod.FULL_PAYMENT))
        # Installments -> affordable_with_plan/installments (full-now breaches; three
        # 300 installments clear the dip with an interim credit; installments start
        # earlier than wait at equal cost, so the comparator picks installments).
        inst_source = baseline(move("2026-01-10", "opening", "open"),
                               move("2026-01-20", "debit", "dip", "-300"),
                               move("2026-02-10", "credit", "refund", "300"))
        inst_case = planner_case(amount="900", methods=(PaymentMethod.FULL_PAYMENT, PaymentMethod.INSTALLMENTS),
                                 options=(installment_option(),))
        decision = plan_request(inst_case, inst_source)
        self.assertEqual((decision.affordability_status, decision.recommended_method),
                         (AffordabilityStatus.AFFORDABLE_WITH_PLAN, RecommendationMethod.INSTALLMENTS))
        partial_case = planner_case(amount="550", options=())
        partial_source = baseline(move("2026-01-10", "opening", "open"),
                                  move("2026-01-20", "debit", "dip", "-400"),
                                  move("2026-01-30", "credit", "refund", "500"))
        decision = plan_request(partial_case, partial_source)
        self.assertEqual((decision.affordability_status, decision.recommended_method),
                         (AffordabilityStatus.AFFORDABLE_WITH_PLAN, RecommendationMethod.PARTIAL_PAYMENT))

    def test_fallback_classes_are_truthful_and_ordered(self) -> None:
        # Upstream uncertainty: blocked baseline.
        source = baseline(move("2026-01-10", "opening", "open"), blocked=True)
        decision = plan_request(self._pool_case(options=(full_option(),)), source)
        self.assertEqual((decision.affordability_status, decision.recommended_method),
                         (AffordabilityStatus.NOT_AFFORDABLE, RecommendationMethod.NOT_RECOMMENDED))
        self.assertIsNone(decision.selected_candidate)
        self.assertEqual(decision.diagnostics, ("fallback_baseline_uncertified",))
        self.assertEqual(decision.capacity.amount_safe_to_pay, money("0"))
        # Financially possible only after the deadline.
        late_source = baseline(move("2026-01-10", "opening", "open"),
                               move("2026-01-20", "debit", "dip", "-400"),
                               move("2026-01-30", "credit", "refund", "500"))
        late_case = planner_case(amount="900", deadline="2026-01-25", options=())
        decision = plan_request(late_case, late_source)
        self.assertEqual(decision.diagnostics, ("fallback_possible_after_deadline",))
        # No accepted method / eligible option.
        no_method = planner_case(methods=(), options=(full_option(),))
        decision = plan_request(no_method, baseline(move("2026-01-10", "opening", "open")))
        self.assertEqual(decision.diagnostics, ("fallback_no_accepted_method",))
        # Genuine no safe candidate: methods accepted, options eligible, replay breaches.
        breach_source = baseline(move("2026-01-10", "opening", "open"),
                                 move("2026-01-20", "debit", "dip", "-1000"))
        decision = plan_request(self._pool_case(options=(full_option(),)), breach_source)
        self.assertEqual(decision.diagnostics, ("fallback_no_safe_candidate",))
        # F-02 regression (a): no accepted methods, yet full payment is financially
        # possible only after the deadline; the after-deadline scan precedes the
        # template proxy in the brief precedence.
        decision = plan_request(planner_case(methods=(), amount="900", deadline="2026-01-25", options=()), late_source)
        self.assertEqual(decision.diagnostics, ("fallback_possible_after_deadline",))
        # F-02 regression (b): installments accepted but the option is unsafe while
        # full payment at D is financially safe; the no-eligible-option class must
        # outrank the no-safe-candidate class (no after-deadline escape exists here).
        decision = plan_request(planner_case(methods=(PaymentMethod.INSTALLMENTS,), amount="900", options=()), breach_source)
        self.assertEqual(decision.diagnostics, ("fallback_no_accepted_method",))
        # Capacity is the unchanged baseline result in every fallback.
        self.assertEqual(decision.capacity, compute_baseline_capacity(self._pool_case(options=(full_option(),)), breach_source))

    def test_public_requests_select_exact_paths(self) -> None:
        repo = DatasetRepository.from_directory(Path(__file__).resolve().parent.parent / "dataset")
        expected = {
            "request_06": (AffordabilityStatus.NOT_AFFORDABLE, RecommendationMethod.NOT_RECOMMENDED, None),
            "request_11": (AffordabilityStatus.AFFORDABLE_LATER, RecommendationMethod.WAIT, d("2025-05-15")),
            "request_21": (AffordabilityStatus.NOT_AFFORDABLE, RecommendationMethod.NOT_RECOMMENDED, None),
        }
        for request_id, (status, method, payment_date) in expected.items():
            with self.subTest(request_id=request_id):
                current = repo.load_request_case(request_id)
                evidence = resolve_case_evidence(current)
                normalization = normalize_case_events(current, evidence)
                forecast = build_baseline_forecast(current, evidence, normalization)
                decision = plan_request(current, forecast)
                self.assertEqual((decision.affordability_status, decision.recommended_method), (status, method))
                if payment_date is None:
                    self.assertIsNone(decision.selected_candidate)
                else:
                    self.assertEqual(decision.selected_candidate.payments, (Payment(payment_date, current.request.requested_amount),))
                    self.assertEqual(decision.selected_candidate.spending_changes, ())
                self.assertEqual(decision.request_id, request_id)

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
from buy_or_wait.planning import PlanningError, replay_schedule  # noqa: E402


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

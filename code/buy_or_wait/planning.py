"""WP-06A pure independent schedule safety replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal

from buy_or_wait.domain import Payment, RequestCase, SpendingChange, SpendingChangeType
from buy_or_wait.events import EventNormalizationError, convert_exact
from buy_or_wait.forecast import BaselineForecast, PrimitiveMovement


@dataclass(frozen=True)
class ReplayCheckpoint:
    checkpoint_index: int
    date: date
    phase: str
    stable_id: str
    cash_balance: Decimal
    reserved_balance: Decimal
    spendable_balance: Decimal
    minimum_balance: Decimal
    headroom: Decimal
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class ReplayFailure:
    reason_code: str
    date: date | None
    checkpoint_index: int | None
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class SafetyReplay:
    request_id: str
    safe: bool
    checkpoints: tuple[ReplayCheckpoint, ...]
    minimum_headroom: Decimal | None
    first_failure: ReplayFailure | None
    applied_change_event_ids: tuple[str, ...]


class PlanningError(ValueError):
    """Trusted forecast contract error, with only source-safe diagnostics."""

    def __init__(self, reason_code: str, source_ids: tuple[str, ...] = ()) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.source_ids = source_ids


def _is_money(value: object, *, positive: bool = False) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and (value > 0 if positive else True)


def _validate_baseline(case: RequestCase, baseline: BaselineForecast) -> tuple[ReplayCheckpoint, ...]:
    if not isinstance(baseline, BaselineForecast) or baseline.request_id != case.request.request_id or baseline.request_date != case.request.request_date:
        raise PlanningError("baseline_case_mismatch", ())
    if baseline.horizon_end < baseline.request_date or not _is_money(baseline.opening_cash) or not _is_money(baseline.minimum_balance):
        raise PlanningError("baseline_invalid", ())
    cash, reserve = baseline.opening_cash, Decimal("0")
    replayed: list[ReplayCheckpoint] = []
    ids: set[str] = set()
    if len(baseline.primitive_movements) != len(baseline.checkpoints):
        raise PlanningError("baseline_replay_mismatch", ())
    for index, (movement, published) in enumerate(zip(baseline.primitive_movements, baseline.checkpoints)):
        if (not isinstance(movement, PrimitiveMovement) or movement.movement_id in ids or
                not _is_money(movement.cash_delta) or not _is_money(movement.reserve_delta) or
                movement.date < baseline.request_date or movement.date > baseline.horizon_end):
            raise PlanningError("baseline_primitive_invalid", getattr(movement, "source_event_ids", ()))
        ids.add(movement.movement_id)
        cash += movement.cash_delta
        reserve += movement.reserve_delta
        checkpoint = ReplayCheckpoint(index, movement.date, movement.phase, movement.movement_id, cash, reserve,
                                      cash - reserve, baseline.minimum_balance, cash - reserve - baseline.minimum_balance,
                                      movement.source_event_ids + movement.source_fact_ids)
        if (published.movement_id != movement.movement_id or published.date != checkpoint.date or
                (published.cash_balance, published.reserved_balance, published.spendable_balance, published.headroom) !=
                (checkpoint.cash_balance, checkpoint.reserved_balance, checkpoint.spendable_balance, checkpoint.headroom)):
            raise PlanningError("baseline_replay_mismatch", checkpoint.source_ids)
        replayed.append(checkpoint)
    minimum = min((point.headroom for point in replayed), default=None)
    if baseline.blocks_downstream:
        if baseline.minimum_headroom is not None:
            raise PlanningError("baseline_replay_mismatch", ())
    elif baseline.minimum_headroom != minimum:
        raise PlanningError("baseline_replay_mismatch", ())
    return tuple(replayed)


def _validate_payments(case: RequestCase, baseline: BaselineForecast, payments: tuple[Payment, ...]) -> ReplayFailure | None:
    previous: date | None = None
    for index, payment in enumerate(payments):
        if not isinstance(payment, Payment) or not isinstance(payment.payment_date, date):
            return ReplayFailure("payment_invalid", None, index, ())
        if previous is not None and payment.payment_date < previous:
            return ReplayFailure("payment_out_of_order", payment.payment_date, index, ())
        if payment.payment_date < case.request.request_date or payment.payment_date > baseline.horizon_end:
            return ReplayFailure("payment_out_of_horizon", payment.payment_date, index, ())
        if not _is_money(payment.amount, positive=True):
            return ReplayFailure("payment_amount_invalid", payment.payment_date, index, ())
        previous = payment.payment_date
    return None


def _changes(case: RequestCase, baseline: BaselineForecast, changes: tuple[SpendingChange, ...]) -> tuple[dict[str, SpendingChange], ReplayFailure | None]:
    if len(changes) > 3:
        return {}, ReplayFailure("too_many_spending_changes", None, None, ())
    anchors: dict[str, set[str]] = {}
    eligible: dict[str, list[PrimitiveMovement]] = {}
    for movement in baseline.primitive_movements:
        if movement.phase == "debit" and movement.origin == "fixed_recurrence" and movement.family_id and movement.occurrence_date and movement.source_amount is not None and movement.source_currency and movement.home_currency:
            for event_id in movement.source_event_ids:
                anchors.setdefault(event_id, set()).add(movement.family_id)
                eligible.setdefault(movement.family_id, []).append(movement)
    chosen: dict[str, SpendingChange] = {}
    for index, change in enumerate(changes):
        if not isinstance(change, SpendingChange) or not isinstance(change.event_id, str):
            return {}, ReplayFailure("change_invalid", None, index, ())
        families = anchors.get(change.event_id)
        if not families:
            return {}, ReplayFailure("change_target_unknown", None, index, (change.event_id,))
        if len(families) != 1:
            return {}, ReplayFailure("change_target_ambiguous", None, index, (change.event_id,))
        family = next(iter(families))
        if family in chosen:
            return {}, ReplayFailure("change_family_duplicate", None, index, (change.event_id,))
        if change.change_type is SpendingChangeType.STOP:
            pass
        elif change.change_type is SpendingChangeType.REDUCE_TO:
            if not _is_money(change.new_amount) or change.new_amount < 0:
                return {}, ReplayFailure("change_amount_invalid", None, index, (change.event_id,))
            if any(change.new_amount >= movement.source_amount for movement in eligible[family]):
                return {}, ReplayFailure("change_amount_not_reducing", None, index, (change.event_id,))
        else:
            return {}, ReplayFailure("change_type_invalid", None, index, (change.event_id,))
        if not eligible[family]:
            return {}, ReplayFailure("change_has_no_effect", None, index, (change.event_id,))
        chosen[family] = change
    return chosen, None


@dataclass(frozen=True)
class CapacityResult:
    request_id: str
    amount_safe_to_pay: Decimal
    earliest_date_for_full_payment: date | None
    diagnostics: tuple[str, ...]


def compute_baseline_capacity(case: RequestCase, baseline: BaselineForecast) -> CapacityResult:
    """Return safe-today amount and first safe standalone full-payment date."""
    replayed = replay_schedule(case, baseline)
    if not replayed.safe or replayed.minimum_headroom is None:
        diagnostic = baseline.diagnostics[0] if baseline.diagnostics else None
        if replayed.minimum_headroom is not None and replayed.first_failure is not None:
            reason: str = replayed.first_failure.reason_code
        else:
            reason = diagnostic.reason_code if diagnostic else "baseline_uncertified"
        return CapacityResult(case.request.request_id, Decimal("0"), None, (reason,))
    headroom = replayed.minimum_headroom
    safe = min(max(headroom, Decimal("0")), case.request.requested_amount).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    if safe != 0 and safe.is_zero():
        safe = Decimal("0")
    if safe > 0:
        confirmation = replay_schedule(case, baseline, (Payment(case.request.request_date, safe),))
        if not confirmation.safe:
            raise PlanningError("capacity_replay_mismatch", ())
    earliest: date | None = None
    day = case.request.request_date
    while day <= baseline.horizon_end:
        attempt = replay_schedule(case, baseline, (Payment(day, case.request.requested_amount),))
        if attempt.safe:
            earliest = day
            break
        day += timedelta(days=1)
    return CapacityResult(case.request.request_id, safe, earliest, ())


def replay_schedule(case: RequestCase, baseline: BaselineForecast, payments: tuple[Payment, ...] = (),
                    spending_changes: tuple[SpendingChange, ...] = ()) -> SafetyReplay:
    """Replay every accepted movement and proposed transformation through horizon."""
    baseline_checkpoints = _validate_baseline(case, baseline)
    payment_failure = _validate_payments(case, baseline, payments)
    if payment_failure:
        return SafetyReplay(case.request.request_id, False, (), None, payment_failure, ())
    change_by_family, change_failure = _changes(case, baseline, spending_changes)
    if change_failure:
        return SafetyReplay(case.request.request_id, False, (), None, change_failure, ())
    if baseline.blocks_downstream or baseline.minimum_headroom is None:
        diagnostic = baseline.diagnostics[0] if baseline.diagnostics else None
        return SafetyReplay(case.request.request_id, False, (), None,
                            ReplayFailure("baseline_uncertified", None, None, diagnostic.source_ids if diagnostic else ()), ())

    cash, reserve, trace, first = baseline.opening_cash, Decimal("0"), [], None
    payments_by_date: dict[date, list[tuple[int, Payment]]] = {}
    for index, payment in enumerate(payments):
        payments_by_date.setdefault(payment.payment_date, []).append((index, payment))
    applied: list[str] = []
    movements_by_date: dict[date, list[PrimitiveMovement]] = {}
    for movement in baseline.primitive_movements:
        movements_by_date.setdefault(movement.date, []).append(movement)
    index = 0
    for day in sorted(set(movements_by_date) | set(payments_by_date)):
        for movement in movements_by_date.get(day, []):
            cash_delta = movement.cash_delta
            change = change_by_family.get(movement.family_id or "")
            if change and movement.phase == "debit" and movement.origin == "fixed_recurrence":
                if change.change_type is SpendingChangeType.STOP:
                    cash_delta = Decimal("0")
                else:
                    try:
                        changed_home = convert_exact(case.relevant_rates, change.new_amount, movement.occurrence_date,
                                                     movement.source_currency, movement.home_currency, movement.source_event_ids)
                    except EventNormalizationError as error:
                        if error.reason_code == "fx_rate_missing":
                            return SafetyReplay(case.request.request_id, False, tuple(trace), None,
                                                ReplayFailure("change_fx_rate_missing", day, index, error.source_ids), tuple(applied))
                        raise PlanningError(error.reason_code, error.source_ids) from error
                    cash_delta = -changed_home
                if change.event_id not in applied:
                    applied.append(change.event_id)
            cash += cash_delta
            reserve += movement.reserve_delta
            point = ReplayCheckpoint(index, day, movement.phase, movement.movement_id, cash, reserve, cash - reserve,
                                     baseline.minimum_balance, cash - reserve - baseline.minimum_balance,
                                     movement.source_event_ids + movement.source_fact_ids)
            trace.append(point)
            if first is None and point.headroom < 0:
                first = ReplayFailure("minimum_balance_breach", day, index, point.source_ids)
            index += 1
        for payment_index, payment in payments_by_date.get(day, []):
            cash -= payment.amount
            point = ReplayCheckpoint(index, day, "payment", f"payment:{payment_index}", cash, reserve, cash - reserve,
                                     baseline.minimum_balance, cash - reserve - baseline.minimum_balance, ())
            trace.append(point)
            if first is None and point.headroom < 0:
                first = ReplayFailure("minimum_balance_breach", day, index, ())
            index += 1
    return SafetyReplay(case.request.request_id, first is None, tuple(trace), min(point.headroom for point in trace), first, tuple(applied))

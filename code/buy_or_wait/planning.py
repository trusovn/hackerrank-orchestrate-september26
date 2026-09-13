"""WP-06A pure independent schedule safety replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from enum import Enum

from buy_or_wait.domain import (
    AffordabilityStatus, Flexibility, Payment, PaymentMethod, PaymentOptionRecord, RequestCase, SpendingChange,
    SpendingChangeType,
)
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


# --- WP-07A no-change candidate enumeration ---------------------------------


class RecommendationMethod(Enum):
    FULL_PAYMENT = "full_payment"
    PARTIAL_PAYMENT = "partial_payment"
    INSTALLMENTS = "installments"
    WAIT = "wait"
    NOT_RECOMMENDED = "not_recommended"


@dataclass(frozen=True)
class PaymentTemplate:
    recommendation_method: RecommendationMethod
    payments: tuple[Payment, ...]
    payment_option_id: str | None


@dataclass(frozen=True)
class PlanCandidate:
    recommendation_method: RecommendationMethod
    payments: tuple[Payment, ...]
    spending_changes: tuple[SpendingChange, ...]
    payment_option_id: str | None
    safety_replay: SafetyReplay
    forecast_debit_reduction: Decimal

    @property
    def total_paid(self) -> Decimal:
        return sum((payment.amount for payment in self.payments), Decimal("0"))

    @property
    def start(self) -> date:
        return self.payments[0].payment_date

    @property
    def completion(self) -> date:
        return self.payments[-1].payment_date

    @property
    def payment_count(self) -> int:
        return len(self.payments)


@dataclass(frozen=True)
class CandidatePool:
    request_id: str
    capacity: CapacityResult
    eligible_templates: tuple[PaymentTemplate, ...]
    candidates: tuple[PlanCandidate, ...]
    diagnostics: tuple[str, ...]


def _validate_full_option(case: RequestCase, options: tuple[PaymentOptionRecord, ...]) -> str | None:
    full = [option for option in options if option.payment_method is PaymentMethod.FULL_PAYMENT]
    if not full:
        return None
    if len(full) != 1:
        raise PlanningError("full_option_ambiguous", (option.payment_option_id for option in full))
    option = full[0]
    request = case.request
    if (option.request_id != request.request_id or option.payment_amount != request.requested_amount or
            option.number_of_payments != 1 or option.first_payment_date != request.request_date or
            option.total_payable_amount != request.requested_amount):
        raise PlanningError("full_option_mismatch", (option.payment_option_id,))
    return option.payment_option_id


def _chronological_complete(payments: tuple[Payment, ...], case: RequestCase, baseline: BaselineForecast) -> bool:
    previous: date | None = None
    for payment in payments:
        if previous is not None and payment.payment_date < previous:
            return False
        previous = payment.payment_date
    if not payments or payments[0].payment_date < case.request.request_date:
        return False
    return payments[-1].payment_date <= case.request.desired_completion_date and payments[-1].payment_date <= baseline.horizon_end


def _expected_installment_payments(option: PaymentOptionRecord) -> tuple[Payment, ...]:
    if option.payment_frequency_days is None or option.payment_frequency_days <= 0:
        raise PlanningError("installment_option_invalid", (option.payment_option_id,))
    payments = []
    day = option.first_payment_date
    for _ in range(option.number_of_payments):
        payments.append(Payment(day, option.payment_amount))
        day += timedelta(days=option.payment_frequency_days)
    # The accepted repository contract (repository.py option_total_mismatch) defines
    # total_payable_amount as payment_amount * number_of_payments; financing_fee is a
    # separate disclosure and never an additive component of the total.
    expected_total = option.payment_amount * option.number_of_payments
    if expected_total != option.total_payable_amount or option.financing_fee < 0:
        raise PlanningError("installment_option_invalid", (option.payment_option_id,))
    return tuple(payments)


def _installment_template(case: RequestCase, baseline: BaselineForecast,
                          option: PaymentOptionRecord) -> PaymentTemplate | str:
    request = case.request
    if option.request_id != request.request_id or option.payment_method is not PaymentMethod.INSTALLMENTS:
        return "installment_option_invalid"
    cap = case.profile.max_installment_months
    if option.number_of_payments <= 0 or option.payment_amount <= 0:
        return "installment_option_invalid"
    if cap is None or cap <= 0 or option.number_of_payments > cap:
        return "installment_cap_exceeded"
    if option.first_payment_date < request.request_date:
        return "installment_first_date_early"
    if option.payment_frequency_days is None or option.payment_frequency_days <= 0:
        return "installment_option_invalid"
    try:
        payments = _expected_installment_payments(option)
    except PlanningError:
        return "installment_option_invalid"
    if payments[-1].payment_date > request.desired_completion_date:
        return "installment_after_deadline"
    if payments[-1].payment_date > baseline.horizon_end:
        return "installment_after_horizon"
    return PaymentTemplate(RecommendationMethod.INSTALLMENTS, payments, option.payment_option_id)


def _no_change_templates(case: RequestCase, baseline: BaselineForecast, capacity: CapacityResult,
                         full_option_id: str | None) -> tuple[list[PaymentTemplate], list[str]]:
    request, profile = case.request, case.profile
    accepted = set(profile.payment_methods_user_will_consider)
    templates: list[PaymentTemplate] = []
    diagnostics: list[str] = []
    amount = request.requested_amount

    if RecommendationMethod.FULL_PAYMENT.value in {method.value for method in accepted}:
        templates.append(PaymentTemplate(RecommendationMethod.FULL_PAYMENT,
                                         (Payment(request.request_date, amount),), full_option_id))
    else:
        diagnostics.append("no_accepted_method_full")

    capacity_safe = capacity.amount_safe_to_pay
    partial_eligible = (RecommendationMethod.PARTIAL_PAYMENT.value in {method.value for method in accepted} and
                        request.allows_partial_payment and 0 < capacity_safe < amount)
    if partial_eligible:
        earliest = capacity.earliest_date_for_full_payment
        if earliest is not None and earliest <= request.desired_completion_date:
            templates.append(PaymentTemplate(
                RecommendationMethod.PARTIAL_PAYMENT,
                (Payment(request.request_date, capacity_safe), Payment(earliest, amount - capacity_safe)),
                None))
        else:
            diagnostics.append("partial_no_earliest")
    else:
        diagnostics.append("partial_not_eligible")

    if RecommendationMethod.INSTALLMENTS.value in {method.value for method in accepted}:
        installment_options = [option for option in case.payment_options
                               if option.payment_method is PaymentMethod.INSTALLMENTS]
        if not installment_options:
            diagnostics.append("no_installment_option")
        for option in installment_options:
            verdict = _installment_template(case, baseline, option)
            if isinstance(verdict, PaymentTemplate):
                templates.append(verdict)
            else:
                diagnostics.append(verdict)
    else:
        diagnostics.append("no_accepted_method_installments")

    # Wait eligibility depends only on full-payment acceptance and D < F <= deadline;
    # the supplied full option is provenance, never a gate (derived wait uses no option ID).
    if RecommendationMethod.FULL_PAYMENT.value in {method.value for method in accepted}:
        earliest = capacity.earliest_date_for_full_payment
        if earliest is not None and request.request_date < earliest <= request.desired_completion_date:
            templates.append(PaymentTemplate(RecommendationMethod.WAIT,
                                             (Payment(earliest, amount),), None))
        elif earliest is None:
            diagnostics.append("wait_no_safe_date")
    else:
        diagnostics.append("no_accepted_method_wait")
    return templates, diagnostics


def build_no_change_candidate_pool(case: RequestCase, baseline: BaselineForecast) -> CandidatePool:
    """Enumerate method/deadline-eligible no-change templates and certify safe candidates."""
    capacity = compute_baseline_capacity(case, baseline)
    full_option_id = _validate_full_option(case, case.payment_options)
    templates, diagnostics = _no_change_templates(case, baseline, capacity, full_option_id)
    candidates: list[PlanCandidate] = []
    for template in templates:
        replay = replay_schedule(case, baseline, template.payments)
        complete = _chronological_complete(template.payments, case, baseline)
        if template.recommendation_method is RecommendationMethod.FULL_PAYMENT or \
                template.recommendation_method is RecommendationMethod.WAIT:
            amount_ok = template.payments[-1].amount == case.request.requested_amount and len(template.payments) == 1
        elif template.recommendation_method is RecommendationMethod.PARTIAL_PAYMENT:
            amount_ok = (len(template.payments) == 2 and
                         sum((payment.amount for payment in template.payments), Decimal("0")) == case.request.requested_amount)
        else:
            amount_ok = True
        if complete and amount_ok and replay.safe:
            candidates.append(PlanCandidate(template.recommendation_method, template.payments, (),
                                            template.payment_option_id, replay, Decimal("0")))
        else:
            diagnostics.append("unsafe_replay")
    return CandidatePool(case.request.request_id, capacity, tuple(templates), tuple(candidates),
                         tuple(diagnostics))


# --- WP-07B spending-change enumeration and changed candidates ---------------


@dataclass(frozen=True)
class SpendingChangeAction:
    """One permitted action on one fixed-recurrence family anchor event."""

    change_type: SpendingChangeType
    event_id: str
    new_amount: Decimal | None = None


@dataclass(frozen=True)
class FamilyAction:
    """Eligible actions for one family, plus every canonical nonempty set."""

    family_id: str
    anchor_event_id: str
    actions: tuple[SpendingChangeAction, ...]
    action_sets: tuple[tuple[SpendingChangeAction, ...], ...]


def _family_catalogue(case: RequestCase, baseline: BaselineForecast) -> dict[str, dict]:
    """Family catalogue from future fixed-recurrence debit movements.

    Maps family_id -> {anchor_event_id, source_amounts, movements}. Only
    primitive movements with phase == 'debit', origin == 'fixed_recurrence',
    a nonblank family_id, occurrence date, and exact source amount/currency
    qualify; explicit commitments, reserves, variable envelopes, and credits
    never become changeable.
    """
    families: dict[str, dict] = {}
    for movement in baseline.primitive_movements:
        if (movement.phase != "debit" or movement.origin != "fixed_recurrence" or
                not movement.family_id or movement.occurrence_date is None or
                not _is_money(movement.source_amount) or not movement.source_currency or
                not movement.home_currency):
            continue
        if movement.date < case.request.request_date:
            continue
        entry = families.setdefault(movement.family_id, {"movements": [], "anchors": set()})
        entry["movements"].append(movement)
        for event_id in movement.source_event_ids:
            if event_id:
                entry["anchors"].add(event_id)
    # An anchor event must resolve to exactly one family; events shared across
    # families are ambiguous and produce no action anywhere.
    event_families: dict[str, set[str]] = {}
    for family_id, entry in families.items():
        for event_id in entry["anchors"]:
            event_families.setdefault(event_id, set()).add(family_id)
    for entry in families.values():
        entry["anchors"] = {event_id for event_id in entry["anchors"] if len(event_families[event_id]) == 1}
    return families


def enumerate_spending_change_actions(case: RequestCase,
                                      baseline: BaselineForecast) -> tuple[FamilyAction, ...]:
    """Return eligible per-family actions with canonical nonempty action sets."""
    families = _family_catalogue(case, baseline)
    protected = case.profile.expense_categories_to_protect
    reduce_cats = case.profile.expense_categories_user_is_willing_to_reduce
    stop_cats = case.profile.expense_categories_user_is_willing_to_stop
    family_actions: list[FamilyAction] = []
    for family_id in sorted(families):
        entry = families[family_id]
        movements = entry["movements"]
        # A source event must identify one exact forecast occurrence. Select the
        # latest supplied historical anchor, then stable event ID; only a future
        # supplied event may anchor when no historical event is available.
        compatible = [event for event in case.events if event.event_id in entry["anchors"]]
        historical = [event for event in compatible
                      if event.settlement_date is not None and event.settlement_date < case.request.request_date]
        anchors = historical or compatible
        if not anchors:
            continue
        anchor_event = max(anchors, key=lambda event: (event.settlement_date or event.event_date, event.event_id))
        anchor_event_id = anchor_event.event_id
        matching = [movement for movement in movements if anchor_event_id in movement.source_event_ids]
        if len({movement.date for movement in matching}) != len(matching):
            continue
        category = anchor_event.category
        if category in protected:
            continue
        flexibilities = {anchor_event.flexibility}
        allow_reduce = (flexibilities & {Flexibility.REDUCIBLE, Flexibility.REDUCIBLE_OR_STOPPABLE} and
                        category in reduce_cats)
        allow_stop = (flexibilities & {Flexibility.STOPPABLE, Flexibility.REDUCIBLE_OR_STOPPABLE} and
                      category in stop_cats)
        actions: list[SpendingChangeAction] = []
        if allow_stop:
            actions.append(SpendingChangeAction(SpendingChangeType.STOP, anchor_event_id))
        if allow_reduce:
            floor = anchor_event.minimum_allowed_amount
            if (isinstance(floor, Decimal) and floor.is_finite() and floor >= 0 and
                    all(floor < movement.source_amount for movement in movements
                        if movement.source_amount is not None)):
                actions.append(SpendingChangeAction(SpendingChangeType.REDUCE_TO, anchor_event_id, floor))
        if not actions:
            continue
        # Canonical nonempty action sets: one action per family, never stop+reduce.
        single = [((action,),) for action in actions]
        action_sets: tuple[tuple[SpendingChangeAction, ...], ...]
        action_sets = tuple(sorted((set_[0] for set_ in single),
                                   key=lambda s: (s[0].change_type.value, s[0].event_id,
                                                  str(s[0].new_amount))))
        family_actions.append(FamilyAction(family_id, anchor_event_id, tuple(actions), action_sets))
    return tuple(family_actions)


def _action_sets(family_actions: tuple[FamilyAction, ...]) -> tuple[tuple[SpendingChangeAction, ...], ...]:
    """Every canonical combination of one-to-three distinct families."""
    combinations: list[tuple[SpendingChangeAction, ...]] = []

    def extend(index: int, current: tuple[SpendingChangeAction, ...]) -> None:
        if len(current) >= 3:
            return
        if index >= len(family_actions):
            return
        for action_set in family_actions[index].action_sets:
            new = current + action_set
            combinations.append(new)
            extend(index + 1, new)
        extend(index + 1, current)

    extend(0, ())
    combinations.sort(key=lambda s: (
        len(s),
        tuple((action.event_id, action.change_type.value, str(action.new_amount)) for action in s),
    ))
    return tuple(combinations)


def _canonical_changes(changes: tuple[SpendingChangeAction, ...]) -> tuple[SpendingChange, ...]:
    ordered = sorted(changes, key=lambda a: (a.event_id, a.change_type.value, str(a.new_amount)))
    return tuple(SpendingChange(action.change_type, action.event_id, action.new_amount) for action in ordered)


def _zero_payment_reduction(case: RequestCase, baseline: BaselineForecast,
                            changes: tuple[SpendingChange, ...]) -> Decimal | None:
    baseline_replay = replay_schedule(case, baseline)
    changed_replay = replay_schedule(case, baseline, (), changes)
    if baseline_replay.minimum_headroom is None or changed_replay.minimum_headroom is None:
        return None
    reduction = changed_replay.minimum_headroom - baseline_replay.minimum_headroom
    if reduction < 0:
        return None
    return reduction


def _changed_templates(case: RequestCase, baseline: BaselineForecast,
                       eligible_templates: tuple[PaymentTemplate, ...],
                       family_actions: tuple[FamilyAction, ...]) -> tuple[list[PlanCandidate], list[str]]:
    """Certify changed candidates: non-wait templates plus exhaustive changed dates."""
    candidates: list[PlanCandidate] = []
    diagnostics: list[str] = []
    accepted_full = RecommendationMethod.FULL_PAYMENT.value in {
        method.value for method in case.profile.payment_methods_user_will_consider}
    requested = case.request.requested_amount
    deadline = case.request.desired_completion_date
    horizon_end = baseline.horizon_end
    request_date = case.request.request_date
    seen: set[tuple] = set()
    last_search_day = min(deadline, horizon_end)
    for action_set in _action_sets(family_actions):
        changes = _canonical_changes(action_set)
        anchor_ids = tuple(sorted({action.event_id for action in action_set}))
        applied: dict[tuple, PlanCandidate] = {}
        for template in eligible_templates:
            if template.recommendation_method is RecommendationMethod.WAIT:
                continue
            replay = replay_schedule(case, baseline, template.payments, changes)
            # Applied IDs are compared as an ordered set: the replay records
            # them in chronological application order, which need not equal the
            # canonical sorted anchor order for multi-family sets.
            if not replay.safe or tuple(sorted(replay.applied_change_event_ids)) != anchor_ids:
                if replay.first_failure is not None and replay.first_failure.reason_code not in {
                        "minimum_balance_breach", "payment_invalid"}:
                    diagnostics.append(f"changed_{replay.first_failure.reason_code}")
                continue
            if not _chronological_complete(template.payments, case, baseline):
                continue
            amount_ok = (sum((payment.amount for payment in template.payments), Decimal("0")) ==
                         (requested if template.recommendation_method is not RecommendationMethod.INSTALLMENTS
                          else template.payments[-1].amount * len(template.payments)))
            if not amount_ok:
                continue
            reduction = _zero_payment_reduction(case, baseline, changes)
            if reduction is None:
                continue
            key = (template.recommendation_method, template.payment_option_id, template.payments, changes)
            if key in seen:
                continue
            seen.add(key)
            applied[key] = PlanCandidate(template.recommendation_method, template.payments, changes,
                                         template.payment_option_id, replay, reduction)
        candidates.extend(applied.values())
        # Exhaustively test one full payment on every date D..min(deadline, horizon_end).
        if accepted_full:
            earliest: date | None = None
            for offset in range((last_search_day - request_date).days + 1):
                day = request_date + timedelta(days=offset)
                replay = replay_schedule(case, baseline, (Payment(day, requested),), changes)
                if replay.safe and tuple(sorted(replay.applied_change_event_ids)) == anchor_ids:
                    earliest = day
                    break
            if earliest is not None:
                method = RecommendationMethod.FULL_PAYMENT if earliest == request_date else RecommendationMethod.WAIT
                key = (method, None, (Payment(earliest, requested),), changes)
                if key not in seen:
                    seen.add(key)
                    reduction = _zero_payment_reduction(case, baseline, changes)
                    if reduction is not None:
                        candidates.append(PlanCandidate(method, (Payment(earliest, requested),), changes,
                                                        None, replay, reduction))
    return candidates, diagnostics


# --- WP-07C ranking and decision ---------------------------------------------


@dataclass(frozen=True)
class PlanningDecision:
    request_id: str
    capacity: CapacityResult
    selected_candidate: PlanCandidate | None
    affordability_status: AffordabilityStatus
    recommended_method: RecommendationMethod
    diagnostics: tuple[str, ...]


_METHOD_KEY = {
    RecommendationMethod.FULL_PAYMENT: 0,
    RecommendationMethod.PARTIAL_PAYMENT: 1,
    RecommendationMethod.INSTALLMENTS: 2,
    RecommendationMethod.WAIT: 3,
    RecommendationMethod.NOT_RECOMMENDED: 4,
}


def _rendered_action_text(changes: tuple[SpendingChange, ...]) -> str:
    return ";".join(f"{change.change_type.value}:{change.event_id}:{change.new_amount}"
                    for change in changes)


class _OptionTieKey:
    """Total three-state option key: supplied offers sort before derived plans,
    and supplied offers compare by stable text ID among themselves.

    Comparing residuals (actions, reduction, action text) before this key keeps
    mixed supplied/derived pairs decided by the published residual criteria,
    while the total order here removes the input-order dependence of min().
    """

    __slots__ = ("is_supplied", "option_id")

    def __init__(self, option_id: str | None) -> None:
        self.is_supplied = option_id is not None
        self.option_id = option_id or ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _OptionTieKey):
            return NotImplemented
        return (self.is_supplied == other.is_supplied
                and self.option_id == other.option_id)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _OptionTieKey):
            return NotImplemented
        if self.is_supplied != other.is_supplied:
            return self.is_supplied
        return self.option_id < other.option_id


def rank_key(candidate: PlanCandidate) -> tuple:
    """Published deterministic comparator: every key is explicit, never ordinal/order.

    The residual keys precede the total option key so mixed supplied/derived
    pairs stay decided by published residual criteria; the option key remains
    total so the comparator is a strict total order for every candidate set.
    """
    return (
        1 if candidate.spending_changes else 0,
        candidate.total_paid,
        candidate.start,
        candidate.payment_count,
        len(candidate.spending_changes),
        candidate.forecast_debit_reduction,
        _rendered_action_text(candidate.spending_changes),
        _OptionTieKey(candidate.payment_option_id),
        _METHOD_KEY[candidate.recommendation_method],
    )


def _fallback_diagnostic(case: RequestCase, baseline: BaselineForecast,
                         pool: CandidatePool) -> str:
    """Truthful precedence: uncertified; after-deadline-only; no method/option; no safe candidate."""
    if baseline.blocks_downstream or baseline.minimum_headroom is None:
        return "fallback_baseline_uncertified"
    deadline = case.request.desired_completion_date
    search_end = min(deadline, baseline.horizon_end)
    deadline_days = (search_end - case.request.request_date).days
    horizon_days = (baseline.horizon_end - case.request.request_date).days
    possible_within_deadline = any(
        replay_schedule(case, baseline,
                        (Payment(case.request.request_date + timedelta(days=offset),
                                 case.request.requested_amount),)).safe
        for offset in range(deadline_days + 1))
    if not possible_within_deadline:
        # Financially possible only after the deadline, regardless of preferences.
        for offset in range(deadline_days + 1, horizon_days + 1):
            day = case.request.request_date + timedelta(days=offset)
            if replay_schedule(case, baseline, (Payment(day, case.request.requested_amount),)).safe:
                return "fallback_possible_after_deadline"
    if not pool.eligible_templates:
        return "fallback_no_accepted_method"
    return "fallback_no_safe_candidate"


def plan_request(case: RequestCase, baseline: BaselineForecast) -> PlanningDecision:
    """Rank certified candidates and derive one status/method from the winner."""
    pool = build_candidate_pool(case, baseline)
    if not pool.candidates:
        diagnostic = _fallback_diagnostic(case, baseline, pool)
        return PlanningDecision(pool.request_id, pool.capacity, None,
                                AffordabilityStatus.NOT_AFFORDABLE,
                                RecommendationMethod.NOT_RECOMMENDED, (diagnostic,))
    winner = min(pool.candidates, key=rank_key)
    method = winner.recommendation_method
    if method is RecommendationMethod.WAIT:
        status = (AffordabilityStatus.AFFORDABLE_LATER if not winner.spending_changes
                  else AffordabilityStatus.AFFORDABLE_WITH_PLAN)
    elif method is RecommendationMethod.FULL_PAYMENT:
        status = (AffordabilityStatus.AFFORDABLE_NOW if not winner.spending_changes
                  else AffordabilityStatus.AFFORDABLE_WITH_PLAN)
    else:
        status = AffordabilityStatus.AFFORDABLE_WITH_PLAN
    return PlanningDecision(pool.request_id, pool.capacity, winner, status, method, ())


def build_candidate_pool(case: RequestCase, baseline: BaselineForecast) -> CandidatePool:
    """Extend the accepted no-change pool with permitted changed candidates."""
    pool = build_no_change_candidate_pool(case, baseline)
    family_actions = enumerate_spending_change_actions(case, baseline)
    if not family_actions:
        return pool
    changed, diagnostics = _changed_templates(case, baseline, pool.eligible_templates, family_actions)
    return CandidatePool(pool.request_id, pool.capacity, pool.eligible_templates,
                         pool.candidates + tuple(changed), pool.diagnostics + tuple(diagnostics))

"""WP-08A typed output row, grounded explanation, and canonical field codecs.

Deterministic, standard-library-only boundary. Consumes one accepted WP-07
``PlanningDecision`` with its unchanged WP-06 capacity and renders one typed
``OutputRow`` and a grounded explanation. No file I/O, no independent
financial validation, no ranking, no forecast, no provider access, and no
pipeline wiring here; WP-08B validates and WP-08C writes the CSV.
"""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from buy_or_wait.domain import (
    AffordabilityStatus, OutputRow, Payment, PaymentMethod, PaymentOptionRecord, RecommendedPaymentMethod,
    RequestCase, RequestScope, SpendingChange, SpendingChangeType,
)
from buy_or_wait.forecast import BaselineForecast
from buy_or_wait.planning import (
    CapacityResult, PlanningDecision, RecommendationMethod, compute_baseline_capacity,
    enumerate_spending_change_actions, replay_schedule,
)


OUTPUT_COLUMNS: tuple[str, ...] = (
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
)

_METHOD_FIELDS = frozenset({
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
})


class OutputValidationError(ValueError):
    """Source-safe error carrying a stable reason code and optional field/request."""

    def __init__(self, reason_code: str, *, request_id: str | None = None,
                 field: str | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.request_id = request_id
        self.field = field


# --- canonical lexical helpers (private) ------------------------------------


def _plain_decimal(value: Decimal, *, trim_scalar: bool = False) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise OutputValidationError("invalid_amount")
    text = format(value, "f")
    if trim_scalar:
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        if text in ("", "-0"):
            text = "0"
        return text
    if value == 0:
        return "0"
    if value == value.to_integral_value():
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    if "." in text:
        integer, fraction = text.split(".", 1)
        if len(fraction) < 2:
            fraction = fraction + "0" * (2 - len(fraction))
        text = f"{integer}.{fraction}"
    return text


def _format_iso_date(value: date) -> str:
    if not isinstance(value, date):
        raise OutputValidationError("invalid_date")
    return value.isoformat()


def _format_plan(payments: tuple[object, ...]) -> str:
    if not payments:
        return "none"
    tokens: list[str] = []
    previous: date | None = None
    for payment in payments:
        if not isinstance(payment, Payment) or not isinstance(payment.payment_date, date) \
                or not _is_money(payment.amount, positive=True):
            raise OutputValidationError("invalid_payment")
        if previous is not None and payment.payment_date < previous:
            raise OutputValidationError("payment_out_of_order")
        previous = payment.payment_date
        tokens.append(f"{_format_iso_date(payment.payment_date)}:{_plain_decimal(payment.amount)}")
    return "|".join(tokens)


def _format_changes(changes: tuple[object, ...]) -> str:
    if not changes:
        return "none"
    ordered = sorted(
        (change for change in changes if isinstance(change, SpendingChange)),
        key=lambda change: (change.event_id, change.change_type.value,
                            _plain_decimal(change.new_amount) if change.new_amount is not None else ""),
    )
    tokens: list[str] = []
    for change in ordered:
        if not isinstance(change.event_id, str) or not change.event_id:
            raise OutputValidationError("invalid_change")
        if change.change_type is SpendingChangeType.STOP:
            tokens.append(f"stop:{change.event_id}")
        elif change.change_type is SpendingChangeType.REDUCE_TO:
            if not _is_money(change.new_amount) or change.new_amount < 0:
                raise OutputValidationError("invalid_change_amount")
            tokens.append(f"reduce_to:{change.event_id}:{_plain_decimal(change.new_amount)}")
        else:
            raise OutputValidationError("invalid_change_type")
    return "|".join(tokens)


def _is_money(value: object, *, positive: bool = False) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and (value > 0 if positive else True)


# --- public seam -------------------------------------------------------------


def serialize_output_row(row: OutputRow) -> dict[str, str]:
    """Render a typed ``OutputRow`` to the canonical eight-field string mapping."""
    if not isinstance(row, OutputRow):
        raise OutputValidationError("invalid_row")
    serialized = {
        "request_id": str(row.request_id),
        "amount_safe_to_pay": _plain_decimal(row.amount_safe_to_pay, trim_scalar=True),
        "affordability_status": _enum_value(row.affordability_status),
        "recommended_payment_method": _enum_value(row.recommended_payment_method),
        "payment_plan": _format_plan(row.payment_plan),
        "earliest_date_for_full_payment": _format_iso_date(row.earliest_date_for_full_payment) if row.earliest_date_for_full_payment is not None else "",
        "spending_changes_needed": _format_changes(row.spending_changes_needed),
        "decision_explanation": str(row.decision_explanation),
    }
    return serialized


def _enum_value(value: object) -> str:
    if isinstance(value, RecommendedPaymentMethod):
        return value.value
    if isinstance(value, AffordabilityStatus):
        return value.value
    raise OutputValidationError("invalid_enum")


# --- strict row parsing ------------------------------------------------------


def _parse_plain_decimal(text: str, *, trim_scalar: bool = False) -> Decimal:
    if not isinstance(text, str) or not text:
        raise OutputValidationError("invalid_amount")
    try:
        parsed = Decimal(text)
    except Exception as error:
        raise OutputValidationError("invalid_amount") from error
    if not parsed.is_finite():
        raise OutputValidationError("invalid_amount")
    if text != _plain_decimal(parsed, trim_scalar=trim_scalar):
        raise OutputValidationError("invalid_amount")
    return parsed


def _parse_plan(text: str) -> tuple[Payment, ...]:
    if text == "none":
        return ()
    if not isinstance(text, str) or not text:
        raise OutputValidationError("invalid_plan")
    tokens = text.split("|")
    if any(token == "" for token in tokens):
        raise OutputValidationError("invalid_plan")
    payments: list[Payment] = []
    previous: date | None = None
    for token in tokens:
        if token.count(":") != 1:
            raise OutputValidationError("invalid_plan")
        date_text, amount_text = token.split(":")
        try:
            payment_date = date.fromisoformat(date_text)
        except Exception as error:
            raise OutputValidationError("invalid_plan") from error
        if payment_date.isoformat() != date_text:
            raise OutputValidationError("invalid_plan")
        amount = _parse_plain_decimal(amount_text)
        if not _is_money(amount, positive=True):
            raise OutputValidationError("invalid_plan")
        if previous is not None and payment_date < previous:
            raise OutputValidationError("invalid_plan")
        previous = payment_date
        payments.append(Payment(payment_date, amount))
    return tuple(payments)


def _parse_changes(text: str) -> tuple[SpendingChange, ...]:
    if text == "none":
        return ()
    if not isinstance(text, str) or not text:
        raise OutputValidationError("invalid_changes")
    tokens = text.split("|")
    if any(token == "" for token in tokens):
        raise OutputValidationError("invalid_changes")
    changes: list[SpendingChange] = []
    for token in tokens:
        if token.startswith("stop:"):
            event_id = token[len("stop:"):]
            if not event_id or ":" in event_id:
                raise OutputValidationError("invalid_changes")
            changes.append(SpendingChange(SpendingChangeType.STOP, event_id))
        elif token.startswith("reduce_to:"):
            rest = token[len("reduce_to:"):]
            if rest.count(":") != 1:
                raise OutputValidationError("invalid_changes")
            event_id, amount_text = rest.split(":")
            amount = _parse_plain_decimal(amount_text)
            if not _is_money(amount) or amount < 0:
                raise OutputValidationError("invalid_changes")
            changes.append(SpendingChange(SpendingChangeType.REDUCE_TO, event_id, amount))
        else:
            raise OutputValidationError("invalid_changes")
    if len({change.event_id for change in changes}) != len(changes):
        raise OutputValidationError("invalid_changes")
    ordered = tuple(sorted(changes, key=lambda change: (change.event_id, change.change_type.value,
                                                        _plain_decimal(change.new_amount) if change.new_amount is not None else "")))
    if ordered != tuple(changes):
        raise OutputValidationError("invalid_changes")
    return ordered


def parse_output_row(values: Mapping[str, str]) -> OutputRow:
    """Parse one canonical eight-field mapping back into a typed ``OutputRow``."""
    if not isinstance(values, Mapping):
        raise OutputValidationError("invalid_row")
    if set(values) != _METHOD_FIELDS:
        raise OutputValidationError("invalid_fields")
    request_id = str(values["request_id"])
    if not request_id:
        raise OutputValidationError("invalid_request_id")
    amount = _parse_plain_decimal(values["amount_safe_to_pay"], trim_scalar=True)
    if not _is_money(amount):
        raise OutputValidationError("invalid_amount")
    status = _parse_enum(AffordabilityStatus, values["affordability_status"])
    method = _parse_enum(RecommendedPaymentMethod, values["recommended_payment_method"])
    earliest_text = values["earliest_date_for_full_payment"]
    earliest: date | None
    if earliest_text == "":
        earliest = None
    else:
        try:
            earliest = date.fromisoformat(earliest_text)
        except Exception as error:
            raise OutputValidationError("invalid_date") from error
        if earliest.isoformat() != earliest_text:
            raise OutputValidationError("invalid_date")
    plan = _parse_plan(values["payment_plan"])
    changes = _parse_changes(values["spending_changes_needed"])
    return OutputRow(request_id, amount, status, method, plan, earliest, changes,
                     str(values["decision_explanation"]))


def _parse_enum(enum_cls, text: str):
    if not isinstance(text, str):
        raise OutputValidationError("invalid_enum")
    try:
        return enum_cls(text)
    except ValueError as error:
        raise OutputValidationError("invalid_enum") from error


# --- decision -> row + explanation -------------------------------------------


def explain_decision(case: RequestCase, baseline: BaselineForecast,
                     decision: PlanningDecision) -> str:
    """Deterministic grounded prose from case/baseline/decision only."""
    if decision.selected_candidate is None:
        return _fallback_text(decision.diagnostics)
    method = decision.recommended_method
    candidate = decision.selected_candidate
    payments = candidate.payments
    changes = candidate.spending_changes
    protected = _plain_decimal(baseline.minimum_balance)
    if method is RecommendationMethod.FULL_PAYMENT:
        if not changes:
            amount = _plain_decimal(candidate.total_paid)
            return (f"Pay the full {amount} on {_format_iso_date(payments[0].payment_date)}; "
                    f"{protected} is protected to keep your balance safe.")
        actions = _format_changes(changes)
        amount = _plain_decimal(candidate.total_paid)
        return (f"After {actions}, pay the full {amount} on {_format_iso_date(payments[0].payment_date)}; "
                f"{protected} is protected to keep your balance safe.")
    if method is RecommendationMethod.PARTIAL_PAYMENT:
        first = payments[0]
        second = payments[1]
        return (f"Pay {_plain_decimal(first.amount)} on {_format_iso_date(first.payment_date)} and "
                f"the remaining {_plain_decimal(second.amount)} on {_format_iso_date(second.payment_date)}; "
                f"{protected} is protected to keep your balance safe.")
    if method is RecommendationMethod.INSTALLMENTS:
        count = len(payments)
        total = candidate.total_paid
        first_date = _format_iso_date(payments[0].payment_date)
        last_date = _format_iso_date(payments[-1].payment_date)
        return (f"Pay {count} installments totaling {_plain_decimal(total)} from {first_date} to {last_date}; "
                f"{protected} is protected to keep your balance safe.")
    if method is RecommendationMethod.WAIT:
        payment = payments[0]
        if not changes:
            return (f"Pay the full {_plain_decimal(payment.amount)} on {_format_iso_date(payment.payment_date)}, "
                    f"your earliest safe date; {protected} is protected to keep your balance safe.")
        actions = _format_changes(changes)
        return (f"After {actions}, pay the full {_plain_decimal(payment.amount)} on "
                f"{_format_iso_date(payment.payment_date)}; {protected} is protected to keep your balance safe.")
    return _fallback_text(decision.diagnostics)


def _fallback_text(diagnostics: tuple[str, ...]) -> str:
    reason = diagnostics[0] if diagnostics else "fallback_no_safe_candidate"
    if reason == "fallback_baseline_uncertified":
        return "an unbounded required debit prevents certifying any safe amount now."
    if reason == "fallback_possible_after_deadline":
        return "the first safe date after deadline is the earliest possible full payment."
    if reason == "fallback_no_accepted_method":
        return "no accepted eligible method or option is available."
    return "no safe complete plan is available in the required horizon."


def build_output_row(case: RequestCase, baseline: BaselineForecast,
                     decision: PlanningDecision) -> OutputRow:
    """Convert one accepted planning decision into a typed ``OutputRow``."""
    if not isinstance(decision, PlanningDecision) or decision.request_id != case.request.request_id:
        raise OutputValidationError("decision_case_mismatch", request_id=getattr(decision, "request_id", None))
    method = _output_method(decision.recommended_method)
    if decision.selected_candidate is None:
        payments: tuple[Payment, ...] = ()
        changes: tuple[SpendingChange, ...] = ()
    else:
        payments = decision.selected_candidate.payments
        changes = decision.selected_candidate.spending_changes
    explanation = explain_decision(case, baseline, decision)
    return OutputRow(case.request.request_id, decision.capacity.amount_safe_to_pay,
                     decision.affordability_status, method, payments,
                     decision.capacity.earliest_date_for_full_payment, changes, explanation)


def _output_method(method: RecommendationMethod) -> RecommendedPaymentMethod:
    if method is RecommendationMethod.FULL_PAYMENT:
        return RecommendedPaymentMethod.FULL_PAYMENT
    if method is RecommendationMethod.PARTIAL_PAYMENT:
        return RecommendedPaymentMethod.PARTIAL_PAYMENT
    if method is RecommendationMethod.INSTALLMENTS:
        return RecommendedPaymentMethod.INSTALLMENTS
    if method is RecommendationMethod.WAIT:
        return RecommendedPaymentMethod.WAIT
    return RecommendedPaymentMethod.NOT_RECOMMENDED


# --- WP-08B independent single-row validation --------------------------------


def _recompute_capacity(case: RequestCase, baseline: BaselineForecast) -> CapacityResult:
    return compute_baseline_capacity(case, baseline)


def validate_output_row(row: OutputRow, case: RequestCase, baseline: BaselineForecast,
                        decision: PlanningDecision) -> None:
    """Reject any row that disagrees with case, capacity, decision, or fresh replay.

    Deterministic, offline, side-effect free. Independent checks run before
    decision agreement so jointly corrupt row/decision values cannot bypass
    capacity, option/action, or replay rules.
    """
    if not isinstance(row, OutputRow):
        raise OutputValidationError("invalid_row")
    if not isinstance(case, RequestCase):
        raise OutputValidationError("invalid_case")
    if not isinstance(baseline, BaselineForecast) or baseline.request_id != case.request.request_id:
        raise OutputValidationError("invalid_baseline")
    if not isinstance(decision, PlanningDecision) or decision.request_id != case.request.request_id:
        raise OutputValidationError("invalid_decision")
    _validate_decision_coherence(decision)
    if row.request_id != case.request.request_id:
        raise OutputValidationError("request_id_mismatch", field="request_id")
    if not _is_money(row.amount_safe_to_pay) or row.amount_safe_to_pay < 0:
        raise OutputValidationError("amount_out_of_range", field="amount_safe_to_pay")
    if row.amount_safe_to_pay > case.request.requested_amount:
        raise OutputValidationError("amount_exceeds_requested", field="amount_safe_to_pay")

    capacity = _recompute_capacity(case, baseline)
    if row.amount_safe_to_pay != capacity.amount_safe_to_pay:
        raise OutputValidationError("safe_amount_mismatch", field="amount_safe_to_pay")
    if row.earliest_date_for_full_payment != capacity.earliest_date_for_full_payment:
        raise OutputValidationError("earliest_date_mismatch", field="earliest_date_for_full_payment")

    _validate_plan_by_method(row, case, baseline, decision)
    _validate_changes(row, case, baseline)
    _validate_replay(row, case, baseline)
    _validate_status_method_table(row, decision)

    expected_explanation = explain_decision(case, baseline, decision)
    if row.decision_explanation != expected_explanation:
        raise OutputValidationError("explanation_mismatch", field="decision_explanation")

    if row.recommended_payment_method != _output_method(decision.recommended_method):
        raise OutputValidationError("method_mismatch", field="recommended_payment_method")
    if row.affordability_status != decision.affordability_status:
        raise OutputValidationError("status_mismatch", field="affordability_status")


def _validate_plan_by_method(row: OutputRow, case: RequestCase, baseline: BaselineForecast,
                             decision: PlanningDecision) -> None:
    method = row.recommended_payment_method
    plan = row.payment_plan
    requested = case.request.requested_amount
    accepted = {candidate.value for candidate in case.profile.payment_methods_user_will_consider}
    if method is RecommendedPaymentMethod.NOT_RECOMMENDED:
        if plan or row.spending_changes_needed:
            raise OutputValidationError("not_recommended_has_plan_or_changes", field="payment_plan")
        return
    if not plan:
        raise OutputValidationError("missing_plan", field="payment_plan")
    if method is RecommendedPaymentMethod.FULL_PAYMENT:
        if PaymentMethod.FULL_PAYMENT.value not in accepted:
            raise OutputValidationError("full_preference_excluded", field="recommended_payment_method")
        if len(plan) != 1 or plan[0].payment_date != case.request.request_date \
                or plan[0].amount != requested:
            raise OutputValidationError("full_plan_mismatch", field="payment_plan")
        return
    if method is RecommendedPaymentMethod.WAIT:
        if PaymentMethod.FULL_PAYMENT.value not in accepted:
            raise OutputValidationError("wait_preference_excluded", field="recommended_payment_method")
        if len(plan) != 1 or plan[0].payment_date <= case.request.request_date \
                or plan[0].amount != requested:
            raise OutputValidationError("wait_plan_mismatch", field="payment_plan")
        deadline = case.request.desired_completion_date
        if plan[0].payment_date > deadline:
            raise OutputValidationError("wait_after_deadline", field="payment_plan")
        return
    if method is RecommendedPaymentMethod.PARTIAL_PAYMENT:
        if PaymentMethod.PARTIAL_PAYMENT.value not in accepted:
            raise OutputValidationError("partial_preference_excluded", field="recommended_payment_method")
        if not case.request.allows_partial_payment:
            raise OutputValidationError("partial_not_allowed", field="payment_plan")
        if len(plan) != 2:
            raise OutputValidationError("partial_plan_mismatch", field="payment_plan")
        first, second = plan
        safe = row.amount_safe_to_pay
        if not (0 < safe < requested):
            raise OutputValidationError("partial_safe_not_in_range", field="amount_safe_to_pay")
        if first.payment_date != case.request.request_date or first.amount != safe:
            raise OutputValidationError("partial_first_mismatch", field="payment_plan")
        earliest = row.earliest_date_for_full_payment
        if earliest is None or second.payment_date != earliest or second.amount != requested - safe:
            raise OutputValidationError("partial_second_mismatch", field="payment_plan")
        if second.payment_date > case.request.desired_completion_date:
            raise OutputValidationError("partial_after_deadline", field="payment_plan")
        return
    if method is RecommendedPaymentMethod.INSTALLMENTS:
        _validate_installments(row, case, baseline, decision)
        return
    raise OutputValidationError("unknown_method", field="recommended_payment_method")


def _validate_installments(row: OutputRow, case: RequestCase, baseline: BaselineForecast,
                           decision: PlanningDecision) -> None:
    if PaymentMethod.INSTALLMENTS.value not in {
            candidate.value for candidate in case.profile.payment_methods_user_will_consider}:
        raise OutputValidationError("installment_preference_excluded", field="recommended_payment_method")
    option = _decision_installment_option(case, decision)
    plan = row.payment_plan
    expected = _expected_installment_payments(option, case)
    if plan != expected:
        raise OutputValidationError("installment_plan_mismatch", field="payment_plan")
    count = len(plan)
    if count <= 0 or option.number_of_payments != count:
        raise OutputValidationError("installment_count_mismatch", field="payment_plan")
    if count > (case.profile.max_installment_months or 0):
        raise OutputValidationError("installment_cap_exceeded", field="payment_plan")
    if plan[-1].payment_date > case.request.desired_completion_date:
        raise OutputValidationError("installment_after_deadline", field="payment_plan")
    if plan[-1].payment_date > baseline.horizon_end:
        raise OutputValidationError("installment_after_horizon", field="payment_plan")
    total = sum((payment.amount for payment in plan), Decimal("0"))
    if total != option.total_payable_amount:
        raise OutputValidationError("installment_total_mismatch", field="payment_plan")
    if option.financing_fee < 0:
        raise OutputValidationError("installment_negative_fee", field="payment_plan")


def _decision_installment_option(case: RequestCase, decision: PlanningDecision) -> PaymentOptionRecord:
    if decision.selected_candidate is None:
        raise OutputValidationError("installment_no_candidate", field="payment_plan")
    option_id = decision.selected_candidate.payment_option_id
    if option_id is None:
        raise OutputValidationError("installment_no_option_id", field="payment_plan")
    option = next((candidate for candidate in case.payment_options
                   if candidate.payment_option_id == option_id), None)
    if option is None or option.payment_method is not PaymentMethod.INSTALLMENTS:
        raise OutputValidationError("installment_option_missing", field="payment_plan")
    return option


def _validate_decision_coherence(decision: PlanningDecision) -> None:
    """Reject a tampered decision before its renderer indexes candidate payments."""
    candidate = decision.selected_candidate
    if decision.recommended_method is RecommendationMethod.NOT_RECOMMENDED:
        if candidate is not None:
            raise OutputValidationError("invalid_decision", field="decision")
        return
    if candidate is None or candidate.recommendation_method is not decision.recommended_method:
        raise OutputValidationError("invalid_decision", field="decision")
    payments = candidate.payments
    if decision.recommended_method in {RecommendationMethod.FULL_PAYMENT, RecommendationMethod.WAIT}:
        valid_count = len(payments) == 1
    elif decision.recommended_method is RecommendationMethod.PARTIAL_PAYMENT:
        valid_count = len(payments) == 2
    else:
        valid_count = len(payments) > 0
    if not valid_count:
        raise OutputValidationError("invalid_decision", field="decision")


def _expected_installment_payments(option: PaymentOptionRecord | None, case: RequestCase) -> tuple[Payment, ...]:
    if option is None:
        raise OutputValidationError("installment_option_invalid", field="payment_plan")
    if option.request_id != case.request.request_id or option.payment_frequency_days is None \
            or option.payment_frequency_days <= 0 or option.number_of_payments <= 0:
        raise OutputValidationError("installment_option_invalid", field="payment_plan")
    payments: list[Payment] = []
    day = option.first_payment_date
    for _ in range(option.number_of_payments):
        payments.append(Payment(day, option.payment_amount))
        day += timedelta(days=option.payment_frequency_days)
    expected_total = option.payment_amount * option.number_of_payments
    if expected_total != option.total_payable_amount or option.financing_fee < 0:
        raise OutputValidationError("installment_option_invalid", field="payment_plan")
    return tuple(payments)


def _validate_changes(row: OutputRow, case: RequestCase, baseline: BaselineForecast) -> None:
    changes = row.spending_changes_needed
    if len(changes) > 3:
        raise OutputValidationError("too_many_changes", field="spending_changes_needed")
    family_actions = enumerate_spending_change_actions(case, baseline)
    allowed: dict[str, set[tuple[SpendingChangeType, Decimal | None]]] = {}
    for family in family_actions:
        for action in family.actions:
            allowed.setdefault(action.event_id, set()).add((action.change_type, action.new_amount))
    for index, change in enumerate(changes):
        if not isinstance(change, SpendingChange) or not isinstance(change.event_id, str) or not change.event_id:
            raise OutputValidationError("change_invalid", field="spending_changes_needed")
        candidates = allowed.get(change.event_id)
        if candidates is None:
            raise OutputValidationError("change_not_eligible", field="spending_changes_needed")
        if change.change_type is SpendingChangeType.STOP:
            if change.new_amount is not None or (SpendingChangeType.STOP, None) not in candidates:
                raise OutputValidationError("change_type_mismatch", field="spending_changes_needed")
        elif change.change_type is SpendingChangeType.REDUCE_TO:
            if not _is_money(change.new_amount) or change.new_amount < 0:
                raise OutputValidationError("change_amount_invalid", field="spending_changes_needed")
            if (SpendingChangeType.REDUCE_TO, change.new_amount) not in candidates:
                raise OutputValidationError("change_type_mismatch", field="spending_changes_needed")
        else:
            raise OutputValidationError("change_type_invalid", field="spending_changes_needed")
    families = {change.event_id: True for change in changes}
    if len(families) != len(changes):
        raise OutputValidationError("change_duplicate", field="spending_changes_needed")


def _validate_replay(row: OutputRow, case: RequestCase, baseline: BaselineForecast) -> None:
    if row.recommended_payment_method is RecommendedPaymentMethod.NOT_RECOMMENDED:
        return
    replay = replay_schedule(case, baseline, row.payment_plan, row.spending_changes_needed)
    if not replay.safe:
        reason = replay.first_failure.reason_code if replay.first_failure is not None else "unsafe"
        raise OutputValidationError(f"replay_{reason}", field="payment_plan")


def _validate_status_method_table(row: OutputRow, decision: PlanningDecision) -> None:
    status, method = row.affordability_status, row.recommended_payment_method
    if method is RecommendedPaymentMethod.FULL_PAYMENT:
        if status is AffordabilityStatus.AFFORDABLE_NOW:
            if row.spending_changes_needed:
                raise OutputValidationError("affordable_now_with_changes", field="affordability_status")
        elif status is AffordabilityStatus.AFFORDABLE_WITH_PLAN:
            if not row.spending_changes_needed:
                raise OutputValidationError("with_plan_unchanged_full", field="affordability_status")
        else:
            raise OutputValidationError("full_method_wrong_status", field="affordability_status")
    elif method is RecommendedPaymentMethod.WAIT:
        if status is AffordabilityStatus.AFFORDABLE_LATER:
            if row.spending_changes_needed:
                raise OutputValidationError("affordable_later_with_changes", field="affordability_status")
        elif status is AffordabilityStatus.AFFORDABLE_WITH_PLAN:
            if not row.spending_changes_needed:
                raise OutputValidationError("with_plan_unchanged_wait", field="affordability_status")
        else:
            raise OutputValidationError("wait_method_wrong_status", field="affordability_status")
    elif method is RecommendedPaymentMethod.PARTIAL_PAYMENT:
        if status is not AffordabilityStatus.AFFORDABLE_WITH_PLAN:
            raise OutputValidationError("partial_method_wrong_status", field="affordability_status")
    elif method is RecommendedPaymentMethod.INSTALLMENTS:
        if status is not AffordabilityStatus.AFFORDABLE_WITH_PLAN:
            raise OutputValidationError("installments_method_wrong_status", field="affordability_status")
    elif method is RecommendedPaymentMethod.NOT_RECOMMENDED:
        if status is not AffordabilityStatus.NOT_AFFORDABLE:
            raise OutputValidationError("not_recommended_wrong_status", field="affordability_status")
    else:
        raise OutputValidationError("unknown_method", field="recommended_payment_method")
    # Decision agreement is checked after the independent rules above (see call site).
    _ = decision


# --- WP-08C batch and atomic writer -----------------------------------------


@dataclass(frozen=True)
class OutputContext:
    """One ordered evaluation request with its validated context triple."""

    case: RequestCase
    baseline: BaselineForecast
    decision: PlanningDecision


def _context_request_ids(contexts: Sequence[OutputContext]) -> list[str]:
    ids: list[str] = []
    for context in contexts:
        if not isinstance(context, OutputContext):
            raise OutputValidationError("invalid_context")
        if not isinstance(context.case, RequestCase):
            raise OutputValidationError("invalid_case")
        ids.append(context.case.request.request_id)
    return ids


def validate_output_batch(rows: Sequence[OutputRow],
                         contexts_in_request_order: Sequence[OutputContext]) -> None:
    """Reject any ordered batch that does not cover exactly the evaluation requests.

    Materialize the expected request order from contexts once, require every
    expected evaluation ID and no missing/duplicate/extra/out-of-order/sample
    row, then run the WP-08B single-row validator on each row with its context.
    """
    if not isinstance(rows, Sequence) or not isinstance(contexts_in_request_order, Sequence):
        raise OutputValidationError("invalid_batch")
    expected_ids = _context_request_ids(contexts_in_request_order)
    if len(expected_ids) != len(set(expected_ids)):
        raise OutputValidationError("duplicate_context")
    seen: set[str] = set()
    row_ids: list[str] = []
    for row in rows:
        if not isinstance(row, OutputRow):
            raise OutputValidationError("invalid_row")
        if row.request_id in seen:
            raise OutputValidationError("duplicate_request", request_id=row.request_id)
        seen.add(row.request_id)
        row_ids.append(row.request_id)
    expected_set = set(expected_ids)
    for rid in row_ids:
        if rid not in expected_set:
            raise OutputValidationError("extra_request", request_id=rid)
    for rid in expected_ids:
        if rid not in seen:
            raise OutputValidationError("missing_request", request_id=rid)
    if row_ids != expected_ids:
        raise OutputValidationError("out_of_order")
    rows_by_id = {row.request_id: row for row in rows}
    for context in contexts_in_request_order:
        request_id = context.case.request.request_id
        if context.case.request.scope is not RequestScope.EVALUATION:
            raise OutputValidationError("sample_scope", request_id=request_id)
        validate_output_row(rows_by_id[request_id], context.case, context.baseline, context.decision)


def _write_csv_sibling(temp_path, rows: Sequence[OutputRow]) -> None:
    with open(temp_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_COLUMNS), extrasaction="raise",
                                 quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for row in rows:
            writer.writerow(serialize_output_row(row))
        handle.flush()
        os.fsync(handle.fileno())


def _read_csv_batch(temp_path) -> tuple[list[OutputRow], list[str]]:
    with open(temp_path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(OUTPUT_COLUMNS):
            raise OutputValidationError("unexpected_header")
        parsed: list[OutputRow] = []
        ids: list[str] = []
        for raw in reader:
            if set(raw) != set(OUTPUT_COLUMNS):
                raise OutputValidationError("unexpected_cells")
            row = parse_output_row(raw)
            parsed.append(row)
            ids.append(row.request_id)
    return parsed, ids


def _reparse_equals(typed: OutputRow, parsed: OutputRow) -> bool:
    return typed == parsed and serialize_output_row(typed) == serialize_output_row(parsed)


def write_output_atomic(path: str | os.PathLike, rows: Sequence[OutputRow],
                        contexts_in_request_order: Sequence[OutputContext]) -> None:
    """Publish one validated row per evaluation request with one ``os.replace``.

    Validate the ordered batch first, then write a sibling temp in the
    destination parent, flush and fsync it, reopen and reparse it, revalidate
    the reparsed batch, require typed equality, and replace the destination
    exactly once. Any failure before replacement preserves the old destination
    byte-for-byte and removes the temp sibling. The destination is never opened
    for a truncating write.
    """
    validate_output_batch(rows, contexts_in_request_order)
    destination = os.fspath(path)
    parent = os.path.dirname(os.path.abspath(destination))
    temp_name: str | None = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".output-", suffix=".csv", dir=parent)
        os.close(fd)
        _write_csv_sibling(temp_name, rows)
        parsed, parsed_ids = _read_csv_batch(temp_name)
        if parsed_ids != [row.request_id for row in rows]:
            raise OutputValidationError("reparse_request_order")
        for typed, reparsed in zip(rows, parsed):
            if not _reparse_equals(typed, reparsed):
                raise OutputValidationError("reparse_mismatch")
        validate_output_batch(parsed, contexts_in_request_order)
        os.replace(temp_name, destination)
        temp_name = None
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass

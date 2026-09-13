"""WP-08A typed output row, grounded explanation, and canonical field codecs.

Deterministic, standard-library-only boundary. Consumes one accepted WP-07
``PlanningDecision`` with its unchanged WP-06 capacity and renders one typed
``OutputRow`` and a grounded explanation. No file I/O, no independent
financial validation, no ranking, no forecast, no provider access, and no
pipeline wiring here; WP-08B validates and WP-08C writes the CSV.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from buy_or_wait.domain import (
    AffordabilityStatus, OutputRow, Payment, RecommendedPaymentMethod, RequestCase, SpendingChange,
    SpendingChangeType,
)
from buy_or_wait.forecast import BaselineForecast
from buy_or_wait.planning import (
    PlanningDecision, RecommendationMethod,
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

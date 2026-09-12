"""Immutable domain contract for the Buy or Wait? decision engine.

Only standard-library dataclasses and enums live here. No CSV I/O, no model
calls, no financial inference. Dates are ``datetime.date``, money and rates are
finite non-negative ``Decimal`` values, permitted source blanks stay ``None``,
pipe-delimited lists become tuples, and membership-only values become frozensets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class RequestScope(Enum):
    SAMPLE = "sample"
    EVALUATION = "evaluation"


class RequestType(Enum):
    PURCHASE = "purchase"
    TRAVEL = "travel"
    HOUSING = "housing"
    EDUCATION = "education"
    DEBT_REPAYMENT = "debt_repayment"
    INVESTMENT = "investment"
    FAMILY_TRANSFER = "family_transfer"
    EMERGENCY_EXPENSE = "emergency_expense"
    OTHER = "other"


class CurrencyCode(Enum):
    ZAR = "ZAR"
    USD = "USD"
    EUR = "EUR"
    IDR = "IDR"
    INR = "INR"


class EventType(Enum):
    EXPENSE = "expense"
    SUBSCRIPTION = "subscription"
    INCOME = "income"
    DEBT_PAYMENT = "debt_payment"
    REFUND = "refund"
    INVESTMENT_PURCHASE = "investment_purchase"
    INVESTMENT_VALUATION = "investment_valuation"
    INVESTMENT_SALE = "investment_sale"


class Direction(Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    NON_CASH = "non_cash"


class EventStatus(Enum):
    SETTLED = "settled"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    UNREALIZED = "unrealized"


class Flexibility(Enum):
    FIXED = "fixed"
    REDUCIBLE = "reducible"
    STOPPABLE = "stoppable"
    REDUCIBLE_OR_STOPPABLE = "reducible_or_stoppable"


class CarrierSourceType(Enum):
    EMPLOYER = "employer"
    BANK = "bank"
    FINANCIAL_SERVICE = "financial_service"
    MERCHANT = "merchant"
    SERVICE_PROVIDER = "service_provider"


class PaymentMethod(Enum):
    FULL_PAYMENT = "full_payment"
    PARTIAL_PAYMENT = "partial_payment"
    INSTALLMENTS = "installments"


class AffordabilityStatus(Enum):
    AFFORDABLE_NOW = "affordable_now"
    AFFORDABLE_WITH_PLAN = "affordable_with_plan"
    AFFORDABLE_LATER = "affordable_later"
    NOT_AFFORDABLE = "not_affordable"


class SpendingChangeType(Enum):
    STOP = "stop"
    REDUCE_TO = "reduce_to"


class EvidenceFactType(Enum):
    RECURRING_AMOUNT_AMENDMENT = "recurring_amount_amendment"
    NEXT_CYCLE_AMOUNT_AMENDMENT = "next_cycle_amount_amendment"
    RECURRENCE_CONFIRMATION = "recurrence_confirmation"
    SETTLEMENT_DATE_REPLACEMENT = "settlement_date_replacement"
    RECURRENCE_STOP = "recurrence_stop"
    RECURRENCE_RESUME = "recurrence_resume"
    RECURRING_EXPENSE_AMENDMENT = "recurring_expense_amendment"
    CONFIRMED_FUTURE_CREDIT = "confirmed_future_credit"
    UNAVAILABLE_CREDIT = "unavailable_credit"
    PENDING_CREDIT = "pending_credit"
    UNREALIZED_VALUE = "unrealized_value"
    SETTLED_ONE_TIME_CREDIT = "settled_one_time_credit"
    INTERNAL_TRANSFER_PAIR = "internal_transfer_pair"
    RECURRING_EXPENSE_NOTICE = "recurring_expense_notice"
    EVENT_AMOUNT = "event_amount"


@dataclass(frozen=True)
class RequestRecord:
    request_id: str
    user_id: str
    request_date: date
    request_type: RequestType
    requested_amount: Decimal
    desired_completion_date: date
    allows_partial_payment: bool
    scope: RequestScope


@dataclass(frozen=True)
class ProfileRecord:
    user_id: str
    home_currency: CurrencyCode
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: frozenset[str]
    expense_categories_to_protect: frozenset[str]
    expense_categories_user_is_willing_to_reduce: frozenset[str]
    expense_categories_user_is_willing_to_stop: frozenset[str]
    payment_methods_user_will_consider: tuple[PaymentMethod, ...]
    max_installment_months: int | None


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    user_id: str
    event_type: EventType
    description: str
    category: str
    direction: Direction
    amount: Decimal | None
    currency: CurrencyCode
    event_date: date
    settlement_date: date | None
    status: EventStatus
    linked_event_id: str | None
    flexibility: Flexibility
    minimum_allowed_amount: Decimal | None


@dataclass(frozen=True)
class ExchangeRateRecord:
    rate_date: date
    from_currency: CurrencyCode
    to_currency: CurrencyCode
    rate: Decimal


@dataclass(frozen=True)
class PaymentOptionRecord:
    payment_option_id: str
    request_id: str
    payment_method: PaymentMethod
    payment_amount: Decimal
    payment_amount_lexeme: str
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: int | None
    financing_fee: Decimal
    total_payable_amount: Decimal
    total_payable_amount_lexeme: str


@dataclass(frozen=True)
class MessageRecord:
    message_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    sent_at: str
    source_type: CarrierSourceType


@dataclass(frozen=True)
class ImageRecord:
    image_id: str
    user_id: str
    request_id: str
    related_event_id: str


@dataclass(frozen=True)
class SourceReference:
    carrier_type: str
    carrier_id: str


@dataclass(frozen=True)
class EvidenceFact:
    fact_id: str
    fact_type: EvidenceFactType
    sources: tuple[SourceReference, ...]
    target_event_id: str | None = None
    target_request_id: str | None = None
    amount: Decimal | None = None
    currency: CurrencyCode | None = None
    effective_date: date | None = None
    settlement_date: date | None = None
    recurrence_duration_months: int | None = None
    notes: str = ""

@dataclass(frozen=True)
class Payment:
    payment_date: date
    amount: Decimal


@dataclass(frozen=True)
class SpendingChange:
    change_type: SpendingChangeType
    event_id: str
    new_amount: Decimal | None = None


@dataclass(frozen=True)
class OutputRow:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: AffordabilityStatus
    recommended_payment_method: PaymentMethod | None
    payment_plan: tuple[Payment, ...]
    earliest_date_for_full_payment: date | None
    spending_changes_needed: tuple[SpendingChange, ...]
    decision_explanation: str


@dataclass(frozen=True)
class RequestCase:
    request: RequestRecord
    profile: ProfileRecord
    events: tuple[EventRecord, ...]
    payment_options: tuple[PaymentOptionRecord, ...]
    messages: tuple[MessageRecord, ...]
    images: tuple[ImageRecord, ...]
    relevant_rates: tuple[ExchangeRateRecord, ...]


def parse_pipe_list(value: str) -> tuple[str, ...]:
    if value == "":
        return ()
    tokens = tuple(value.split("|"))
    if any(token == "" for token in tokens):
        raise ValueError("pipe_list_has_empty_token")
    if len(set(tokens)) != len(tokens):
        raise ValueError("pipe_list_has_duplicate")
    return tokens


def parse_bool(value: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("invalid_boolean")


def parse_date(value: str) -> date:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError("invalid_date")
    return date.fromisoformat(value)


def parse_decimal(value: str) -> Decimal:
    parsed = Decimal(value)
    if not parsed.is_finite():
        raise ValueError("invalid_decimal")
    return parsed
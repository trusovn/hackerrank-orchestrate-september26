"""Strict, eager, fail-fast dataset repository.

Reads every participant-facing CSV exactly once, validates the complete dataset
before exposing any request case, and assembles deterministic ``RequestCase``
objects from in-memory indexes. Performs no financial inference and never
exposes solved sample output columns as product input.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator

from buy_or_wait.domain import (
    CarrierSourceType,
    CurrencyCode,
    Direction,
    EventRecord,
    EventStatus,
    EventType,
    ExchangeRateRecord,
    Flexibility,
    ImageRecord,
    MessageRecord,
    PaymentOptionRecord,
    ProfileRecord,
    RequestCase,
    RequestRecord,
    RequestScope,
    RequestType,
    PaymentMethod,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_pipe_list,
)

_HEADERS = {
    "requests.csv": (
        "request_id",
        "user_id",
        "request_date",
        "request_type",
        "requested_amount",
        "desired_completion_date",
        "allows_partial_payment",
        "request_text",
    ),
    "sample_requests.csv": (
        "request_id",
        "user_id",
        "request_date",
        "request_type",
        "requested_amount",
        "desired_completion_date",
        "allows_partial_payment",
        "request_text",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ),
    "financial_profiles.csv": (
        "user_id",
        "home_currency",
        "current_available_balance",
        "minimum_balance_to_keep",
        "financial_priorities",
        "expense_categories_to_protect",
        "expense_categories_user_is_willing_to_reduce",
        "expense_categories_user_is_willing_to_stop",
        "payment_methods_user_will_consider",
        "max_installment_months",
    ),
    "financial_events.csv": (
        "event_id",
        "user_id",
        "event_type",
        "description",
        "category",
        "direction",
        "amount",
        "currency",
        "event_date",
        "settlement_date",
        "status",
        "linked_event_id",
        "flexibility",
        "minimum_allowed_amount",
    ),
    "exchange_rates.csv": (
        "rate_date",
        "from_currency",
        "to_currency",
        "rate",
    ),
    "request_payment_options.csv": (
        "payment_option_id",
        "request_id",
        "payment_method",
        "payment_amount",
        "number_of_payments",
        "first_payment_date",
        "payment_frequency_days",
        "financing_fee",
        "total_payable_amount",
    ),
    "messages.csv": (
        "message_id",
        "user_id",
        "request_id",
        "related_event_id",
        "sent_at",
        "source_type",
        "message_text",
    ),
    "images.csv": (
        "image_id",
        "user_id",
        "request_id",
        "related_event_id",
    ),
}


class RepositoryValidationError(ValueError):
    """Validation failure with a stable reason code and safe source location.

    The message never contains raw message text, request text, or other
    sensitive carrier content.
    """

    def __init__(
        self,
        reason_code: str,
        source_file: str,
        location: str,
        source_ids: tuple[str, ...] = (),
    ) -> None:
        self.reason_code = reason_code
        self.source_file = source_file
        self.location = location
        self.source_ids = source_ids
        super().__init__(
            f"[{reason_code}] {source_file} at {location}"
            + (f" ids={','.join(source_ids)}" if source_ids else "")
        )


def _fail(
    reason_code: str,
    source_file: str,
    location: str,
    source_ids: tuple[str, ...] = (),
) -> RepositoryValidationError:
    return RepositoryValidationError(reason_code, source_file, location, source_ids)


def _read_rows(path: Path, source_file: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise _fail("empty_file", source_file, "row=1") from None
        if tuple(header) != _HEADERS[source_file]:
            raise _fail("unexpected_header", source_file, "row=1")
        rows = []
        for row_number, raw in enumerate(reader, start=2):
            if len(raw) != len(header):
                raise _fail("wrong_field_count", source_file, f"row={row_number}")
            rows.append(dict(zip(header, raw)))
        return rows


def _require(row: dict[str, str], key: str, source_file: str, row_number: int) -> str:
    value = row[key]
    if value == "":
        raise _fail("missing_required_value", source_file, f"row={row_number} field={key}")
    return value


def _optional(row: dict[str, str], key: str) -> str | None:
    return row[key] if row[key] != "" else None


def _parse_amount(
    value: str | None,
    source_file: str,
    row_number: int,
    field: str,
) -> Decimal:
    if value is None:
        raise _fail("missing_required_value", source_file, f"row={row_number} field={field}")
    try:
        parsed = parse_decimal(value)
    except (InvalidOperation, ValueError):
        raise _fail("invalid_decimal", source_file, f"row={row_number} field={field}") from None
    if parsed < 0:
        raise _fail("negative_amount", source_file, f"row={row_number} field={field}")
    return parsed


def _parse_optional_amount(
    value: str | None,
    source_file: str,
    row_number: int,
    field: str,
) -> Decimal | None:
    if value is None:
        return None
    return _parse_amount(value, source_file, row_number, field)


def _parse_positive_int(
    value: str | None,
    source_file: str,
    row_number: int,
    field: str,
) -> int | None:
    if value is None:
        return None
    try:
        if not value.isdigit() or int(value) <= 0:
            raise ValueError
    except ValueError:
        raise _fail("invalid_positive_integer", source_file, f"row={row_number} field={field}") from None
    return int(value)


def _parse_enum(
    enum_type,
    value: str | None,
    source_file: str,
    row_number: int,
    field: str,
    *,
    required: bool = True,
):
    if value is None:
        if required:
            raise _fail("missing_required_value", source_file, f"row={row_number} field={field}")
        return None
    try:
        return enum_type(value)
    except ValueError:
        raise _fail("invalid_enum_value", source_file, f"row={row_number} field={field}") from None


def _parse_pipe_list(
    value: str, source_file: str, row_number: int, field: str
) -> tuple[str, ...]:
    try:
        tokens = parse_pipe_list(value)
    except ValueError as error:
        reason = str(error) if str(error) in ("pipe_list_has_empty_token", "pipe_list_has_duplicate") else "pipe_list_has_duplicate"
        raise _fail(
            reason, source_file, f"row={row_number} field={field}"
        ) from None
    return tokens


@dataclass(frozen=True)
class _RawRequest:
    record: RequestRecord
    row_number: int


@dataclass(frozen=True)
class _Index:
    requests: dict[str, _RawRequest]
    request_order: dict[RequestScope, tuple[str, ...]]
    profiles: dict[str, ProfileRecord]
    events_by_user: dict[str, tuple[EventRecord, ...]]
    options_by_request: dict[str, tuple[PaymentOptionRecord, ...]]
    messages_by_user: dict[str, tuple[MessageRecord, ...]]
    images_by_user: dict[str, tuple[ImageRecord, ...]]
    rates_by_user: dict[str, tuple[ExchangeRateRecord, ...]]


class DatasetRepository:
    """Eagerly validated, read-only view over the participant dataset."""

    def __init__(self, index: _Index) -> None:
        self._index = index

    @classmethod
    def from_directory(cls, dataset_root: Path) -> "DatasetRepository":
        dataset_root = Path(dataset_root)

        request_rows = _read_rows(dataset_root / "requests.csv", "requests.csv")
        sample_rows = _read_rows(dataset_root / "sample_requests.csv", "sample_requests.csv")
        profile_rows = _read_rows(dataset_root / "financial_profiles.csv", "financial_profiles.csv")
        event_rows = _read_rows(dataset_root / "financial_events.csv", "financial_events.csv")
        rate_rows = _read_rows(dataset_root / "exchange_rates.csv", "exchange_rates.csv")
        option_rows = _read_rows(
            dataset_root / "request_payment_options.csv", "request_payment_options.csv"
        )
        message_rows = _read_rows(dataset_root / "messages.csv", "messages.csv")
        image_rows = _read_rows(dataset_root / "images.csv", "images.csv")

        profiles = cls._parse_profiles(profile_rows)
        events = cls._parse_events(event_rows)
        rates = cls._parse_rates(rate_rows)

        requests: dict[str, _RawRequest] = {}
        scope_order: dict[RequestScope, list[str]] = {
            RequestScope.EVALUATION: [],
            RequestScope.SAMPLE: [],
        }
        for row_number, row in enumerate(request_rows, start=2):
            record = cls._parse_request(row, row_number, RequestScope.EVALUATION)
            if record.request_id in requests:
                raise _fail(
                    "duplicate_request_id",
                    "requests.csv",
                    f"row={row_number}",
                    (record.request_id,),
                )
            if record.user_id not in profiles:
                raise _fail(
                    "unknown_profile",
                    "requests.csv",
                    f"row={row_number}",
                    (record.request_id, record.user_id),
                )
            requests[record.request_id] = _RawRequest(record, row_number)
            scope_order[RequestScope.EVALUATION].append(record.request_id)

        sample_input_fields = _HEADERS["sample_requests.csv"][:8]
        for row_number, full_row in enumerate(sample_rows, start=2):
            row = {field: full_row[field] for field in sample_input_fields}
            record = cls._parse_request(row, row_number, RequestScope.SAMPLE)
            if record.request_id in requests:
                raise _fail(
                    "duplicate_request_id",
                    "sample_requests.csv",
                    f"row={row_number}",
                    (record.request_id,),
                )
            if record.user_id not in profiles:
                raise _fail(
                    "unknown_profile",
                    "sample_requests.csv",
                    f"row={row_number}",
                    (record.request_id, record.user_id),
                )
            requests[record.request_id] = _RawRequest(record, row_number)
            scope_order[RequestScope.SAMPLE].append(record.request_id)

        request_users = {record.user_id for record in (r.record for r in requests.values())}
        for user_id in profiles:
            matching = [r.record for r in requests.values() if r.record.user_id == user_id]
            if len(matching) > 1:
                raise _fail(
                    "multiple_requests_per_user",
                    "requests.csv",
                    f"user={user_id}",
                    tuple(sorted(r.request_id for r in matching)),
                )

        cls._validate_options(option_rows, requests)
        cls._validate_carriers(message_rows, image_rows, requests, events)

        options_by_request: dict[str, list[PaymentOptionRecord]] = {}
        for row_number, row in enumerate(option_rows, start=2):
            request_id = _require(row, "request_id", "request_payment_options.csv", row_number)
            options_by_request.setdefault(request_id, []).append(
                cls._parse_option(row, row_number)
            )

        events_by_user: dict[str, list[EventRecord]] = {}
        for event in events:
            events_by_user.setdefault(event.user_id, []).append(event)

        messages_by_user: dict[str, list[MessageRecord]] = {}
        for row_number, row in enumerate(message_rows, start=2):
            record = cls._parse_message(row, row_number)
            messages_by_user.setdefault(record.user_id, []).append(record)

        images_by_user: dict[str, list[ImageRecord]] = {}
        for row_number, row in enumerate(image_rows, start=2):
            record = cls._parse_image(row, row_number)
            images_by_user.setdefault(record.user_id, []).append(record)

        profile_currencies = {user: p.home_currency for user, p in profiles.items()}
        user_currencies: dict[str, set[CurrencyCode]] = {}
        for user_id, event_list in events_by_user.items():
            for event in event_list:
                user_currencies.setdefault(user_id, set()).add(event.currency)
                user_currencies.setdefault(user_id, set()).add(profile_currencies[user_id])

        rates_by_user: dict[str, list[ExchangeRateRecord]] = {}
        for rate in rates:
            for user_id, currencies in user_currencies.items():
                if rate.from_currency in currencies and rate.to_currency in currencies:
                    rates_by_user.setdefault(user_id, []).append(rate)

        index = _Index(
            requests=requests,
            request_order={
                scope: tuple(ids) for scope, ids in scope_order.items()
            },
            profiles=profiles,
            events_by_user={user: tuple(items) for user, items in events_by_user.items()},
            options_by_request={
                request_id: tuple(items) for request_id, items in options_by_request.items()
            },
            messages_by_user={user: tuple(items) for user, items in messages_by_user.items()},
            images_by_user={user: tuple(items) for user, items in images_by_user.items()},
            rates_by_user={user: tuple(items) for user, items in rates_by_user.items()},
        )
        return cls(index)

    @staticmethod
    def _parse_request(
        row: dict[str, str],
        row_number: int,
        scope: RequestScope,
    ) -> RequestRecord:
        source_file = "requests.csv" if scope is RequestScope.EVALUATION else "sample_requests.csv"
        request_id = _require(row, "request_id", source_file, row_number)
        user_id = _require(row, "user_id", source_file, row_number)
        request_date = DatasetRepository._parse_date_field(row, "request_date", source_file, row_number)
        completion = DatasetRepository._parse_date_field(row, "desired_completion_date", source_file, row_number)
        if completion < request_date:
            raise _fail(
                "completion_before_request_date",
                source_file,
                f"row={row_number}",
                (request_id,),
            )
        return RequestRecord(
            request_id=request_id,
            user_id=user_id,
            request_date=request_date,
            request_type=_parse_enum(
                RequestType, _require(row, "request_type", source_file, row_number), source_file, row_number, "request_type"
            ),
            requested_amount=_parse_amount(
                _require(row, "requested_amount", source_file, row_number),
                source_file,
                row_number,
                "requested_amount",
            ),
            desired_completion_date=completion,
            allows_partial_payment=DatasetRepository._parse_bool_field(row, "allows_partial_payment", source_file, row_number),
            scope=scope,
        )

    @staticmethod
    def _parse_date_field(
        row: dict[str, str], field: str, source_file: str, row_number: int
    ) -> date:
        try:
            return parse_date(_require(row, field, source_file, row_number))
        except ValueError as error:
            if str(error) == "invalid_date":
                raise _fail("invalid_date", source_file, f"row={row_number} field={field}") from None
            raise _fail("invalid_date", source_file, f"row={row_number} field={field}") from None

    @staticmethod
    def _parse_bool_field(
        row: dict[str, str], field: str, source_file: str, row_number: int
    ) -> bool:
        try:
            return parse_bool(_require(row, field, source_file, row_number))
        except ValueError:
            raise _fail("invalid_boolean", source_file, f"row={row_number} field={field}") from None

    @staticmethod
    def _parse_profiles(rows: list[dict[str, str]]) -> dict[str, ProfileRecord]:
        source_file = "financial_profiles.csv"
        profiles: dict[str, ProfileRecord] = {}
        for row_number, row in enumerate(rows, start=2):
            user_id = _require(row, "user_id", source_file, row_number)
            if user_id in profiles:
                raise _fail("duplicate_user_id", source_file, f"row={row_number}", (user_id,))
            methods = DatasetRepository._parse_enum_list(
                PaymentMethod,
                _parse_pipe_list(
                    _require(row, "payment_methods_user_will_consider", source_file, row_number),
                    source_file,
                    row_number,
                    "payment_methods_user_will_consider",
                ),
                source_file,
                row_number,
                "payment_methods_user_will_consider",
            )
            considers_installments = PaymentMethod.INSTALLMENTS in methods
            cap = _parse_positive_int(
                _optional(row, "max_installment_months"), source_file, row_number, "max_installment_months"
            )
            if considers_installments and cap is None:
                raise _fail(
                    "missing_installment_cap",
                    source_file,
                    f"row={row_number}",
                    (user_id,),
                )
            if not considers_installments and cap is not None:
                raise _fail(
                    "unexpected_installment_cap",
                    source_file,
                    f"row={row_number}",
                    (user_id,),
                )
            protected = frozenset(
                _parse_pipe_list(
                    _optional(row, "expense_categories_to_protect") or "",
                    source_file,
                    row_number,
                    "expense_categories_to_protect",
                )
            )
            reducible = frozenset(
                _parse_pipe_list(
                    _optional(row, "expense_categories_user_is_willing_to_reduce") or "",
                    source_file,
                    row_number,
                    "expense_categories_user_is_willing_to_reduce",
                )
            )
            stoppable = frozenset(
                _parse_pipe_list(
                    _optional(row, "expense_categories_user_is_willing_to_stop") or "",
                    source_file,
                    row_number,
                    "expense_categories_user_is_willing_to_stop",
                )
            )
            if protected & (reducible | stoppable):
                raise _fail(
                    "protected_category_is_reducible",
                    source_file,
                    f"row={row_number}",
                    (user_id,),
                )
            profiles[user_id] = ProfileRecord(
                user_id=user_id,
                home_currency=_parse_enum(
                    CurrencyCode, _require(row, "home_currency", source_file, row_number), source_file, row_number, "home_currency"
                ),
                current_available_balance=_parse_amount(
                    _require(row, "current_available_balance", source_file, row_number),
                    source_file,
                    row_number,
                    "current_available_balance",
                ),
                minimum_balance_to_keep=_parse_amount(
                    _require(row, "minimum_balance_to_keep", source_file, row_number),
                    source_file,
                    row_number,
                    "minimum_balance_to_keep",
                ),
                financial_priorities=frozenset(
                    _parse_pipe_list(
                        _optional(row, "financial_priorities") or "",
                        source_file,
                        row_number,
                        "financial_priorities",
                    )
                ),
                expense_categories_to_protect=protected,
                expense_categories_user_is_willing_to_reduce=reducible,
                expense_categories_user_is_willing_to_stop=stoppable,
                payment_methods_user_will_consider=tuple(methods),
                max_installment_months=cap,
            )
        return profiles

    @staticmethod
    def _parse_enum_list(enum_type, tokens, source_file, row_number, field):
        try:
            return [enum_type(token) for token in tokens]
        except ValueError:
            raise _fail("invalid_enum_value", source_file, f"row={row_number} field={field}") from None

    @staticmethod
    def _parse_events(rows: list[dict[str, str]]) -> tuple[EventRecord, ...]:
        source_file = "financial_events.csv"
        events: dict[str, EventRecord] = {}
        records: list[EventRecord] = []
        for row_number, row in enumerate(rows, start=2):
            event_id = _require(row, "event_id", source_file, row_number)
            if event_id in events:
                raise _fail("duplicate_event_id", source_file, f"row={row_number}", (event_id,))
            user_id = _require(row, "user_id", source_file, row_number)
            flexibility = _parse_enum(
                Flexibility, _require(row, "flexibility", source_file, row_number), source_file, row_number, "flexibility"
            )
            minimum_allowed = _parse_optional_amount(
                _optional(row, "minimum_allowed_amount"), source_file, row_number, "minimum_allowed_amount"
            )
            if flexibility in (Flexibility.REDUCIBLE, Flexibility.REDUCIBLE_OR_STOPPABLE):
                if minimum_allowed is None:
                    raise _fail(
                        "missing_minimum_allowed_amount", source_file, f"row={row_number}", (event_id,)
                    )
            elif minimum_allowed is not None:
                raise _fail(
                    "unexpected_minimum_allowed_amount", source_file, f"row={row_number}", (event_id,)
                )
            event_date = DatasetRepository._parse_date_field(row, "event_date", source_file, row_number)
            settlement_date = DatasetRepository._parse_optional_date(row, "settlement_date", source_file, row_number)
            amount = _parse_optional_amount(_optional(row, "amount"), source_file, row_number, "amount")
            status = _parse_enum(
                EventStatus, _require(row, "status", source_file, row_number), source_file, row_number, "status"
            )
            if settlement_date is None and status is not EventStatus.UNREALIZED:
                raise _fail(
                    "missing_settlement_date",
                    source_file,
                    f"row={row_number}",
                    (event_id,),
                )
            record = EventRecord(
                event_id=event_id,
                user_id=user_id,
                event_type=_parse_enum(
                    EventType, _require(row, "event_type", source_file, row_number), source_file, row_number, "event_type"
                ),
                description=_require(row, "description", source_file, row_number),
                category=_require(row, "category", source_file, row_number),
                direction=_parse_enum(
                    Direction, _require(row, "direction", source_file, row_number), source_file, row_number, "direction"
                ),
                amount=amount,
                currency=_parse_enum(
                    CurrencyCode, _require(row, "currency", source_file, row_number), source_file, row_number, "currency"
                ),
                event_date=event_date,
                settlement_date=settlement_date,
                status=status,
                linked_event_id=_optional(row, "linked_event_id"),
                flexibility=flexibility,
                minimum_allowed_amount=minimum_allowed,
            )
            if flexibility in (Flexibility.REDUCIBLE, Flexibility.REDUCIBLE_OR_STOPPABLE):
                if record.amount is None or minimum_allowed > record.amount:
                    raise _fail(
                        "minimum_allowed_above_amount",
                        source_file,
                        f"row={row_number}",
                        (event_id,),
                    )
            events[event_id] = record
            records.append(record)

        for record in records:
            linked = record.linked_event_id
            if linked is None:
                continue
            if linked == record.event_id:
                raise _fail(
                    "self_linked_event",
                    source_file,
                    f"event={record.event_id}",
                    (record.event_id,),
                )
            target = events.get(linked)
            if target is None or target.user_id != record.user_id:
                raise _fail(
                    "unknown_linked_event",
                    source_file,
                    f"event={record.event_id}",
                    (record.event_id, linked),
                )
        return tuple(records)

    @staticmethod
    def _parse_optional_date(
        row: dict[str, str], field: str, source_file: str, row_number: int
    ) -> date | None:
        value = _optional(row, field)
        if value is None:
            return None
        try:
            return parse_date(value)
        except ValueError:
            raise _fail("invalid_date", source_file, f"row={row_number} field={field}") from None

    @staticmethod
    def _parse_rates(rows: list[dict[str, str]]) -> tuple[ExchangeRateRecord, ...]:
        source_file = "exchange_rates.csv"
        seen: set[tuple[date, CurrencyCode, CurrencyCode]] = set()
        records: list[ExchangeRateRecord] = []
        for row_number, row in enumerate(rows, start=2):
            rate_date = DatasetRepository._parse_date_field(row, "rate_date", source_file, row_number)
            from_currency = _parse_enum(
                CurrencyCode, _require(row, "from_currency", source_file, row_number), source_file, row_number, "from_currency"
            )
            to_currency = _parse_enum(
                CurrencyCode, _require(row, "to_currency", source_file, row_number), source_file, row_number, "to_currency"
            )
            key = (rate_date, from_currency, to_currency)
            if key in seen:
                raise _fail(
                    "duplicate_rate_key",
                    source_file,
                    f"row={row_number}",
                    (f"{rate_date.isoformat()}:{from_currency.value}->{to_currency.value}",),
                )
            seen.add(key)
            records.append(
                ExchangeRateRecord(
                    rate_date=rate_date,
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=_parse_amount(
                        _require(row, "rate", source_file, row_number),
                        source_file,
                        row_number,
                        "rate",
                    ),
                )
            )
        return tuple(records)

    @staticmethod
    def _parse_option(row: dict[str, str], row_number: int) -> PaymentOptionRecord:
        source_file = "request_payment_options.csv"
        method = _parse_enum(
            PaymentMethod,
            _require(row, "payment_method", source_file, row_number),
            source_file,
            row_number,
            "payment_method",
        )
        payment_lexeme = _require(row, "payment_amount", source_file, row_number)
        payment_amount = _parse_amount(payment_lexeme, source_file, row_number, "payment_amount")
        count = _parse_positive_int(
            _require(row, "number_of_payments", source_file, row_number),
            source_file,
            row_number,
            "number_of_payments",
        )
        total_lexeme = _require(row, "total_payable_amount", source_file, row_number)
        total = _parse_amount(total_lexeme, source_file, row_number, "total_payable_amount")
        frequency = _parse_positive_int(
            _optional(row, "payment_frequency_days"), source_file, row_number, "payment_frequency_days"
        )
        if method is PaymentMethod.FULL_PAYMENT:
            if count != 1:
                raise _fail(
                    "invalid_full_payment_shape", source_file, f"row={row_number}"
                )
            if frequency is not None:
                raise _fail(
                    "unexpected_frequency_full_payment", source_file, f"row={row_number}"
                )
            fee = _parse_amount(_require(row, "financing_fee", source_file, row_number), source_file, row_number, "financing_fee")
            if fee != 0:
                raise _fail(
                    "nonzero_fee_full_payment", source_file, f"row={row_number}"
                )
        else:
            if count <= 1:
                raise _fail(
                    "invalid_installment_shape", source_file, f"row={row_number}"
                )
            if frequency is None:
                raise _fail(
                    "missing_frequency_installments", source_file, f"row={row_number}"
                )
            fee = _parse_amount(_require(row, "financing_fee", source_file, row_number), source_file, row_number, "financing_fee")
        if payment_amount * count != total:
            raise _fail(
                "option_total_mismatch",
                source_file,
                f"row={row_number}",
            )
        return PaymentOptionRecord(
            payment_option_id=_require(row, "payment_option_id", source_file, row_number),
            request_id=_require(row, "request_id", source_file, row_number),
            payment_method=method,
            payment_amount=payment_amount,
            payment_amount_lexeme=payment_lexeme,
            number_of_payments=count,
            first_payment_date=DatasetRepository._parse_date_field(row, "first_payment_date", source_file, row_number),
            payment_frequency_days=frequency,
            financing_fee=fee,
            total_payable_amount=total,
            total_payable_amount_lexeme=total_lexeme,
        )

    @staticmethod
    def _validate_options(
        rows: list[dict[str, str]], requests: dict[str, _RawRequest]
    ) -> None:
        source_file = "request_payment_options.csv"
        option_ids: set[str] = set()
        request_amounts = {
            request_id: raw.record.requested_amount
            for request_id, raw in requests.items()
        }
        request_dates = {
            request_id: raw.record.request_date for request_id, raw in requests.items()
        }
        full_counts: dict[str, int] = {}
        for row_number, row in enumerate(rows, start=2):
            option_id = _require(row, "payment_option_id", source_file, row_number)
            if option_id in option_ids:
                raise _fail("duplicate_payment_option_id", source_file, f"row={row_number}", (option_id,))
            option_ids.add(option_id)
            request_id = _require(row, "request_id", source_file, row_number)
            if request_id not in requests:
                raise _fail(
                    "option_unknown_request", source_file, f"row={row_number}", (option_id, request_id)
                )
            method = _parse_enum(
                PaymentMethod,
                _require(row, "payment_method", source_file, row_number),
                source_file,
                row_number,
                "payment_method",
            )
            if method is PaymentMethod.FULL_PAYMENT:
                full_counts[request_id] = full_counts.get(request_id, 0) + 1
                payment_lexeme = _require(row, "payment_amount", source_file, row_number)
                payment_amount = _parse_amount(payment_lexeme, source_file, row_number, "payment_amount")
                total = _parse_amount(
                    _require(row, "total_payable_amount", source_file, row_number),
                    source_file,
                    row_number,
                    "total_payable_amount",
                )
                if payment_amount != request_amounts[request_id]:
                    raise _fail(
                        "full_payment_amount_mismatch",
                        source_file,
                        f"row={row_number}",
                        (option_id,),
                    )
                if total != request_amounts[request_id]:
                    raise _fail(
                        "full_payment_total_mismatch",
                        source_file,
                        f"row={row_number}",
                        (option_id,),
                    )
                first_date = DatasetRepository._parse_date_field(row, "first_payment_date", source_file, row_number)
                if first_date != request_dates[request_id]:
                    raise _fail(
                        "full_payment_first_date_mismatch",
                        source_file,
                        f"row={row_number}",
                        (option_id,),
                    )
        for request_id in requests:
            if full_counts.get(request_id, 0) != 1:
                raise _fail(
                    "missing_full_payment_option",
                    source_file,
                    f"request={request_id}",
                    (request_id,),
                )

    @staticmethod
    def _validate_carriers(
        message_rows: list[dict[str, str]],
        image_rows: list[dict[str, str]],
        requests: dict[str, _RawRequest],
        events: tuple[EventRecord, ...],
    ) -> None:
        event_users = {event.event_id: event.user_id for event in events}
        request_users = {request_id: raw.record.user_id for request_id, raw in requests.items()}
        message_ids: set[str] = set()

        for row_number, row in enumerate(message_rows, start=2):
            source_file = "messages.csv"
            message_id = _require(row, "message_id", source_file, row_number)
            if message_id in message_ids:
                raise _fail("duplicate_message_id", source_file, f"row={row_number}", (message_id,))
            message_ids.add(message_id)
            user_id = _require(row, "user_id", source_file, row_number)
            _parse_enum(
                CarrierSourceType,
                _require(row, "source_type", source_file, row_number),
                source_file,
                row_number,
                "source_type",
            )
            request_link = _optional(row, "request_id")
            if request_link is not None:
                if request_link not in request_users:
                    raise _fail(
                        "unknown_request_link", source_file, f"row={row_number}", (message_id, request_link)
                    )
                if request_users[request_link] != user_id:
                    raise _fail(
                        "wrong_user_request_link", source_file, f"row={row_number}", (message_id, request_link)
                    )
            event_link = _optional(row, "related_event_id")
            if event_link is not None:
                if event_link not in event_users:
                    raise _fail(
                        "unknown_event_link", source_file, f"row={row_number}", (message_id, event_link)
                    )
                if event_users[event_link] != user_id:
                    raise _fail(
                        "wrong_user_event_link", source_file, f"row={row_number}", (message_id, event_link)
                    )

        blank_amount_events = {
            event.event_id: event.user_id
            for event in events
            if event.amount is None
        }
        image_links: dict[str, list[str]] = {}
        image_ids: set[str] = set()
        for row_number, row in enumerate(image_rows, start=2):
            source_file = "images.csv"
            image_id = _require(row, "image_id", source_file, row_number)
            if image_id in image_ids:
                raise _fail("duplicate_image_id", source_file, f"row={row_number}", (image_id,))
            image_ids.add(image_id)
            user_id = _require(row, "user_id", source_file, row_number)
            request_link = _require(row, "request_id", source_file, row_number)
            if request_link not in request_users:
                raise _fail(
                    "unknown_request_link", source_file, f"row={row_number}", (image_id, request_link)
                )
            if request_users[request_link] != user_id:
                raise _fail(
                    "wrong_user_request_link", source_file, f"row={row_number}", (image_id, request_link)
                )
            event_link = _require(row, "related_event_id", source_file, row_number)
            if event_link not in event_users:
                raise _fail(
                    "unknown_event_link", source_file, f"row={row_number}", (image_id, event_link)
                )
            if event_users[event_link] != user_id:
                raise _fail(
                    "wrong_user_event_link", source_file, f"row={row_number}", (image_id, event_link)
                )
            if event_link not in blank_amount_events:
                raise _fail(
                    "image_links_to_non_blank_event",
                    source_file,
                    f"row={row_number}",
                    (image_id, event_link),
                )
            image_links.setdefault(event_link, []).append(image_id)

        for event_id, images in image_links.items():
            if len(images) > 1:
                raise _fail(
                    "multiple_images_for_blank_event",
                    source_file,
                    f"event={event_id}",
                    (event_id, *images),
                )
        for event_id in blank_amount_events:
            if event_id not in image_links:
                raise _fail(
                    "blank_event_without_image",
                    "financial_events.csv",
                    f"event={event_id}",
                    (event_id,),
                )

    @staticmethod
    def _parse_message(row: dict[str, str], row_number: int) -> MessageRecord:
        source_file = "messages.csv"
        return MessageRecord(
            message_id=_require(row, "message_id", source_file, row_number),
            user_id=_require(row, "user_id", source_file, row_number),
            request_id=_optional(row, "request_id"),
            related_event_id=_optional(row, "related_event_id"),
            sent_at=_require(row, "sent_at", source_file, row_number),
            source_type=_parse_enum(
                CarrierSourceType,
                _require(row, "source_type", source_file, row_number),
                source_file,
                row_number,
                "source_type",
            ),
        )

    @staticmethod
    def _parse_image(row: dict[str, str], row_number: int) -> ImageRecord:
        source_file = "images.csv"
        return ImageRecord(
            image_id=_require(row, "image_id", source_file, row_number),
            user_id=_require(row, "user_id", source_file, row_number),
            request_id=_require(row, "request_id", source_file, row_number),
            related_event_id=_require(row, "related_event_id", source_file, row_number),
        )

    def load_request_case(self, request_id: str) -> RequestCase:
        raw = self._index.requests.get(request_id)
        if raw is None:
            raise _fail("unknown_request_id", "requests.csv", f"request={request_id}", (request_id,))
        record = raw.record
        user_id = record.user_id

        carriers = tuple(
            message
            for message in self._index.messages_by_user.get(user_id, ())
            if message.request_id is None or message.request_id == request_id
        )
        images = tuple(
            image
            for image in self._index.images_by_user.get(user_id, ())
            if image.request_id == request_id
        )

        return RequestCase(
            request=record,
            profile=self._index.profiles[user_id],
            events=self._index.events_by_user.get(user_id, ()),
            payment_options=self._index.options_by_request.get(request_id, ()),
            messages=carriers,
            images=images,
            relevant_rates=self._index.rates_by_user.get(user_id, ()),
        )

    def iter_request_cases(
        self, scope: RequestScope = RequestScope.EVALUATION
    ) -> Iterator[RequestCase]:
        for request_id in self._index.request_order[scope]:
            yield self.load_request_case(request_id)
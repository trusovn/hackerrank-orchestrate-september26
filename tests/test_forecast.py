"""Focused tests for the WP-05 baseline forecast boundary.

Fail-first suite for ``buy_or_wait.forecast``. Small immutable synthetic
``RequestCase``/``EvidenceResolution``/``EventNormalization`` builders keep
every decisive amount, date, ID, and reason code visible in each test.
Component cases load accepted participant-facing sample cases through
``DatasetRepository`` and forecast through the public API with explicit
expected values written independently from the implementation.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from buy_or_wait.domain import (  # noqa: E402
    CarrierSourceType,
    CurrencyCode,
    Direction,
    EventRecord,
    EventStatus,
    EventType,
    ExchangeRateRecord,
    EvidenceFactType,
    Flexibility,
    ImageRecord,
    MessageRecord,
    PaymentMethod,
    ProfileRecord,
    RequestCase,
    RequestRecord,
    RequestScope,
    RequestType,
    SourceReference,
)
from buy_or_wait.evidence import (  # noqa: E402
    EvidenceDiagnostic,
    EvidenceFact,
    EvidenceResolution,
)
from buy_or_wait.events import (  # noqa: E402
    EventNormalization,
    NormalizedCashEffect,
    NormalizedCashRecord,
    NormalizedReserve,
    normalize_case_events,
)
from buy_or_wait.repository import DatasetRepository  # noqa: E402

from buy_or_wait.forecast import (  # noqa: E402
    DEFAULT_FORECAST_POLICY,
    ForecastBuildError,
    ForecastPolicy,
    HorizonEndpoint,
    IncomeContinuation,
    RecurrenceTiming,
    UnknownSameDayOrder,
    VariableSpending,
    build_baseline_forecast,
)


def _d(value: str) -> date:
    return date.fromisoformat(value)


def _dec(value: str) -> Decimal:
    return Decimal(value)


def _request(
    request_id: str = "request_T",
    user_id: str = "user_T",
    request_date: str = "2026-01-10",
) -> RequestRecord:
    return RequestRecord(
        request_id=request_id,
        user_id=user_id,
        request_date=_d(request_date),
        request_type=RequestType.PURCHASE,
        requested_amount=_dec("100"),
        desired_completion_date=_d("2026-03-01"),
        allows_partial_payment=True,
        scope=RequestScope.SAMPLE,
    )


def _profile(
    user_id: str = "user_T",
    home_currency: CurrencyCode = CurrencyCode.ZAR,
    balance: str = "1000",
    minimum: str = "100",
) -> ProfileRecord:
    return ProfileRecord(
        user_id=user_id,
        home_currency=home_currency,
        current_available_balance=_dec(balance),
        minimum_balance_to_keep=_dec(minimum),
        financial_priorities=frozenset(),
        expense_categories_to_protect=frozenset(),
        expense_categories_user_is_willing_to_reduce=frozenset(),
        expense_categories_user_is_willing_to_stop=frozenset(),
        payment_methods_user_will_consider=(PaymentMethod.FULL_PAYMENT,),
        max_installment_months=None,
    )


def _event(
    event_id: str,
    event_type: EventType = EventType.EXPENSE,
    category: str = "utilities",
    direction: Direction = Direction.DEBIT,
    amount: Decimal | None = _dec("100"),
    currency: CurrencyCode = CurrencyCode.ZAR,
    event_date: str = "2025-12-06",
    settlement_date: str | None = "2025-12-06",
    status: EventStatus = EventStatus.SETTLED,
    description: str | None = None,
    flexibility: Flexibility = Flexibility.FIXED,
    minimum_allowed_amount: Decimal | None = None,
    user_id: str = "user_T",
) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        user_id=user_id,
        event_type=event_type,
        description=description or f"{category} {event_type.value}",
        category=category,
        direction=direction,
        amount=amount,
        currency=currency,
        event_date=_d(event_date),
        settlement_date=_d(settlement_date) if settlement_date else None,
        status=status,
        linked_event_id=None,
        flexibility=flexibility,
        minimum_allowed_amount=minimum_allowed_amount,
    )


def _message(message_id: str, user_id: str = "user_T") -> MessageRecord:
    return MessageRecord(
        message_id=message_id,
        user_id=user_id,
        request_id=None,
        related_event_id=None,
        sent_at="2026-01-05T09:00:00Z",
        source_type=CarrierSourceType.EMPLOYER,
    )


def _image(
    image_id: str,
    user_id: str = "user_T",
    request_id: str = "request_T",
) -> ImageRecord:
    return ImageRecord(
        image_id=image_id,
        user_id=user_id,
        request_id=request_id,
        related_event_id="event_T",
    )


def _fact(
    fact_id: str,
    fact_type: EvidenceFactType,
    target_event_id: str | None = None,
    amount: Decimal | None = None,
    currency: CurrencyCode | None = None,
    effective_date: date | None = None,
    settlement_date: date | None = None,
    sources: tuple[SourceReference, ...] = (
        SourceReference("message", "message_11"),
    ),
) -> EvidenceFact:
    return EvidenceFact(
        fact_id=fact_id,
        fact_type=fact_type,
        sources=sources,
        target_event_id=target_event_id,
        amount=amount,
        currency=currency,
        effective_date=effective_date,
        settlement_date=settlement_date,
    )


def _resolution(
    facts: tuple[EvidenceFact, ...] = (),
    diagnostics: tuple[EvidenceDiagnostic, ...] = (),
    blocks_downstream: bool = False,
) -> EvidenceResolution:
    return EvidenceResolution(
        facts=facts,
        diagnostics=diagnostics,
        blocks_downstream=blocks_downstream,
    )


def _rate(
    rate_date: str,
    from_currency: CurrencyCode,
    to_currency: CurrencyCode,
    rate: str,
) -> ExchangeRateRecord:
    return ExchangeRateRecord(
        rate_date=_d(rate_date),
        from_currency=from_currency,
        to_currency=to_currency,
        rate=_dec(rate),
    )


def _case(
    *,
    events: tuple[EventRecord, ...] = (),
    messages: tuple[MessageRecord, ...] = (),
    images: tuple[ImageRecord, ...] = (),
    rates: tuple[ExchangeRateRecord, ...] = (),
    request: RequestRecord | None = None,
    profile: ProfileRecord | None = None,
) -> RequestCase:
    return RequestCase(
        request=request or _request(),
        profile=profile or _profile(),
        events=events,
        payment_options=(),
        messages=messages,
        images=images,
        relevant_rates=rates,
    )


def _norm_record(
    event: EventRecord,
    record_id: str | None = None,
    amount_home: Decimal | None = None,
) -> NormalizedCashRecord:
    return NormalizedCashRecord(
        record_id=record_id or f"event:{event.event_id}",
        direction=event.direction,
        amount_home=amount_home if amount_home is not None else event.amount,
        home_currency=event.currency,
        source_currency=event.currency,
        source_amount=event.amount,
        settlement_date=event.settlement_date,
        source_event_ids=(event.event_id,),
        source_fact_ids=(),
        category=event.category,
        event_type=event.event_type,
        status=event.status,
        flexibility=event.flexibility,
        minimum_allowed_amount=event.minimum_allowed_amount,
    )


def _norm_effect(
    event: EventRecord,
    effect_date: str,
    amount_home: Decimal | None = None,
    record_id: str | None = None,
) -> NormalizedCashEffect:
    return NormalizedCashEffect(
        record_id=record_id or f"event:{event.event_id}",
        direction=event.direction,
        amount_home=amount_home if amount_home is not None else event.amount,
        home_currency=event.currency,
        source_currency=event.currency,
        source_amount=event.amount,
        effect_date=_d(effect_date),
        source_event_ids=(event.event_id,),
        source_fact_ids=(),
        category=event.category,
        event_type=event.event_type,
        status=event.status,
        flexibility=event.flexibility,
        minimum_allowed_amount=event.minimum_allowed_amount,
    )


def _norm_reserve(
    event: EventRecord,
    reserved_on: str,
    settlement_date: str | None = None,
) -> NormalizedReserve:
    return NormalizedReserve(
        record_id=f"event:{event.event_id}",
        direction=event.direction,
        amount_home=event.amount,
        home_currency=event.currency,
        source_currency=event.currency,
        source_amount=event.amount,
        reserved_on=_d(reserved_on),
        settlement_date=_d(settlement_date) if settlement_date else None,
        source_event_ids=(event.event_id,),
        source_fact_ids=(),
        category=event.category,
        event_type=event.event_type,
        status=event.status,
        flexibility=event.flexibility,
        minimum_allowed_amount=event.minimum_allowed_amount,
    )


def _empty_normalization(
    hist: tuple[NormalizedCashRecord, ...] = (),
    reserves: tuple[NormalizedReserve, ...] = (),
    effects: tuple[NormalizedCashEffect, ...] = (),
    blocks: bool = False,
) -> EventNormalization:
    return EventNormalization(
        historical_cash=hist,
        opening_reserves=reserves,
        dated_cash_effects=effects,
        decisions=(),
        blocks_downstream=blocks,
    )


def _forecast(case, evidence, normalization=None, policy=None):
    if normalization is None:
        normalization = normalize_case_events(case, evidence)
    return build_baseline_forecast(
        case, evidence, normalization, policy or DEFAULT_FORECAST_POLICY
    )


def _occurrences_by_date(result):
    return {occ.date: occ for occ in result.projected_occurrences}


def _occurrence_dates(result, family_id=None):
    return sorted(
        occ.date
        for occ in result.projected_occurrences
        if family_id is None or occ.family_id == family_id
    )


def _diag_codes(result):
    return {diagnostic.reason_code for diagnostic in result.diagnostics}


class PolicySurfaceTests(unittest.TestCase):
    def test_default_policy_values_are_explicit(self) -> None:
        self.assertIs(DEFAULT_FORECAST_POLICY.recurrence_timing, RecurrenceTiming.STRICT)
        self.assertIs(
            DEFAULT_FORECAST_POLICY.income_continuation,
            IncomeContinuation.I0_EXPLICIT_ONGOING,
        )
        self.assertIs(
            DEFAULT_FORECAST_POLICY.variable_spending,
            VariableSpending.V0_MAX_COMPLETE_MONTH,
        )
        self.assertIs(
            DEFAULT_FORECAST_POLICY.horizon_endpoint, HorizonEndpoint.DAY_90_INCLUSIVE
        )
        self.assertIs(
            DEFAULT_FORECAST_POLICY.same_day_order,
            UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        with self.assertRaises(Exception):
            ForecastPolicy(
                recurrence_timing=RecurrenceTiming.STRICT,
                income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
                variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
                horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
                same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
                extra="not_allowed",
            )


class BoundaryValidationTests(unittest.TestCase):
    """Phase 1: fail closed on an unrepresentable input contract."""

    def test_invalid_evidence_type_fails(self) -> None:
        case = _case()
        with self.assertRaises(ForecastBuildError) as caught:
            build_baseline_forecast(
                case, "not_evidence", _empty_normalization()
            )
        self.assertEqual(caught.exception.reason_code, "invalid_evidence")

    def test_invalid_normalization_type_fails(self) -> None:
        case = _case()
        with self.assertRaises(ForecastBuildError) as caught:
            build_baseline_forecast(
                case, _resolution(), "not_normalization"
            )
        self.assertEqual(caught.exception.reason_code, "invalid_normalization")

    def test_request_and_profile_user_ids_must_match(self) -> None:
        case = _case(profile=_profile(user_id="user_other"))
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(case, _resolution(), _empty_normalization())
        self.assertEqual(caught.exception.reason_code, "user_id_mismatch")

    def test_duplicate_record_id_fails(self) -> None:
        event = _event("event_1")
        other_event = _event("event_2")
        record = _norm_record(event)
        normalization = _empty_normalization(hist=(record, record))
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(_case(events=(event, other_event)), _resolution(), normalization)
        self.assertEqual(caught.exception.reason_code, "duplicate_record_id")

    def test_source_event_cannot_own_two_normalized_effects(self) -> None:
        event = _event("event_1", status=EventStatus.SCHEDULED)
        normalization = _empty_normalization(
            effects=(
                _norm_effect(event, "2026-01-15", record_id="effect:first"),
                _norm_effect(event, "2026-01-16", record_id="effect:second"),
            )
        )
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(_case(events=(event,)), _resolution(), normalization)
        self.assertEqual(caught.exception.reason_code, "duplicate_source_owner")

    def test_upstream_block_is_monotonic(self) -> None:
        case = _case()
        normalization = _empty_normalization(blocks=True)
        result = _forecast(case, _resolution(), normalization)
        self.assertTrue(result.blocks_downstream)
        self.assertIsNone(result.minimum_headroom)

    def test_record_without_source_owner_fails(self) -> None:
        event = _event("event_1")
        record = _norm_record(event, record_id="event:event_1")
        orphan = NormalizedCashRecord(
            record_id="event:orphan",
            direction=Direction.DEBIT,
            amount_home=_dec("10"),
            home_currency=CurrencyCode.ZAR,
            source_currency=CurrencyCode.ZAR,
            source_amount=_dec("10"),
            settlement_date=_d("2025-12-06"),
            source_event_ids=(),
            source_fact_ids=(),
            category="utilities",
            event_type=EventType.EXPENSE,
            status=EventStatus.SETTLED,
            flexibility=Flexibility.FIXED,
            minimum_allowed_amount=None,
        )
        normalization = _empty_normalization(hist=(record, orphan))
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(_case(events=(event,)), _resolution(), normalization)
        self.assertEqual(caught.exception.reason_code, "source_owner_missing")

    def test_non_finite_amount_fails(self) -> None:
        event = _event("event_1", amount=_dec("10"))
        record = _norm_record(event, amount_home=Decimal("NaN"))
        normalization = _empty_normalization(hist=(record,))
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(_case(events=(event,)), _resolution(), normalization)
        self.assertEqual(caught.exception.reason_code, "invalid_monetary_input")

    def test_missing_normalized_amount_fails_closed(self) -> None:
        event = _event("event_1")
        record = replace(_norm_record(event), amount_home=None)
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(
                _case(events=(event,)), _resolution(), _empty_normalization(hist=(record,))
            )
        self.assertEqual(caught.exception.reason_code, "invalid_monetary_input")


class CadenceTests(unittest.TestCase):
    """AC-02: only supported strict cadences recur."""

    def _monthly_debit_case(self, days, amounts=None, request_date="2026-01-10"):
        amounts = amounts or ["100", "100", "100"]
        events = tuple(
            _event(
                f"event_ut{index}",
                category="utilities",
                amount=_dec(amounts[index]),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(days)
        )
        return _case(events=events, request=_request(request_date=request_date))

    def test_strict_monthly_debit_projects_after_request_date(self) -> None:
        case = self._monthly_debit_case(
            ["2025-10-06", "2025-11-06", "2025-12-06"]
        )
        result = _forecast(case, _resolution())
        self.assertEqual(
            _occurrence_dates(result, "series:event_ut2"),
            [date(2026, 2, 6), date(2026, 3, 6), date(2026, 4, 6)],
        )
        occurrence = _occurrences_by_date(result)[date(2026, 2, 6)]
        self.assertEqual(occurrence.home_amount, _dec("100"))
        self.assertEqual(occurrence.origin, "fixed_recurrence")
        self.assertEqual(occurrence.direction, Direction.DEBIT)
        trace = next(
            trace
            for trace in result.series_traces
            if trace.family_id == "series:event_ut2"
        )
        self.assertEqual(
            trace.generated_dates,
            (date(2026, 2, 6), date(2026, 3, 6), date(2026, 4, 6)),
        )

    def test_month_end_family_handles_short_and_leap_months(self) -> None:
        events = (
            _event("event_me1", amount=_dec("90"), event_date="2027-11-30", settlement_date="2027-11-30"),
            _event("event_me2", amount=_dec("90"), event_date="2027-12-31", settlement_date="2027-12-31"),
            _event("event_me3", amount=_dec("90"), event_date="2028-01-31", settlement_date="2028-01-31"),
        )
        case = _case(events=events, request=_request(request_date="2028-02-01"))
        result = _forecast(case, _resolution())
        self.assertEqual(
            _occurrence_dates(result, "series:event_me3"),
            [date(2028, 2, 29), date(2028, 3, 31), date(2028, 4, 30)],
        )

    def test_skipped_month_does_not_recur(self) -> None:
        case = self._monthly_debit_case(
            ["2025-09-15", "2025-10-15", "2025-12-15"]
        )
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )
        self.assertTrue(
            any(trace.reason_code == "unsupported_cadence" for trace in result.series_traces)
        )

    def test_two_observations_do_not_recur(self) -> None:
        case = self._monthly_debit_case(["2025-11-06", "2025-12-06"])
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )

    def test_weekly_seven_day_cadence(self) -> None:
        events = tuple(
            _event(
                f"event_wk{index}",
                category="streaming",
                amount=_dec("20"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-12-01", "2025-12-08", "2025-12-15"]
            )
        )
        case = _case(events=events, request=_request(request_date="2025-12-20"))
        result = _forecast(case, _resolution())
        self.assertEqual(
            _occurrence_dates(result, "series:event_wk2"),
            [date(2025, 12, 22), date(2025, 12, 29), date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26), date(2026, 2, 2), date(2026, 2, 9), date(2026, 2, 16), date(2026, 2, 23), date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16)],
        )

    def test_fortnightly_fourteen_day_cadence(self) -> None:
        events = tuple(
            _event(
                f"event_fn{index}",
                category="streaming",
                amount=_dec("20"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-12-01", "2025-12-15", "2025-12-29"]
            )
        )
        case = _case(events=events, request=_request(request_date="2025-12-30"))
        result = _forecast(case, _resolution())
        self.assertEqual(
            _occurrence_dates(result, "series:event_fn2"),
            [date(2026, 1, 12), date(2026, 1, 26), date(2026, 2, 9), date(2026, 2, 23), date(2026, 3, 9), date(2026, 3, 23)],
        )

    def test_tolerant_weekly_and_fortnightly_project_earliest_debits(self) -> None:
        cases = (
            (
                "tw",
                ("2025-12-01", "2025-12-09", "2025-12-15"),
                "2025-12-19",
                [date(2025, 12, 20), date(2025, 12, 27)],
            ),
            (
                "tf",
                ("2025-12-01", "2025-12-16", "2025-12-29"),
                "2025-12-30",
                [date(2026, 1, 10), date(2026, 1, 24)],
            ),
        )
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.TOLERANT_2_DAY,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        for prefix, days, request_date, expected in cases:
            with self.subTest(prefix=prefix):
                events = tuple(
                    _event(
                        f"event_{prefix}{index}",
                        category="streaming",
                        amount=_dec("20"),
                        event_date=day,
                        settlement_date=day,
                    )
                    for index, day in enumerate(days)
                )
                result = _forecast(
                    _case(events=events, request=_request(request_date=request_date)),
                    _resolution(),
                    policy=policy,
                )
                self.assertEqual(
                    _occurrence_dates(result, f"series:event_{prefix}2")[:2],
                    expected,
                )

    def test_description_separates_fixed_series(self) -> None:
        events = tuple(
            _event(
                f"event_desc{description_index}{month_index}",
                category="utilities",
                description=description,
                amount=_dec("100"),
                event_date=day,
                settlement_date=day,
            )
            for description_index, description in enumerate(("Water bill", "Electric bill"))
            for month_index, day in enumerate(
                ("2025-10-06", "2025-11-06", "2025-12-06")
            )
        )
        result = _forecast(_case(events=events), _resolution())
        self.assertEqual(
            _occurrence_dates(result, "series:event_desc02"),
            [date(2026, 2, 6), date(2026, 3, 6), date(2026, 4, 6)],
        )
        self.assertEqual(
            _occurrence_dates(result, "series:event_desc12"),
            [date(2026, 2, 6), date(2026, 3, 6), date(2026, 4, 6)],
        )

    def test_twentyone_day_interval_is_rejected(self) -> None:
        events = tuple(
            _event(
                f"event_td{index}",
                category="streaming",
                amount=_dec("20"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-12-01", "2025-12-22", "2026-01-05"]
            )
        )
        case = _case(events=events, request=_request(request_date="2026-01-10"))
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )

    def test_duplicate_dates_do_not_recur(self) -> None:
        events = (
            _event("event_dd1", amount=_dec("20"), event_date="2025-10-06", settlement_date="2025-10-06"),
            _event("event_dd2", amount=_dec("20"), event_date="2025-11-06", settlement_date="2025-11-06"),
            _event("event_dd3", amount=_dec("20"), event_date="2025-11-06", settlement_date="2025-11-06"),
        )
        case = _case(events=events)
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )

    def test_structured_identity_mismatch_separates_series(self) -> None:
        fixed_events = (
            _event("event_fx1", amount=_dec("20"), event_date="2025-10-06", settlement_date="2025-10-06"),
            _event("event_fx2", amount=_dec("20"), event_date="2025-11-06", settlement_date="2025-11-06"),
        )
        flexible_events = (
            _event(
                "event_fl1",
                amount=_dec("20"),
                event_date="2025-12-06",
                settlement_date="2025-12-06",
                flexibility=Flexibility.REDUCIBLE,
            ),
            _event(
                "event_fl2",
                amount=_dec("20"),
                event_date="2026-01-06",
                settlement_date="2026-01-06",
                flexibility=Flexibility.REDUCIBLE,
            ),
        )
        case = _case(events=fixed_events + flexible_events)
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )

    def test_tolerant_mode_projects_debit_on_earliest_plausible(self) -> None:
        events = tuple(
            _event(
                f"event_tl{index}",
                category="utilities",
                amount=_dec("100"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-15", "2025-11-16", "2025-12-14"]
            )
        )
        case = _case(events=events)
        strict = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in strict.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )
        tolerant = _forecast(
            case,
            _resolution(),
            policy=ForecastPolicy(
                recurrence_timing=RecurrenceTiming.TOLERANT_2_DAY,
                income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
                variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
                horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
                same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
            ),
        )
        self.assertEqual(
            _occurrence_dates(tolerant, "series:event_tl2"),
            [date(2026, 1, 13), date(2026, 2, 13), date(2026, 3, 13)],
        )

    def test_tolerant_monthly_rejects_multiple_observations_in_one_month(self) -> None:
        events = tuple(
            _event(
                f"event_tm{index}",
                amount=_dec("100"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(("2025-10-01", "2025-11-01", "2025-11-02"))
        )
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.TOLERANT_2_DAY,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        result = _forecast(_case(events=events), _resolution(), policy=policy)
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )

    def test_monthly_series_needs_consecutive_months(self) -> None:
        case = self._monthly_debit_case(
            ["2025-10-06", "2025-11-06", "2025-12-06", "2026-02-06"],
            amounts=["100", "100", "100", "100"],
            request_date="2026-03-10",
        )
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )


class AmountSelectionTests(unittest.TestCase):
    def test_equal_amount_suffix_selects_latest_amount(self) -> None:
        events = tuple(
            _event(
                f"event_sa{index}",
                category="utilities",
                amount=_dec(amount),
                event_date=day,
                settlement_date=day,
            )
            for index, (day, amount) in enumerate(
                [
                    ("2025-10-06", "80"),
                    ("2025-11-06", "120"),
                    ("2025-12-06", "120"),
                ]
            )
        )
        case = _case(events=events, messages=(_message("message_11"),))
        result = _forecast(case, _resolution())
        occurrence = _occurrences_by_date(result)[date(2026, 2, 6)]
        self.assertEqual(occurrence.home_amount, _dec("120"))

    def test_varying_debit_without_suffix_is_not_fixed(self) -> None:
        events = tuple(
            _event(
                f"event_va{index}",
                category="utilities",
                amount=_dec(amount),
                event_date=day,
                settlement_date=day,
            )
            for index, (day, amount) in enumerate(
                [
                    ("2025-10-06", "80"),
                    ("2025-11-06", "120"),
                    ("2025-12-06", "140"),
                ]
            )
        )
        case = _case(events=events, messages=(_message("message_11"),))
        result = _forecast(case, _resolution())
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "fixed_recurrence"],
            [],
        )


class FactLifecycleTests(unittest.TestCase):
    """AC-03: evidence lifecycle changes only intended future occurrences."""

    def _rent_case(self, request_date="2026-01-10"):
        events = tuple(
            _event(
                f"event_re{index}",
                category="rent",
                amount=_dec("1000"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-02", "2025-11-02", "2025-12-02"]
            )
        )
        return events, _case(
            events=events,
            messages=(_message("message_11"),),
            request=_request(request_date=request_date),
        )

    def test_recurring_amendment_changes_future_only(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_amount_amendment",
                    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
                    target_event_id="event_re2",
                    amount=_dec("1200"),
                    currency=CurrencyCode.ZAR,
                    effective_date=_d("2026-01-01"),
                    sources=(SourceReference("message", "message_11"),),
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrence_dates(result, "series:event_re2"),
            [date(2026, 2, 2), date(2026, 3, 2), date(2026, 4, 2)],
        )
        occurrence = _occurrences_by_date(result)[date(2026, 2, 2)]
        self.assertEqual(occurrence.home_amount, _dec("1200"))
        self.assertEqual(
            occurrence.source_event_ids, ("event_re2",)
        )

    def test_amendment_without_date_applies_from_next_future(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_amount_amendment",
                    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
                    target_event_id="event_re2",
                    amount=_dec("1300"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        result = _forecast(case, evidence)
        occurrence = _occurrences_by_date(result)[date(2026, 2, 2)]
        self.assertEqual(occurrence.home_amount, _dec("1300"))

    def test_recurring_amendment_preserves_amount_before_effective_date(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_amount_amendment",
                    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
                    target_event_id="event_re2",
                    amount=_dec("200"),
                    currency=CurrencyCode.ZAR,
                    effective_date=_d("2026-03-01"),
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrences_by_date(result)[date(2026, 2, 2)].home_amount,
            _dec("1000"),
        )
        self.assertEqual(
            _occurrences_by_date(result)[date(2026, 3, 2)].home_amount,
            _dec("200"),
        )

    def test_next_cycle_amendment_is_conservative_for_debits(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::next_cycle_amount_amendment",
                    EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
                    target_event_id="event_re2",
                    amount=_dec("800"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        result = _forecast(case, evidence)
        first = _occurrences_by_date(result)[date(2026, 2, 2)]
        self.assertEqual(first.home_amount, _dec("800"))
        second = _occurrences_by_date(result)[date(2026, 3, 2)]
        self.assertEqual(second.home_amount, _dec("1000"))

    def test_next_cycle_amendment_is_conservative_for_credits(self) -> None:
        events = tuple(
            _event(
                f"event_cr{index}",
                event_type=EventType.INCOME,
                category="salary",
                direction=Direction.CREDIT,
                amount=_dec("500"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-15", "2025-11-15", "2025-12-15"]
            )
        )
        case = _case(events=events, messages=(_message("message_11"),))
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::next_cycle_amount_amendment",
                    EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
                    target_event_id="event_cr2",
                    amount=_dec("400"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I1_STRICT_RECENT_HISTORY,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        result = _forecast(case, evidence, policy=policy)
        occurrence = _occurrences_by_date(result)[date(2026, 1, 15)]
        self.assertEqual(occurrence.home_amount, _dec("400"))
        later = _occurrences_by_date(result)[date(2026, 2, 15)]
        self.assertEqual(later.home_amount, _dec("400"))

    def test_settlement_date_replacement_moves_first_occurrence(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::settlement_date_replacement",
                    EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
                    target_event_id="event_re2",
                    settlement_date=_d("2026-02-10"),
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrence_dates(result, "series:event_re2"),
            [date(2026, 2, 10), date(2026, 3, 2), date(2026, 4, 2)],
        )

    def test_delayed_date_replacement_preserves_other_cycles(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::settlement_date_replacement",
                    EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
                    target_event_id="event_re2",
                    settlement_date=_d("2026-03-10"),
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrence_dates(result, "series:event_re2"),
            [date(2026, 2, 2), date(2026, 3, 10), date(2026, 4, 2)],
        )

    def test_recurrence_stop_removes_all_future(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurrence_stop",
                    EvidenceFactType.RECURRENCE_STOP,
                    target_event_id="event_re2",
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(_occurrence_dates(result, "series:event_re2"), [])
        trace = next(
            trace
            for trace in result.series_traces
            if trace.family_id == "series:event_re2"
        )
        self.assertEqual(trace.reason_code, "stopped")

    def test_recurrence_resume_restarts_at_boundary(self) -> None:
        events, case = self._rent_case(request_date="2026-02-10")
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurrence_stop",
                    EvidenceFactType.RECURRENCE_STOP,
                    target_event_id="event_re2",
                ),
                _fact(
                    "message_11::recurrence_resume",
                    EvidenceFactType.RECURRENCE_RESUME,
                    target_event_id="event_re2",
                    amount=_dec("900"),
                    currency=CurrencyCode.ZAR,
                    effective_date=_d("2026-02-15"),
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrence_dates(result, "series:event_re2"),
            [date(2026, 2, 15), date(2026, 4, 2), date(2026, 5, 2)],
        )
        occurrence = _occurrences_by_date(result)[date(2026, 2, 15)]
        self.assertEqual(occurrence.home_amount, _dec("900"))

    def test_recurrence_resume_replaces_next_weekly_slot(self) -> None:
        events = tuple(
            _event(
                f"event_rr{index}",
                category="streaming",
                amount=_dec("20"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2026-01-09", "2026-01-16", "2026-01-23"]
            )
        )
        case = _case(
            events=events,
            messages=(_message("message_11"),),
            request=_request(request_date="2026-01-31"),
        )
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurrence_stop",
                    EvidenceFactType.RECURRENCE_STOP,
                    target_event_id="event_rr2",
                ),
                _fact(
                    "message_11::recurrence_resume",
                    EvidenceFactType.RECURRENCE_RESUME,
                    target_event_id="event_rr2",
                    amount=_dec("20"),
                    currency=CurrencyCode.ZAR,
                    effective_date=_d("2026-02-01"),
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrence_dates(result, "series:event_rr2")[:2],
            [date(2026, 2, 1), date(2026, 2, 13)],
        )
        self.assertNotIn(
            date(2026, 2, 6), _occurrence_dates(result, "series:event_rr2")
        )

    def test_explicit_effect_replaces_matching_inferred_slot(self) -> None:
        events, case = self._rent_case()
        normalization = _empty_normalization(
            hist=tuple(_norm_record(event) for event in events),
            effects=(
                _norm_effect(
                    events[-1],
                    "2026-02-02",
                    amount_home=_dec("125"),
                    record_id="effect:event_re2",
                ),
            ),
        )
        result = _forecast(case, _resolution(), normalization)
        occurrences = [
            occurrence
            for occurrence in result.projected_occurrences
            if occurrence.date == date(2026, 2, 2)
        ]
        self.assertEqual(len(occurrences), 1)
        self.assertEqual(occurrences[0].origin, "explicit")
        self.assertEqual(occurrences[0].home_amount, _dec("125"))

    def test_unbounded_notice_blocks_without_occurrence(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_expense_notice",
                    EvidenceFactType.RECURRING_EXPENSE_NOTICE,
                    target_event_id="event_re2",
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(_occurrence_dates(result, "series:event_re2"), [])
        self.assertTrue(result.blocks_downstream)
        self.assertIsNone(result.minimum_headroom)
        self.assertIn("unbounded_recurring_debit", _diag_codes(result))

    def test_amendment_to_unknown_target_blocks_debit(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_amount_amendment",
                    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
                    target_event_id="event_re9",
                    amount=_dec("1200"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        normalization = _empty_normalization()
        result = _forecast(case, evidence, normalization)
        self.assertTrue(result.blocks_downstream)
        self.assertIn("amendment_target_unresolved", _diag_codes(result))

    def test_history_never_changes_from_facts(self) -> None:
        events, case = self._rent_case()
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_amount_amendment",
                    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
                    target_event_id="event_re2",
                    amount=_dec("1200"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(result.opening_cash, _dec("1000"))
        trace = next(
            trace
            for trace in result.series_traces
            if trace.family_id == "series:event_re2"
        )
        self.assertEqual(
            [(obs[0], obs[1]) for obs in trace.observations],
            [
                (date(2025, 10, 2), _dec("1000")),
                (date(2025, 11, 2), _dec("1000")),
                (date(2025, 12, 2), _dec("1000")),
            ],
        )


class VariableSpendingTests(unittest.TestCase):
    """AC-04: conservative variable envelopes with exclusive ownership."""

    def _variable_case(self, request_date="2026-01-10"):
        groceries = [
            ("2025-09-05", "40"), ("2025-09-15", "50"), ("2025-09-25", "60"),
            ("2025-10-08", "200"),
            ("2025-11-10", "120"),
        ]
        events = tuple(
            _event(
                f"event_gr{index}",
                category="groceries",
                amount=_dec(amount),
                event_date=day,
                settlement_date=day,
            )
            for index, (day, amount) in enumerate(groceries)
        )
        return events, _case(
            events=events,
            messages=(_message("message_11"),),
            request=_request(request_date=request_date),
        )

    def test_v0_uses_maximum_of_latest_three_usable_months(self) -> None:
        events, case = self._variable_case()
        result = _forecast(case, _resolution())
        envelopes = [
            occ for occ in result.projected_occurrences if occ.origin == "variable_envelope"
        ]
        self.assertEqual(
            [occ.home_amount for occ in envelopes],
            [_dec("200"), _dec("200"), _dec("200"), _dec("200")],
        )
        self.assertEqual(
            [occ.date for occ in envelopes],
            [date(2026, 1, 10), date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
        )
        self.assertEqual(envelopes[0].family_id, "variable:groceries:ZAR")

    def test_v0_reserves_envelope_at_opening_checkpoint(self) -> None:
        events, case = self._variable_case()
        result = _forecast(case, _resolution())
        opening = result.checkpoints[0]
        self.assertEqual(opening.kind, "opening")
        self.assertEqual(opening.cash_balance, _dec("1000"))
        reserve_cp = result.checkpoints[1]
        self.assertEqual(reserve_cp.kind, "debit")
        self.assertEqual(reserve_cp.date, date(2026, 1, 10))
        self.assertEqual(reserve_cp.cash_balance, _dec("800"))
        self.assertEqual(reserve_cp.spendable_balance, _dec("800"))

    def test_v0_requires_two_usable_months(self) -> None:
        events = (
            _event("event_gr0", category="groceries", amount=_dec("120"), event_date="2025-11-10", settlement_date="2025-11-10"),
        )
        case = _case(events=events)
        result = _forecast(case, _resolution())
        self.assertTrue(result.blocks_downstream)
        self.assertIsNone(result.minimum_headroom)
        self.assertIn("variable_history_unbounded", _diag_codes(result))
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "variable_envelope"],
            [],
        )

    def test_v2_mean_rounds_up_to_cent(self) -> None:
        events, case = self._variable_case()
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V2_MEAN_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        result = _forecast(case, _resolution(), policy=policy)
        envelopes = [
            occ for occ in result.projected_occurrences if occ.origin == "variable_envelope"
        ]
        self.assertEqual(
            [occ.home_amount for occ in envelopes],
            [_dec("156.67"), _dec("156.67"), _dec("156.67"), _dec("156.67")],
        )

    def test_v1_uses_max_cadenced_occurrence_instead_of_envelope(self) -> None:
        weekly = [
            ("2025-10-06", "30"), ("2025-10-13", "40"), ("2025-10-20", "35"),
            ("2025-10-27", "36"), ("2025-11-03", "38"), ("2025-11-10", "42"),
        ]
        events = tuple(
            _event(
                f"event_v1{index}",
                category="groceries",
                amount=_dec(amount),
                event_date=day,
                settlement_date=day,
            )
            for index, (day, amount) in enumerate(weekly)
        )
        case = _case(events=events)
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V1_MAX_CADENCED_OCCURRENCE,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        result = _forecast(case, _resolution(), policy=policy)
        envelopes = [
            occ for occ in result.projected_occurrences if occ.origin == "variable_envelope"
        ]
        self.assertEqual(envelopes, [])
        groceries_occurrences = [
            occ
            for occ in result.projected_occurrences
            if occ.family_id == "variable:groceries:ZAR:event_v15"
        ]
        self.assertTrue(groceries_occurrences)
        self.assertEqual(groceries_occurrences[0].date, date(2026, 1, 12))
        self.assertEqual(groceries_occurrences[0].home_amount, _dec("42"))

    def test_variable_families_include_source_currency_for_all_policies(self) -> None:
        monthly_events = tuple(
            _event(
                f"event_vm{currency.value}{index}",
                category="groceries",
                amount=_dec(amount),
                currency=currency,
                event_date=day,
                settlement_date=day,
            )
            for currency, amount in ((CurrencyCode.ZAR, "100"), (CurrencyCode.USD, "10"))
            for index, day in enumerate(("2025-10-05", "2025-11-05"))
        )
        monthly_case = _case(events=monthly_events)
        monthly_normalization = _empty_normalization(
            hist=tuple(
                _norm_record(
                    event,
                    amount_home=_dec("100") if event.currency is CurrencyCode.ZAR else _dec("200"),
                )
                for event in monthly_events
            )
        )
        for policy_kind in (
            VariableSpending.V0_MAX_COMPLETE_MONTH,
            VariableSpending.V2_MEAN_COMPLETE_MONTH,
        ):
            policy = ForecastPolicy(
                recurrence_timing=RecurrenceTiming.STRICT,
                income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
                variable_spending=policy_kind,
                horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
                same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
            )
            result = _forecast(
                monthly_case, _resolution(), monthly_normalization, policy=policy
            )
            families = {
                occurrence.family_id
                for occurrence in result.projected_occurrences
                if occurrence.origin == "variable_envelope"
            }
            self.assertEqual(families, {"variable:groceries:USD", "variable:groceries:ZAR"})

        weekly_events = tuple(
            _event(
                f"event_v1{currency.value}{index}",
                category="groceries",
                amount=_dec(amount),
                currency=currency,
                event_date=day,
                settlement_date=day,
            )
            for currency, amounts in (
                (CurrencyCode.ZAR, ("10", "20", "30")),
                (CurrencyCode.USD, ("1", "2", "3")),
            )
            for index, (day, amount) in enumerate(
                zip(("2025-12-01", "2025-12-08", "2025-12-15"), amounts)
            )
        )
        weekly_case = _case(events=weekly_events)
        weekly_normalization = _empty_normalization(
            hist=tuple(
                _norm_record(
                    event,
                    amount_home=event.amount if event.currency is CurrencyCode.ZAR else event.amount * _dec("10"),
                )
                for event in weekly_events
            )
        )
        v1_policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V1_MAX_CADENCED_OCCURRENCE,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        v1_result = _forecast(
            weekly_case, _resolution(), weekly_normalization, policy=v1_policy
        )
        v1_families = {
            occurrence.family_id
            for occurrence in v1_result.projected_occurrences
            if occurrence.origin == "variable_series"
        }
        self.assertEqual(len(v1_families), 2)
        self.assertTrue(any(":USD:" in family for family in v1_families))
        self.assertTrue(any(":ZAR:" in family for family in v1_families))

    def test_envelope_never_combines_with_fixed_series(self) -> None:
        rent_events = tuple(
            _event(
                f"event_rt{index}",
                category="rent",
                amount=_dec("1000"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-02", "2025-11-02", "2025-12-02"]
            )
        )
        groceries = [
            ("2025-11-05", "150"),
            ("2025-11-25", "180"),
        ]
        grocery_events = tuple(
            _event(
                f"event_gr{index}",
                category="groceries",
                amount=_dec(amount),
                event_date=day,
                settlement_date=day,
            )
            for index, (day, amount) in enumerate(groceries)
        )
        case = _case(events=rent_events + grocery_events)
        result = _forecast(case, _resolution())
        # rent recurs as fixed series; groceries have only one usable month -> blocked
        self.assertTrue(result.blocks_downstream)
        rent_dates = _occurrence_dates(result, "series:event_rt2")
        self.assertIn(date(2026, 2, 2), rent_dates)
        self.assertEqual(
            [occ for occ in result.projected_occurrences if occ.origin == "variable_envelope"],
            [],
        )


class IncomeAndFXTests(unittest.TestCase):
    """AC-05: income is never optimistic; FX is exact per settlement date."""

    def _salary_case(self, months, request_date="2026-01-10", currency=CurrencyCode.ZAR):
        events = tuple(
            _event(
                f"event_in{index}",
                event_type=EventType.INCOME,
                category="salary",
                direction=Direction.CREDIT,
                amount=_dec("500"),
                currency=currency,
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(months)
        )
        return events, _case(
            events=events,
            messages=(_message("message_11"),),
            request=_request(request_date=request_date),
        )

    def _i1_policy(self):
        return ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I1_STRICT_RECENT_HISTORY,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )

    def test_i0_does_not_continue_plain_salary_history(self) -> None:
        events, case = self._salary_case(
            ["2025-10-15", "2025-11-15", "2025-12-15"]
        )
        result = _forecast(case, _resolution())
        credits = [
            occ
            for occ in result.projected_occurrences
            if occ.direction is Direction.CREDIT
        ]
        self.assertEqual(credits, [])

    def test_i1_continues_strict_recent_salary(self) -> None:
        events, case = self._salary_case(
            ["2025-10-15", "2025-11-15", "2025-12-15"]
        )
        result = _forecast(case, _resolution(), policy=self._i1_policy())
        self.assertEqual(
            _occurrence_dates(result, "series:event_in2"),
            [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)],
        )

    def test_i0_amendment_establishes_ongoing(self) -> None:
        events, case = self._salary_case(
            ["2025-10-15", "2025-11-15", "2025-12-15"]
        )
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurring_amount_amendment",
                    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
                    target_event_id="event_in2",
                    amount=_dec("600"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(
            _occurrence_dates(result, "series:event_in2"),
            [date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 15)],
        )
        occurrence = _occurrences_by_date(result)[date(2026, 1, 15)]
        self.assertEqual(occurrence.home_amount, _dec("600"))

    def test_i0_confirmation_is_next_only(self) -> None:
        events, case = self._salary_case(
            ["2025-10-15", "2025-11-15", "2025-12-15"]
        )
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::recurrence_confirmation",
                    EvidenceFactType.RECURRENCE_CONFIRMATION,
                    target_event_id="event_in2",
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(_occurrence_dates(result, "series:event_in2"), [])

    def test_i0_next_cycle_amendment_does_not_establish_ongoing_income(self) -> None:
        events, case = self._salary_case(
            ["2025-10-15", "2025-11-15", "2025-12-15"]
        )
        evidence = _resolution(
            facts=(
                _fact(
                    "message_11::next_cycle_amount_amendment",
                    EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
                    target_event_id="event_in2",
                    amount=_dec("400"),
                    currency=CurrencyCode.ZAR,
                ),
            )
        )
        result = _forecast(case, evidence)
        self.assertEqual(_occurrence_dates(result, "series:event_in2"), [])

    def test_missed_expected_credit_makes_salary_stale(self) -> None:
        events, case = self._salary_case(
            ["2025-09-15", "2025-10-15", "2025-11-15"],
            request_date="2026-01-20",
        )
        result = _forecast(case, _resolution(), policy=self._i1_policy())
        self.assertEqual(_occurrence_dates(result), [])
        trace = next(
            trace
            for trace in result.series_traces
            if trace.family_id == "series:event_in2"
        )
        self.assertEqual(trace.reason_code, "stale_credit")

    def test_missed_debit_starts_after_request_date(self) -> None:
        events = tuple(
            _event(
                f"event_md{index}",
                category="utilities",
                amount=_dec("100"),
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-06", "2025-11-06", "2025-12-06"]
            )
        )
        case = _case(events=events, request=_request(request_date="2026-01-10"))
        result = _forecast(case, _resolution())
        self.assertEqual(
            _occurrence_dates(result, "series:event_md2"),
            [date(2026, 2, 6), date(2026, 3, 6), date(2026, 4, 6)],
        )

    def test_one_time_credit_never_recurs(self) -> None:
        events = (
            _event(
                "event_ot1",
                event_type=EventType.REFUND,
                category="shopping",
                direction=Direction.CREDIT,
                amount=_dec("50"),
                event_date="2025-11-01",
                settlement_date="2025-11-01",
            ),
            _event(
                "event_ot2",
                event_type=EventType.REFUND,
                category="shopping",
                direction=Direction.CREDIT,
                amount=_dec("50"),
                event_date="2025-12-01",
                settlement_date="2025-12-01",
            ),
            _event(
                "event_ot3",
                event_type=EventType.REFUND,
                category="shopping",
                direction=Direction.CREDIT,
                amount=_dec("50"),
                event_date="2026-01-01",
                settlement_date="2026-01-01",
            ),
        )
        case = _case(events=events)
        result = _forecast(case, _resolution(), policy=self._i1_policy())
        self.assertEqual(_occurrence_dates(result), [])

    def test_foreign_salary_converts_per_settlement_date(self) -> None:
        events = tuple(
            _event(
                f"event_us{index}",
                event_type=EventType.INCOME,
                category="salary",
                direction=Direction.CREDIT,
                amount=_dec("100"),
                currency=CurrencyCode.USD,
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-15", "2025-11-15", "2025-12-15"]
            )
        )
        rates = (
            _rate("2025-10-15", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-11-15", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-12-15", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2026-01-15", CurrencyCode.USD, CurrencyCode.ZAR, "12"),
            _rate("2026-02-15", CurrencyCode.USD, CurrencyCode.ZAR, "14"),
        )
        case = _case(events=events, rates=rates)
        result = _forecast(case, _resolution(), policy=self._i1_policy())
        occurrences = {occ.date: occ for occ in result.projected_occurrences}
        self.assertEqual(occurrences[date(2026, 1, 15)].home_amount, _dec("1200"))
        self.assertEqual(occurrences[date(2026, 2, 15)].home_amount, _dec("1400"))
        self.assertFalse(result.blocks_downstream)

    def test_missing_credit_fx_omits_only_that_credit(self) -> None:
        events = tuple(
            _event(
                f"event_us{index}",
                event_type=EventType.INCOME,
                category="salary",
                direction=Direction.CREDIT,
                amount=_dec("100"),
                currency=CurrencyCode.USD,
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-15", "2025-11-15", "2025-12-15"]
            )
        )
        rates = (
            _rate("2025-10-15", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-11-15", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-12-15", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2026-01-15", CurrencyCode.USD, CurrencyCode.ZAR, "12"),
        )
        case = _case(events=events, rates=rates)
        result = _forecast(case, _resolution(), policy=self._i1_policy())
        dates = _occurrence_dates(result, "series:event_us2")
        self.assertEqual(dates, [date(2026, 1, 15)])
        self.assertFalse(result.blocks_downstream)
        self.assertIn("fx_rate_missing_credit", _diag_codes(result))
        self.assertIsNotNone(result.minimum_headroom)

    def test_missing_debit_fx_blocks(self) -> None:
        events = tuple(
            _event(
                f"event_fd{index}",
                category="utilities",
                amount=_dec("10"),
                currency=CurrencyCode.USD,
                event_date=day,
                settlement_date=day,
            )
            for index, day in enumerate(
                ["2025-10-06", "2025-11-06", "2025-12-06"]
            )
        )
        rates = (
            _rate("2025-10-06", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-11-06", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-12-06", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
        )
        case = _case(events=events, rates=rates)
        result = _forecast(case, _resolution())
        self.assertTrue(result.blocks_downstream)
        self.assertIsNone(result.minimum_headroom)
        self.assertIn("fx_rate_missing_debit", _diag_codes(result))

    def test_conflicting_rates_fail_atomically(self) -> None:
        events = (
            _event(
                "event_cf1",
                category="utilities",
                amount=_dec("10"),
                currency=CurrencyCode.USD,
                event_date="2025-10-06",
                settlement_date="2025-10-06",
            ),
            _event(
                "event_cf2",
                category="utilities",
                amount=_dec("10"),
                currency=CurrencyCode.USD,
                event_date="2025-11-06",
                settlement_date="2025-11-06",
            ),
            _event(
                "event_cf3",
                category="utilities",
                amount=_dec("10"),
                currency=CurrencyCode.USD,
                event_date="2025-12-06",
                settlement_date="2025-12-06",
            ),
        )
        rates = (
            _rate("2025-10-06", CurrencyCode.USD, CurrencyCode.ZAR, "10"),
            _rate("2025-10-06", CurrencyCode.USD, CurrencyCode.ZAR, "11"),
        )
        case = _case(events=events, rates=rates)
        with self.assertRaises(ForecastBuildError) as caught:
            _forecast(case, _resolution(), _empty_normalization())
        self.assertEqual(caught.exception.reason_code, "fx_rate_conflict")


class LedgerTests(unittest.TestCase):
    """AC-06/AC-07: exact checkpoint boundary and conservative failure."""

    def _reserve_case(self, settlement_date="2026-01-20", request_date="2026-01-10"):
        pending = _event(
            "event_pd1",
            category="shopping",
            amount=_dec("200"),
            event_date="2026-01-05",
            settlement_date=settlement_date,
            status=EventStatus.PENDING,
        )
        case = _case(events=(pending,), request=_request(request_date=request_date))
        return case

    def test_reserve_reduces_spendable_once(self) -> None:
        case = self._reserve_case()
        evidence = _resolution()
        normalization = normalize_case_events(case, evidence)
        result = _forecast(case, evidence, normalization)
        opening = result.checkpoints[0]
        self.assertEqual(opening.kind, "opening")
        self.assertEqual(opening.cash_balance, _dec("1000"))
        self.assertEqual(opening.reserved_balance, _dec("0"))
        reserve_cp = next(cp for cp in result.checkpoints if cp.kind == "reserve")
        self.assertEqual(reserve_cp.reserved_balance, _dec("200"))
        self.assertEqual(reserve_cp.spendable_balance, _dec("800"))
        settlement_cp = next(
            cp for cp in result.checkpoints if cp.kind == "reserve_settlement"
        )
        self.assertEqual(settlement_cp.cash_balance, _dec("800"))
        self.assertEqual(settlement_cp.reserved_balance, _dec("0"))
        self.assertEqual(settlement_cp.spendable_balance, _dec("800"))

    def test_reserve_settling_after_horizon_stays_reserved(self) -> None:
        case = self._reserve_case(settlement_date="2026-04-20")
        evidence = _resolution()
        normalization = normalize_case_events(case, evidence)
        result = _forecast(case, evidence, normalization)
        self.assertEqual(
            [cp.kind for cp in result.checkpoints if cp.kind == "reserve_settlement"],
            [],
        )
        last = result.checkpoints[-1]
        self.assertEqual(last.reserved_balance, _dec("200"))

    def test_day_90_included_by_default_and_excluded_under_day_89(self) -> None:
        scheduled = _event(
            "event_s90",
            category="shopping",
            direction=Direction.CREDIT,
            amount=_dec("70"),
            event_date="2026-04-10",
            settlement_date="2026-04-10",
            status=EventStatus.SCHEDULED,
        )
        case = _case(events=(scheduled,))
        evidence = _resolution()
        normalization = normalize_case_events(case, evidence)
        default = _forecast(case, evidence, normalization)
        self.assertIn(
            date(2026, 4, 10), _occurrence_dates(default)
        )
        day89 = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_89_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        result89 = _forecast(case, evidence, normalization, policy=day89)
        self.assertEqual(result89.horizon_end, date(2026, 4, 9))
        self.assertNotIn(
            date(2026, 4, 10), _occurrence_dates(result89)
        )

    def test_debit_before_credit_same_day_default(self) -> None:
        debit = _event(
            "event_dc1",
            category="shopping",
            amount=_dec("900"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        credit = _event(
            "event_dc2",
            event_type=EventType.INCOME,
            category="salary",
            direction=Direction.CREDIT,
            amount=_dec("900"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        case = _case(events=(debit, credit))
        evidence = _resolution()
        normalization = normalize_case_events(case, evidence)
        result = _forecast(case, evidence, normalization)
        day_cps = [
            cp for cp in result.checkpoints if cp.date == date(2026, 1, 15)
        ]
        self.assertEqual(
            [cp.kind for cp in day_cps], ["debit", "credit"]
        )
        self.assertEqual(day_cps[0].spendable_balance, _dec("100"))
        self.assertEqual(day_cps[1].spendable_balance, _dec("1000"))
        self.assertEqual(day_cps[0].headroom, _dec("0"))

    def test_same_day_same_kind_uses_stable_record_order(self) -> None:
        event_b = _event(
            "event_b",
            amount=_dec("100"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        event_a = _event(
            "event_a",
            amount=_dec("200"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        case = _case(events=(event_b, event_a))
        result = _forecast(
            case,
            _resolution(),
            _empty_normalization(
                effects=(_norm_effect(event_b, "2026-01-15"), _norm_effect(event_a, "2026-01-15"))
            ),
        )
        day_debits = [
            checkpoint
            for checkpoint in result.checkpoints
            if checkpoint.date == date(2026, 1, 15) and checkpoint.kind == "debit"
        ]
        self.assertEqual(
            [checkpoint.source_ids for checkpoint in day_debits],
            [("event_a",), ("event_b",)],
        )

    def test_alternate_order_reverses_credit_and_debit(self) -> None:
        debit = _event(
            "event_dc1",
            category="shopping",
            amount=_dec("900"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        credit = _event(
            "event_dc2",
            event_type=EventType.INCOME,
            category="salary",
            direction=Direction.CREDIT,
            amount=_dec("900"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        case = _case(events=(debit, credit))
        evidence = _resolution()
        normalization = normalize_case_events(case, evidence)
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.CREDIT_DEBIT_PAYMENT,
        )
        result = _forecast(case, evidence, normalization, policy=policy)
        day_cps = [
            cp for cp in result.checkpoints if cp.date == date(2026, 1, 15)
        ]
        self.assertEqual(
            [cp.kind for cp in day_cps], ["credit", "debit"]
        )

    def test_negative_headroom_reported_exactly(self) -> None:
        debit = _event(
            "event_neg",
            category="shopping",
            amount=_dec("1500"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        case = _case(events=(debit,))
        result = _forecast(case, _resolution())
        debit_cp = next(cp for cp in result.checkpoints if cp.kind == "debit")
        self.assertEqual(debit_cp.spendable_balance, _dec("-500"))
        self.assertEqual(debit_cp.headroom, _dec("-600"))
        self.assertEqual(result.minimum_headroom, _dec("-600"))

    def test_minimum_headroom_over_checkpoints(self) -> None:
        debit = _event(
            "event_min",
            category="shopping",
            amount=_dec("300"),
            event_date="2026-01-15",
            settlement_date="2026-01-15",
            status=EventStatus.SCHEDULED,
        )
        credit = _event(
            "event_minc",
            event_type=EventType.INCOME,
            category="salary",
            direction=Direction.CREDIT,
            amount=_dec("500"),
            event_date="2026-02-15",
            settlement_date="2026-02-15",
            status=EventStatus.SCHEDULED,
        )
        case = _case(events=(debit, credit))
        result = _forecast(case, _resolution())
        self.assertEqual(result.minimum_headroom, _dec("600"))


class ComponentCorpusTests(unittest.TestCase):
    """Component tests through repository -> evidence -> events -> forecast."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = DatasetRepository.from_directory("dataset")

    def _run(self, request_id):
        case = self.repository.load_request_case(request_id)
        evidence = resolve_case_evidence(case)
        normalization = normalize_case_events(case, evidence)
        return case, _forecast(case, evidence, normalization)

    def test_request_02_salary_amendment_projects_amended_amount(self) -> None:
        case, result = self._run("request_02")
        self.assertEqual(case.request.request_id, "request_02")
        salary_family = "series:event_136"
        salary_dates = _occurrence_dates(result, salary_family)
        self.assertIn(date(2025, 9, 15), salary_dates)
        occurrence = next(
            occ
            for occ in result.projected_occurrences
            if occ.family_id == salary_family and occ.date == date(2025, 9, 15)
        )
        self.assertEqual(occurrence.home_amount, _dec("42750000"))
        self.assertEqual(occurrence.source_amount, _dec("42750000"))
        self.assertEqual(occurrence.origin, "fixed_recurrence")

    def test_request_25_foreign_salary_uses_exact_fx_per_date(self) -> None:
        case, result = self._run("request_25")
        self.assertEqual(case.profile.home_currency, CurrencyCode.IDR)
        salary_family = "series:event_2199"
        policy = ForecastPolicy(
            recurrence_timing=RecurrenceTiming.STRICT,
            income_continuation=IncomeContinuation.I1_STRICT_RECENT_HISTORY,
            variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
            horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
            same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
        )
        case, result = self._run("request_25")
        evidence = resolve_case_evidence(case)
        normalization = normalize_case_events(case, evidence)
        result = _forecast(case, evidence, normalization, policy=policy)
        occurrence = next(
            occ
            for occ in result.projected_occurrences
            if occ.family_id == salary_family
            and occ.date == date(2024, 3, 15)
        )
        self.assertEqual(occurrence.source_amount, _dec("1800"))
        self.assertEqual(occurrence.source_currency, CurrencyCode.USD)
        self.assertEqual(occurrence.home_amount, _dec("28499994.00"))

    def test_component_result_invariants(self) -> None:
        for request_id in ("request_02", "request_09"):
            case, result = self._run(request_id)
            self.assertEqual(result.request_id, request_id)
            self.assertEqual(
                result.request_date, case.request.request_date
            )
            self.assertEqual(result.opening_cash, case.profile.current_available_balance)
            self.assertEqual(result.minimum_balance, case.profile.minimum_balance_to_keep)
            # every historical record is owned by exactly one trace
            owned = [
                record_id
                for trace in result.series_traces
                for record_id in trace.observation_record_ids
            ]
            self.assertEqual(len(owned), len(set(owned)))
            self.assertEqual(len(owned), len(normalize_case_events(
                case, resolve_case_evidence(case)
            ).historical_cash))
            # checkpoints are ordered and reconstructible
            self.assertEqual(result.checkpoints[0].kind, "opening")
            dates = [cp.date for cp in result.checkpoints]
            self.assertEqual(dates, sorted(dates))


from buy_or_wait.evidence import resolve_case_evidence  # noqa: E402


if __name__ == "__main__":
    unittest.main()

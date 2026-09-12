"""Focused tests for the WP-04 lifecycle normalization and exact FX boundary.

Fail-first suite for ``buy_or_wait.events``. Small immutable synthetic
``RequestCase`` and ``EvidenceResolution`` builders keep every decisive amount,
date, ID, link, and reason code visible in each test. Component cases load
accepted participant-facing sample cases through ``DatasetRepository`` and
normalize them through the public API with explicit expected values.
"""

from __future__ import annotations

import sys
import unittest
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
    EventNormalizationError,
    NormalizationDecision,
    NormalizedCashEffect,
    NormalizedCashRecord,
    NormalizedReserve,
    normalize_case_events,
)


def _d(value: str) -> date:
    return date.fromisoformat(value)


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
        requested_amount=Decimal("100"),
        desired_completion_date=_d("2026-03-01"),
        allows_partial_payment=True,
        scope=RequestScope.SAMPLE,
    )


def _profile(
    user_id: str = "user_T",
    home_currency: CurrencyCode = CurrencyCode.ZAR,
) -> ProfileRecord:
    return ProfileRecord(
        user_id=user_id,
        home_currency=home_currency,
        current_available_balance=Decimal("1000"),
        minimum_balance_to_keep=Decimal("100"),
        financial_priorities=frozenset(),
        expense_categories_to_protect=frozenset(),
        expense_categories_user_is_willing_to_reduce=frozenset(),
        expense_categories_user_is_willing_to_stop=frozenset(),
        payment_methods_user_will_consider=(PaymentMethod.FULL_PAYMENT,),
        max_installment_months=None,
    )


def _event(
    event_id: str,
    user_id: str = "user_T",
    event_type: EventType = EventType.EXPENSE,
    category: str = "groceries",
    direction: Direction = Direction.DEBIT,
    amount: Decimal | None = Decimal("100"),
    currency: CurrencyCode = CurrencyCode.ZAR,
    event_date: str = "2025-12-15",
    settlement_date: str | None = "2025-12-16",
    status: EventStatus = EventStatus.SETTLED,
    linked_event_id: str | None = None,
    flexibility: Flexibility = Flexibility.FIXED,
    minimum_allowed_amount: Decimal | None = None,
) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        user_id=user_id,
        event_type=event_type,
        description=f"event {event_id}",
        category=category,
        direction=direction,
        amount=amount,
        currency=currency,
        event_date=_d(event_date),
        settlement_date=_d(settlement_date) if settlement_date else None,
        status=status,
        linked_event_id=linked_event_id,
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
    fact_id: str = "message_11::confirmed_future_credit",
    fact_type: EvidenceFactType = EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
    sources: tuple[SourceReference, ...] = (
        SourceReference("message", "message_11"),
    ),
    target_event_id: str | None = None,
    amount: Decimal | None = None,
    currency: CurrencyCode | None = None,
    effective_date: date | None = None,
    settlement_date: date | None = None,
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


def _decisions_by_subject(result: EventNormalization) -> dict[tuple[str, str], NormalizationDecision]:
    return {
        (decision.subject_kind, decision.subject_id): decision
        for decision in result.decisions
    }


class BoundaryValidationTests(unittest.TestCase):
    """Phase 1: fail closed on an unrepresentable input contract."""

    def test_duplicate_event_id_fails_closed(self) -> None:
        case = _case(
            events=(
                _event("event_A", amount=Decimal("10")),
                _event("event_A", amount=Decimal("20"), event_date="2025-12-20"),
            )
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "duplicate_event_id")

    def test_duplicate_fact_id_fails_closed(self) -> None:
        case = _case(
            messages=(_message("message_11"),),
            events=(_event("event_A"),),
        )
        fact = _fact(target_event_id="event_A")
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact, fact)))
        self.assertEqual(ctx.exception.reason_code, "duplicate_fact_id")

    def test_fact_targeting_unknown_event_fails_closed(self) -> None:
        case = _case(messages=(_message("message_11"),), events=(_event("event_A"),))
        fact = _fact(fact_type=EvidenceFactType.EVENT_AMOUNT, target_event_id="event_ghost")
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "unknown_fact_target")

    def test_fact_carrier_not_in_case_fails_closed(self) -> None:
        case = _case(events=(_event("event_A"),))
        fact = _fact(
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            target_event_id="event_A",
            amount=Decimal("100"),
            currency=CurrencyCode.ZAR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "unknown_fact_carrier")

    def test_upstream_blocks_downstream_is_never_cleared(self) -> None:
        case = _case()
        result = normalize_case_events(
            case,
            _resolution(
                diagnostics=(
                    EvidenceDiagnostic(
                        "message",
                        "message_11",
                        "unresolved_required_debit_blocks",
                        ("message_11",),
                        blocks_downstream=True,
                    ),
                ),
                blocks_downstream=True,
            ),
        )
        self.assertTrue(result.blocks_downstream)

    def test_upstream_diagnostic_propagates_by_safe_ids(self) -> None:
        case = _case(messages=(_message("message_11"),))
        result = normalize_case_events(
            case,
            _resolution(
                diagnostics=(
                    EvidenceDiagnostic(
                        "message",
                        "message_11",
                        "unresolved_required_debit_blocks",
                        ("message_11",),
                        blocks_downstream=True,
                    ),
                ),
                blocks_downstream=True,
            ),
        )
        decisions = _decisions_by_subject(result)
        decision = decisions[("diagnostic", "message_11")]
        self.assertEqual(decision.disposition, "unresolved")
        self.assertEqual(decision.reason_code, "unresolved_required_debit_blocks")
        self.assertEqual(decision.source_ids, ("message_11",))


class EventAmountResolutionTests(unittest.TestCase):
    """Phase 2: populated amounts win; blank amounts fill only once."""

    def test_event_amount_fact_fills_blank_scheduled_debit(self) -> None:
        # request_16 / event_1442 shape: scheduled debit with blank amount
        # filled by exactly one targeted EVENT_AMOUNT fact.
        case = _case(
            messages=(),
            images=(_image("image_02"),),
            events=(
                _event(
                    "event_1442",
                    event_type=EventType.EXPENSE,
                    category="rent",
                    direction=Direction.DEBIT,
                    amount=None,
                    event_date="2026-01-11",
                    settlement_date="2026-01-16",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        fact = _fact(
            fact_id="image_02::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_02"),),
            target_event_id="event_1442",
            amount=Decimal("100000"),
            currency=CurrencyCode.ZAR,
        )
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(len(result.dated_cash_effects), 1)
        effect = result.dated_cash_effects[0]
        self.assertEqual(effect.record_id, "event:event_1442")
        self.assertEqual(effect.amount_home, Decimal("100000"))
        self.assertEqual(effect.direction, Direction.DEBIT)
        self.assertEqual(effect.effect_date, _d("2026-01-16"))
        self.assertEqual(effect.source_fact_ids, ("image_02::event_amount",))

    def test_multiple_event_amount_facts_fail_closed(self) -> None:
        case = _case(
            images=(_image("image_02"), _image("image_03")),
            events=(
                _event(
                    "event_1442",
                    direction=Direction.DEBIT,
                    amount=None,
                    status=EventStatus.SCHEDULED,
                    settlement_date="2026-01-20",
                ),
            ),
        )
        fact_one = _fact(
            fact_id="image_02::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_02"),),
            target_event_id="event_1442",
            amount=Decimal("100"),
            currency=CurrencyCode.ZAR,
        )
        fact_two = _fact(
            fact_id="image_03::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_03"),),
            target_event_id="event_1442",
            amount=Decimal("200"),
            currency=CurrencyCode.ZAR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact_one, fact_two)))
        self.assertEqual(ctx.exception.reason_code, "event_amount_conflict")

    def test_event_amount_currency_mismatch_fails_closed(self) -> None:
        case = _case(
            images=(_image("image_02"),),
            events=(
                _event(
                    "event_1442",
                    currency=CurrencyCode.ZAR,
                    direction=Direction.DEBIT,
                    amount=None,
                    settlement_date="2026-01-16",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        fact = _fact(
            fact_id="image_02::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_02"),),
            target_event_id="event_1442",
            amount=Decimal("100"),
            currency=CurrencyCode.EUR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "event_amount_currency_mismatch")

    def test_event_amount_fact_on_populated_event_fails_closed(self) -> None:
        case = _case(
            images=(_image("image_02"),),
            events=(_event("event_A", amount=Decimal("100")),),
        )
        fact = _fact(
            fact_id="image_02::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_02"),),
            target_event_id="event_A",
            amount=Decimal("100"),
            currency=CurrencyCode.ZAR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "event_amount_target_not_blank")

    def test_missing_required_scheduled_debit_amount_blocks(self) -> None:
        # A scheduled required debit without a grounded amount invents no
        # value and blocks downstream certification.
        case = _case(
            events=(
                _event(
                    "event_noamount",
                    direction=Direction.DEBIT,
                    amount=None,
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertTrue(result.blocks_downstream)
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        decision = decisions[("event", "event_noamount")]
        self.assertEqual(decision.disposition, "unresolved")
        self.assertEqual(decision.reason_code, "missing_required_debit_amount")

    def test_missing_settled_history_amount_does_not_block(self) -> None:
        # request_19 / event_1700 / image_04 boundary: a settled historical
        # row without an accepted amount is excluded from numeric history,
        # stays unresolved, and does not replay a debit or block the request.
        case = _case(
            images=(_image("image_04"),),
            events=(
                _event(
                    "event_1700",
                    event_type=EventType.EXPENSE,
                    direction=Direction.DEBIT,
                    amount=None,
                    event_date="2024-09-03",
                    settlement_date="2024-09-03",
                ),
            ),
        )
        result = normalize_case_events(
            case,
            _resolution(
                diagnostics=(
                    EvidenceDiagnostic(
                        "image",
                        "image_04",
                        "unavailable_image_review",
                        ("image_04",),
                    ),
                ),
            ),
        )
        self.assertFalse(result.blocks_downstream)
        self.assertEqual(result.historical_cash, ())
        self.assertEqual(result.opening_reserves, ())
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        event_decision = decisions[("event", "event_1700")]
        self.assertEqual(event_decision.disposition, "unresolved")
        self.assertEqual(event_decision.reason_code, "missing_settled_history_amount")
        image_decision = decisions[("diagnostic", "image_04")]
        self.assertEqual(image_decision.reason_code, "unavailable_image_review")

    def test_settled_blank_amount_filled_by_one_event_amount_fact(self) -> None:
        # Accepted settled-fill contract (e.g. image_06 -> event_3051): a
        # settled historical debit with a blank amount may be filled by
        # exactly one targeted, currency-matching EVENT_AMOUNT fact, emitted
        # once as a historical record at the directed settlement-date rate.
        case = _case(
            images=(_image("image_06"),),
            events=(
                _event(
                    "event_3051",
                    event_type=EventType.EXPENSE,
                    category="dining",
                    direction=Direction.DEBIT,
                    amount=None,
                    currency=CurrencyCode.USD,
                    event_date="2025-09-28",
                    settlement_date="2025-10-01",
                    status=EventStatus.SETTLED,
                ),
            ),
            rates=(
                ExchangeRateRecord(
                    rate_date=_d("2025-10-01"),
                    from_currency=CurrencyCode.USD,
                    to_currency=CurrencyCode.ZAR,
                    rate=Decimal("18.5"),
                ),
            ),
            profile=_profile(home_currency=CurrencyCode.ZAR),
        )
        fact = _fact(
            fact_id="image_06::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_06"),),
            target_event_id="event_3051",
            amount=Decimal("10"),
            currency=CurrencyCode.USD,
        )
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertFalse(result.blocks_downstream)
        self.assertEqual(len(result.historical_cash), 1)
        record = result.historical_cash[0]
        self.assertEqual(record.record_id, "event:event_3051")
        self.assertEqual(record.amount_home, Decimal("185.0"))
        self.assertEqual(record.settlement_date, _d("2025-10-01"))
        self.assertEqual(record.source_fact_ids, ("image_06::event_amount",))
        self.assertEqual(result.opening_reserves, ())
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        event_decision = decisions[("event", "event_3051")]
        self.assertEqual(event_decision.disposition, "included")
        self.assertEqual(event_decision.reason_code, "historical_already_in_opening")
        fact_decision = decisions[("fact", "image_06::event_amount")]
        self.assertEqual(fact_decision.disposition, "included")
        self.assertEqual(fact_decision.reason_code, "event_amount_fill")

    def test_settled_investment_fill_matches_non_fill_reason_codes(self) -> None:
        # The lifecycle reason code must not depend on the amount's provenance
        # (event amount vs EVENT_AMOUNT fill fact): blank-amount settled
        # investment purchase/sale fills use the same reason codes as the
        # populated-amount siblings.
        for event_type, expected_reason in (
            (EventType.INVESTMENT_PURCHASE, "investment_purchase_cash"),
            (EventType.INVESTMENT_SALE, "investment_sale_cash"),
        ):
            with self.subTest(event_type=event_type):
                direction = (
                    Direction.DEBIT
                    if event_type is EventType.INVESTMENT_PURCHASE
                    else Direction.CREDIT
                )
                filled_case = _case(
                    images=(_image("image_06"),),
                    events=(
                        _event(
                            "event_inv",
                            event_type=event_type,
                            category="investments",
                            direction=direction,
                            amount=None,
                            settlement_date="2025-10-01",
                            status=EventStatus.SETTLED,
                        ),
                    ),
                )
                fact = _fact(
                    fact_id="image_06::event_amount",
                    fact_type=EvidenceFactType.EVENT_AMOUNT,
                    sources=(SourceReference("image", "image_06"),),
                    target_event_id="event_inv",
                    amount=Decimal("50"),
                    currency=CurrencyCode.ZAR,
                )
                filled = normalize_case_events(filled_case, _resolution(facts=(fact,)))
                populated_case = _case(
                    events=(
                        _event(
                            "event_inv",
                            event_type=event_type,
                            category="investments",
                            direction=direction,
                            amount=Decimal("50"),
                            settlement_date="2025-10-01",
                            status=EventStatus.SETTLED,
                        ),
                    ),
                )
                populated = normalize_case_events(populated_case, _resolution())
                filled_decision = _decisions_by_subject(filled)[("event", "event_inv")]
                populated_decision = _decisions_by_subject(populated)[
                    ("event", "event_inv")
                ]
                self.assertEqual(filled_decision.reason_code, expected_reason)
                self.assertEqual(
                    filled_decision.reason_code, populated_decision.reason_code
                )

    def test_settled_blank_amount_with_two_facts_fails_closed(self) -> None:
        case = _case(
            images=(_image("image_06"), _image("image_07")),
            events=(
                _event(
                    "event_3051",
                    direction=Direction.DEBIT,
                    amount=None,
                    settlement_date="2025-10-01",
                    status=EventStatus.SETTLED,
                ),
            ),
        )
        fact_one = _fact(
            fact_id="image_06::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_06"),),
            target_event_id="event_3051",
            amount=Decimal("10"),
            currency=CurrencyCode.ZAR,
        )
        fact_two = _fact(
            fact_id="image_07::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_07"),),
            target_event_id="event_3051",
            amount=Decimal("20"),
            currency=CurrencyCode.ZAR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact_one, fact_two)))
        self.assertEqual(ctx.exception.reason_code, "event_amount_conflict")

    def test_settled_blank_amount_currency_mismatch_fails_closed(self) -> None:
        case = _case(
            images=(_image("image_06"),),
            events=(
                _event(
                    "event_3051",
                    currency=CurrencyCode.ZAR,
                    direction=Direction.DEBIT,
                    amount=None,
                    settlement_date="2025-10-01",
                    status=EventStatus.SETTLED,
                ),
            ),
        )
        fact = _fact(
            fact_id="image_06::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_06"),),
            target_event_id="event_3051",
            amount=Decimal("10"),
            currency=CurrencyCode.EUR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "event_amount_currency_mismatch")

    def test_settled_populated_amount_with_fact_fails_closed(self) -> None:
        case = _case(
            images=(_image("image_06"),),
            events=(
                _event(
                    "event_3051",
                    amount=Decimal("50"),
                    settlement_date="2025-10-01",
                    status=EventStatus.SETTLED,
                ),
            ),
        )
        fact = _fact(
            fact_id="image_06::event_amount",
            fact_type=EvidenceFactType.EVENT_AMOUNT,
            sources=(SourceReference("image", "image_06"),),
            target_event_id="event_3051",
            amount=Decimal("10"),
            currency=CurrencyCode.ZAR,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "event_amount_target_not_blank")


class LifecycleMatrixTests(unittest.TestCase):
    """Phase 4: one decision per source ownership for every matrix row."""

    def test_settled_cash_becomes_one_historical_record(self) -> None:
        case = _case(events=(_event("event_hist", amount=Decimal("250")),))
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.historical_cash), 1)
        record = result.historical_cash[0]
        self.assertEqual(record.record_id, "event:event_hist")
        self.assertEqual(record.amount_home, Decimal("250"))
        self.assertEqual(record.direction, Direction.DEBIT)
        self.assertEqual(record.settlement_date, _d("2025-12-16"))
        self.assertEqual(result.opening_reserves, ())
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        self.assertEqual(
            decisions[("event", "event_hist")].reason_code,
            "historical_already_in_opening",
        )

    def test_pending_debit_becomes_one_reserve_never_second_debit(self) -> None:
        # request_01 / event_102 shape: pending debit reserves once; a
        # possible-duplicate description never releases or duplicates it.
        case = _case(
            events=(
                _event(
                    "event_102",
                    direction=Direction.DEBIT,
                    amount=Decimal("567.6"),
                    event_date="2026-01-02",
                    settlement_date="2026-01-05",
                    status=EventStatus.PENDING,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.opening_reserves), 1)
        reserve = result.opening_reserves[0]
        self.assertEqual(reserve.record_id, "event:event_102")
        self.assertEqual(reserve.amount_home, Decimal("567.6"))
        self.assertEqual(reserve.reserved_on, _d("2026-01-10"))
        self.assertEqual(reserve.settlement_date, _d("2026-01-05"))
        self.assertEqual(result.dated_cash_effects, ())
        self.assertEqual(result.historical_cash, ())
        decisions = _decisions_by_subject(result)
        self.assertEqual(
            decisions[("event", "event_102")].reason_code,
            "pending_debit_reserved",
        )

    def test_possible_duplicate_pending_debit_still_one_reserve(self) -> None:
        # event_12709 shape: possible-duplicate pending debit linked to a
        # settled original remains one reserve; the link proves nothing.
        case = _case(
            events=(
                _event(
                    "event_12708",
                    direction=Direction.DEBIT,
                    amount=Decimal("134.75"),
                    event_date="2025-03-26",
                    settlement_date="2025-03-27",
                    status=EventStatus.SETTLED,
                ),
                _event(
                    "event_12709",
                    direction=Direction.DEBIT,
                    amount=Decimal("134.75"),
                    event_date="2025-04-06",
                    settlement_date="2025-04-10",
                    status=EventStatus.PENDING,
                    linked_event_id="event_12708",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.historical_cash), 1)
        self.assertEqual(len(result.opening_reserves), 1)
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        self.assertEqual(
            decisions[("event", "event_12709")].reason_code,
            "possible_duplicate_retained",
        )

    def test_pending_credit_adds_no_cash(self) -> None:
        # request_20 / event_1785 shape: pending refund credit is unavailable
        # even with a passed predicted settlement date.
        case = _case(
            messages=(_message("message_14"),),
            events=(
                _event(
                    "event_1784",
                    direction=Direction.DEBIT,
                    amount=Decimal("8640"),
                    event_date="2025-12-14",
                    settlement_date="2025-12-15",
                    status=EventStatus.SETTLED,
                ),
                _event(
                    "event_1785",
                    event_type=EventType.REFUND,
                    direction=Direction.CREDIT,
                    amount=Decimal("8640"),
                    event_date="2026-02-04",
                    settlement_date="2026-02-14",
                    status=EventStatus.PENDING,
                    linked_event_id="event_1784",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.historical_cash), 1)
        self.assertEqual(result.historical_cash[0].record_id, "event:event_1784")
        self.assertEqual(result.opening_reserves, ())
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        self.assertEqual(
            decisions[("event", "event_1785")].reason_code,
            "pending_credit_unavailable",
        )

    def test_scheduled_debit_becomes_dated_debit(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_sched_debit",
                    direction=Direction.DEBIT,
                    amount=Decimal("75"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.dated_cash_effects), 1)
        effect = result.dated_cash_effects[0]
        self.assertEqual(effect.direction, Direction.DEBIT)
        self.assertEqual(effect.amount_home, Decimal("75"))
        self.assertEqual(effect.effect_date, _d("2026-02-01"))
        decisions = _decisions_by_subject(result)
        self.assertEqual(decisions[("event", "event_sched_debit")].reason_code, "scheduled_debit")

    def test_scheduled_confirmed_income_becomes_dated_credit(self) -> None:
        # request_01 / event_103 shape: credit once at settlement.
        case = _case(
            events=(
                _event(
                    "event_103",
                    event_type=EventType.INCOME,
                    category="salary",
                    direction=Direction.CREDIT,
                    amount=Decimal("23320"),
                    event_date="2026-03-15",
                    settlement_date="2026-03-15",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.dated_cash_effects), 1)
        effect = result.dated_cash_effects[0]
        self.assertEqual(effect.direction, Direction.CREDIT)
        self.assertEqual(effect.amount_home, Decimal("23320"))
        self.assertEqual(effect.effect_date, _d("2026-03-15"))
        decisions = _decisions_by_subject(result)
        self.assertEqual(decisions[("event", "event_103")].reason_code, "scheduled_credit")

    def test_failed_and_cancelled_rows_have_no_cash_effect(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_438",
                    direction=Direction.DEBIT,
                    amount=Decimal("389.4"),
                    settlement_date="2025-11-04",
                    status=EventStatus.FAILED,
                ),
                _event(
                    "event_100",
                    direction=Direction.DEBIT,
                    amount=Decimal("816.2"),
                    settlement_date="2024-02-16",
                    status=EventStatus.CANCELLED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(result.historical_cash, ())
        self.assertEqual(result.opening_reserves, ())
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        self.assertEqual(decisions[("event", "event_438")].reason_code, "failed_no_cash")
        self.assertEqual(decisions[("event", "event_100")].reason_code, "cancelled_no_cash")

    def test_retry_processed_independently_of_failed_predecessor(self) -> None:
        # event_5168 (failed debt payment) plus event_5169 (scheduled retry):
        # the link neither clones nor erases the successor.
        case = _case(
            events=(
                _event(
                    "event_5168",
                    event_type=EventType.DEBT_PAYMENT,
                    direction=Direction.DEBIT,
                    amount=Decimal("350"),
                    settlement_date="2025-12-12",
                    status=EventStatus.FAILED,
                ),
                _event(
                    "event_5169",
                    event_type=EventType.DEBT_PAYMENT,
                    direction=Direction.DEBIT,
                    amount=Decimal("350"),
                    settlement_date="2026-01-12",
                    status=EventStatus.SCHEDULED,
                    linked_event_id="event_5168",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.dated_cash_effects), 1)
        self.assertEqual(result.dated_cash_effects[0].record_id, "event:event_5169")
        self.assertEqual(result.dated_cash_effects[0].amount_home, Decimal("350"))
        decisions = _decisions_by_subject(result)
        self.assertEqual(decisions[("event", "event_5168")].reason_code, "failed_no_cash")
        self.assertEqual(decisions[("event", "event_5169")].reason_code, "scheduled_debit")

    def test_settled_purchase_plus_refund_stays_two_records(self) -> None:
        # event_99 shape: a settled refund is its own historical credit; a
        # link alone never nets the pair.
        case = _case(
            events=(
                _event(
                    "event_98",
                    direction=Direction.DEBIT,
                    amount=Decimal("700"),
                    settlement_date="2024-01-27",
                    status=EventStatus.SETTLED,
                ),
                _event(
                    "event_99",
                    event_type=EventType.REFUND,
                    direction=Direction.CREDIT,
                    amount=Decimal("583"),
                    settlement_date="2024-01-29",
                    status=EventStatus.SETTLED,
                    linked_event_id="event_98",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.historical_cash), 2)
        amounts = sorted(record.amount_home for record in result.historical_cash)
        self.assertEqual(amounts, [Decimal("583"), Decimal("700")])
        directions = sorted(record.direction.value for record in result.historical_cash)
        self.assertEqual(directions, ["credit", "debit"])

    def test_settled_refund_after_request_date_fails_closed(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_late",
                    event_type=EventType.REFUND,
                    direction=Direction.CREDIT,
                    amount=Decimal("583"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SETTLED,
                ),
            ),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "inconsistent_settled_boundary")

    def test_overdue_scheduled_row_fails_closed(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_overdue",
                    direction=Direction.DEBIT,
                    amount=Decimal("100"),
                    settlement_date="2025-01-01",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "overdue_scheduled_unrouted")

    def test_investment_purchase_follows_status(self) -> None:
        settled_case = _case(
            events=(
                _event(
                    "event_1855",
                    event_type=EventType.INVESTMENT_PURCHASE,
                    direction=Direction.DEBIT,
                    amount=Decimal("676.8"),
                    event_date="2025-12-29",
                    settlement_date="2025-12-29",
                    status=EventStatus.SETTLED,
                ),
            ),
        )
        settled_result = normalize_case_events(settled_case, _resolution())
        self.assertEqual(len(settled_result.historical_cash), 1)
        decisions = _decisions_by_subject(settled_result)
        self.assertEqual(
            decisions[("event", "event_1855")].reason_code,
            "investment_purchase_cash",
        )

    def test_investment_valuation_is_never_cash(self) -> None:
        # request_21 / event_1856 shape at any status.
        case = _case(
            events=(
                _event(
                    "event_1856",
                    event_type=EventType.INVESTMENT_VALUATION,
                    direction=Direction.NON_CASH,
                    amount=Decimal("270.72"),
                    event_date="2026-04-01",
                    settlement_date=None,
                    status=EventStatus.UNREALIZED,
                    linked_event_id="event_1855",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(result.historical_cash, ())
        self.assertEqual(result.opening_reserves, ())
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        decision = decisions[("event", "event_1856")]
        self.assertEqual(decision.disposition, "excluded")
        self.assertEqual(decision.reason_code, "unrealized_non_cash")

    def test_settled_investment_sale_is_one_cash_credit(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_11129",
                    event_type=EventType.INVESTMENT_SALE,
                    direction=Direction.CREDIT,
                    amount=Decimal("13062500"),
                    settlement_date="2024-12-01",
                    status=EventStatus.SETTLED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.historical_cash), 1)
        self.assertEqual(result.historical_cash[0].direction, Direction.CREDIT)
        decisions = _decisions_by_subject(result)
        self.assertEqual(
            decisions[("event", "event_11129")].reason_code,
            "investment_sale_cash",
        )

    def test_work_expense_and_pending_reimbursement_stay_separate(self) -> None:
        # Reimbursement classification follows status/direction only: a
        # pending reimbursement credit adds no cash while the settled expense
        # stays historical.
        case = _case(
            events=(
                _event(
                    "event_expense",
                    category="work_expense",
                    direction=Direction.DEBIT,
                    amount=Decimal("300"),
                    settlement_date="2026-01-01",
                    status=EventStatus.SETTLED,
                ),
                _event(
                    "event_reimb",
                    category="work_expense",
                    direction=Direction.CREDIT,
                    amount=Decimal("300"),
                    settlement_date="2026-02-01",
                    status=EventStatus.PENDING,
                    linked_event_id="event_expense",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.historical_cash), 1)
        self.assertEqual(result.dated_cash_effects, ())
        self.assertEqual(result.opening_reserves, ())
        decisions = _decisions_by_subject(result)
        self.assertEqual(
            decisions[("event", "event_reimb")].reason_code,
            "pending_credit_unavailable",
        )

    def test_scheduled_reimbursement_is_dated_credit(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_reimb_sched",
                    category="work_expense",
                    direction=Direction.CREDIT,
                    amount=Decimal("300"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.dated_cash_effects), 1)
        self.assertEqual(result.dated_cash_effects[0].direction, Direction.CREDIT)
        decisions = _decisions_by_subject(result)
        self.assertEqual(decisions[("event", "event_reimb_sched")].reason_code, "scheduled_credit")


class TransferPairTests(unittest.TestCase):
    """Only a fully validated transfer pair is neutral; links alone never net."""

    def _transfer_fact(self, target_event_id: str) -> EvidenceFact:
        return _fact(
            fact_id="message_13::internal_transfer_pair",
            fact_type=EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            sources=(SourceReference("message", "message_13"),),
            target_event_id=target_event_id,
        )

    def test_validated_pair_is_neutral(self) -> None:
        case = _case(
            messages=(_message("message_13"),),
            events=(
                _event(
                    "event_transfer_out",
                    direction=Direction.DEBIT,
                    amount=Decimal("500"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
                _event(
                    "event_transfer_in",
                    direction=Direction.CREDIT,
                    amount=Decimal("500"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                    linked_event_id="event_transfer_out",
                ),
            ),
        )
        fact = self._transfer_fact("event_transfer_out")
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        for event_id in ("event_transfer_out", "event_transfer_in"):
            decision = decisions[("event", event_id)]
            self.assertEqual(decision.disposition, "excluded")
            self.assertEqual(decision.reason_code, "internal_transfer_neutral")
        fact_decision = decisions[("fact", fact.fact_id)]
        self.assertEqual(fact_decision.disposition, "included")

    def test_validated_pair_neutral_across_all_statuses(self) -> None:
        # Status cross-product: a fully validated pair neutralizes to zero
        # records and excluded/internal_transfer_neutral decisions for settled,
        # pending, and scheduled members alike.
        for status in (EventStatus.SETTLED, EventStatus.PENDING, EventStatus.SCHEDULED):
            with self.subTest(status=status):
                settlement = "2025-10-01" if status is EventStatus.SETTLED else "2026-02-01"
                case = _case(
                    messages=(_message("message_13"),),
                    events=(
                        _event(
                            "event_transfer_out",
                            direction=Direction.DEBIT,
                            amount=Decimal("500"),
                            settlement_date=settlement,
                            status=status,
                        ),
                        _event(
                            "event_transfer_in",
                            direction=Direction.CREDIT,
                            amount=Decimal("500"),
                            settlement_date=settlement,
                            status=status,
                            linked_event_id="event_transfer_out",
                        ),
                    ),
                )
                fact = self._transfer_fact("event_transfer_out")
                result = normalize_case_events(case, _resolution(facts=(fact,)))
                self.assertEqual(result.historical_cash, ())
                self.assertEqual(result.opening_reserves, ())
                self.assertEqual(result.dated_cash_effects, ())
                decisions = _decisions_by_subject(result)
                for event_id in ("event_transfer_out", "event_transfer_in"):
                    decision = decisions[("event", event_id)]
                    self.assertEqual(decision.disposition, "excluded")
                    self.assertEqual(
                        decision.reason_code, "internal_transfer_neutral"
                    )
                self.assertEqual(
                    decisions[("fact", fact.fact_id)].disposition, "included"
                )

    def test_unmatched_pair_leaves_roles_unnetted_across_statuses(self) -> None:
        # Unmatched/ambiguous pairs never net: each member keeps its own
        # lifecycle role regardless of status.
        for status in (EventStatus.SETTLED, EventStatus.PENDING, EventStatus.SCHEDULED):
            with self.subTest(status=status):
                settlement = "2025-10-01" if status is EventStatus.SETTLED else "2026-02-01"
                case = _case(
                    messages=(_message("message_13"),),
                    events=(
                        _event(
                            "event_transfer_out",
                            direction=Direction.DEBIT,
                            amount=Decimal("500"),
                            settlement_date=settlement,
                            status=status,
                        ),
                        _event(
                            "event_transfer_in",
                            direction=Direction.CREDIT,
                            amount=Decimal("400"),
                            settlement_date=settlement,
                            status=status,
                            linked_event_id="event_transfer_out",
                        ),
                    ),
                )
                fact = self._transfer_fact("event_transfer_out")
                result = normalize_case_events(case, _resolution(facts=(fact,)))
                decisions = _decisions_by_subject(result)
                # No pair member may be marked neutral when no validated pair
                # exists; the fact is unresolved and no role is stripped.
                fact_decision = decisions[("fact", fact.fact_id)]
                self.assertEqual(fact_decision.disposition, "unresolved")
                for event_id in ("event_transfer_out", "event_transfer_in"):
                    decision = decisions[("event", event_id)]
                    self.assertNotEqual(
                        decision.reason_code, "internal_transfer_neutral"
                    )

    def test_unmatched_pair_leaves_events_unresolved_without_netting(self) -> None:
        case = _case(
            messages=(_message("message_13"),),
            events=(
                _event(
                    "event_transfer_out",
                    direction=Direction.DEBIT,
                    amount=Decimal("500"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
                _event(
                    "event_transfer_in",
                    direction=Direction.CREDIT,
                    amount=Decimal("400"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                    linked_event_id="event_transfer_out",
                ),
            ),
        )
        fact = self._transfer_fact("event_transfer_out")
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        # Each event keeps its own lifecycle effect; the debit stays a dated
        # debit and nothing is netted away.
        self.assertEqual(len(result.dated_cash_effects), 2)
        decisions = _decisions_by_subject(result)
        fact_decision = decisions[("fact", fact.fact_id)]
        self.assertEqual(fact_decision.disposition, "unresolved")
        self.assertEqual(fact_decision.reason_code, "transfer_pair_unmatched")

    def test_link_without_transfer_fact_never_nets(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_transfer_out",
                    direction=Direction.DEBIT,
                    amount=Decimal("500"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
                _event(
                    "event_transfer_in",
                    direction=Direction.CREDIT,
                    amount=Decimal("500"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                    linked_event_id="event_transfer_out",
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(len(result.dated_cash_effects), 2)


class FactOnlyCreditTests(unittest.TestCase):
    """Fact-only confirmed future credit becomes one dated credit."""

    def test_fact_only_confirmed_future_credit(self) -> None:
        # request_15 / message_11 shape: one dated credit from the structured
        # fact amount, currency, and settlement date; no EventRecord synthesis.
        case = _case(
            messages=(_message("message_11"),),
            profile=_profile(home_currency=CurrencyCode.EUR),
        )
        fact = _fact(
            fact_id="message_11::confirmed_future_credit",
            fact_type=EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            sources=(SourceReference("message", "message_11"),),
            amount=Decimal("1661"),
            currency=CurrencyCode.EUR,
            settlement_date=_d("2026-01-15"),
        )
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(len(result.dated_cash_effects), 1)
        effect = result.dated_cash_effects[0]
        self.assertEqual(effect.record_id, "fact:message_11::confirmed_future_credit")
        self.assertEqual(effect.amount_home, Decimal("1661"))
        self.assertEqual(effect.direction, Direction.CREDIT)
        self.assertEqual(effect.effect_date, _d("2026-01-15"))
        self.assertEqual(effect.source_event_ids, ())
        self.assertEqual(effect.source_fact_ids, ("message_11::confirmed_future_credit",))
        decisions = _decisions_by_subject(result)
        fact_decision = decisions[("fact", fact.fact_id)]
        self.assertEqual(fact_decision.disposition, "included")
        self.assertEqual(fact_decision.reason_code, "fact_confirmed_future_credit")

    def test_fact_only_foreign_credit_requires_settlement_date(self) -> None:
        case = _case(messages=(_message("message_11"),))
        fact = _fact(
            fact_id="message_11::confirmed_future_credit",
            fact_type=EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            sources=(SourceReference("message", "message_11"),),
            amount=Decimal("1661"),
            currency=CurrencyCode.EUR,
            settlement_date=None,
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(ctx.exception.reason_code, "fx_settlement_date_missing")


class AmendmentDecisionTests(unittest.TestCase):
    """Recurrence amendments carry no direct cash effect in WP-04."""

    def _series_amendment_case(self) -> RequestCase:
        return _case(
            messages=(_message("message_08"),),
            events=(
                _event(
                    "event_941",
                    event_type=EventType.INCOME,
                    category="salary",
                    direction=Direction.CREDIT,
                    amount=Decimal("38760000"),
                    currency=CurrencyCode.ZAR,
                    settlement_date="2025-06-15",
                    status=EventStatus.SETTLED,
                ),
            ),
        )

    def test_amendment_fact_is_excluded_without_touching_history(self) -> None:
        case = self._series_amendment_case()
        fact = _fact(
            fact_id="message_08::recurring_amount_amendment",
            fact_type=EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            sources=(SourceReference("message", "message_08"),),
            target_event_id="event_941",
            amount=Decimal("38760000"),
            currency=CurrencyCode.ZAR,
            effective_date=_d("2025-08-15"),
        )
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        self.assertEqual(len(result.historical_cash), 1)
        self.assertEqual(result.historical_cash[0].amount_home, Decimal("38760000"))
        self.assertEqual(result.dated_cash_effects, ())
        decisions = _decisions_by_subject(result)
        fact_decision = decisions[("fact", fact.fact_id)]
        self.assertEqual(fact_decision.disposition, "excluded")
        self.assertEqual(fact_decision.reason_code, "recurrence_amendment_no_direct_cash")


class ExactFXTests(unittest.TestCase):
    """Exact directed settlement-date FX with no rounding or chaining."""

    def _usd_case(self, event_id: str = "event_2288") -> RequestCase:
        return _case(
            events=(
                _event(
                    event_id,
                    event_type=EventType.INCOME,
                    category="salary",
                    direction=Direction.CREDIT,
                    amount=Decimal("1800"),
                    currency=CurrencyCode.USD,
                    event_date="2024-03-15",
                    settlement_date="2024-03-15",
                    status=EventStatus.SCHEDULED,
                ),
            ),
            rates=(
                ExchangeRateRecord(
                    rate_date=_d("2024-03-15"),
                    from_currency=CurrencyCode.USD,
                    to_currency=CurrencyCode.IDR,
                    rate=Decimal("15833.33"),
                ),
            ),
            profile=_profile(home_currency=CurrencyCode.IDR),
            request=_request(request_date="2024-03-14"),
        )

    def test_request_25_oracle_is_exact(self) -> None:
        result = normalize_case_events(self._usd_case(), _resolution())
        self.assertEqual(len(result.dated_cash_effects), 1)
        effect = result.dated_cash_effects[0]
        self.assertEqual(effect.amount_home, Decimal("28499994.00"))
        self.assertEqual(effect.amount_home, Decimal("1800") * Decimal("15833.33"))

    def test_wrong_date_rate_is_never_used(self) -> None:
        case = self._usd_case()
        case = RequestCase(
            request=case.request,
            profile=case.profile,
            events=case.events,
            payment_options=(),
            messages=(),
            images=(),
            relevant_rates=(
                ExchangeRateRecord(
                    rate_date=_d("2024-03-14"),
                    from_currency=CurrencyCode.USD,
                    to_currency=CurrencyCode.IDR,
                    rate=Decimal("15833.33"),
                ),
            ),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "fx_rate_missing")

    def test_reverse_only_rate_is_never_inverted(self) -> None:
        case = self._usd_case()
        case = RequestCase(
            request=case.request,
            profile=case.profile,
            events=case.events,
            payment_options=(),
            messages=(),
            images=(),
            relevant_rates=(
                ExchangeRateRecord(
                    rate_date=_d("2024-03-15"),
                    from_currency=CurrencyCode.IDR,
                    to_currency=CurrencyCode.USD,
                    rate=Decimal("0.0000632"),
                ),
            ),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "fx_rate_missing")

    def test_conflicting_duplicate_rate_fails_closed(self) -> None:
        case = self._usd_case()
        case = RequestCase(
            request=case.request,
            profile=case.profile,
            events=case.events,
            payment_options=(),
            messages=(),
            images=(),
            relevant_rates=(
                ExchangeRateRecord(
                    rate_date=_d("2024-03-15"),
                    from_currency=CurrencyCode.USD,
                    to_currency=CurrencyCode.IDR,
                    rate=Decimal("15833.33"),
                ),
                ExchangeRateRecord(
                    rate_date=_d("2024-03-15"),
                    from_currency=CurrencyCode.USD,
                    to_currency=CurrencyCode.IDR,
                    rate=Decimal("15833.34"),
                ),
            ),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "fx_rate_conflict")

    def test_invalid_rate_fails_closed(self) -> None:
        case = self._usd_case()
        case = RequestCase(
            request=case.request,
            profile=case.profile,
            events=case.events,
            payment_options=(),
            messages=(),
            images=(),
            relevant_rates=(
                ExchangeRateRecord(
                    rate_date=_d("2024-03-15"),
                    from_currency=CurrencyCode.USD,
                    to_currency=CurrencyCode.IDR,
                    rate=Decimal("0"),
                ),
            ),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "fx_rate_invalid")

    def test_foreign_record_without_settlement_date_fails_closed(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_nodate",
                    direction=Direction.DEBIT,
                    amount=Decimal("100"),
                    currency=CurrencyCode.USD,
                    settlement_date=None,
                    status=EventStatus.SCHEDULED,
                ),
            ),
            profile=_profile(home_currency=CurrencyCode.IDR),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "fx_settlement_date_missing")

    def test_home_currency_needs_no_rate(self) -> None:
        case = _case(events=(_event("event_hist", amount=Decimal("250")),))
        result = normalize_case_events(case, _resolution())
        self.assertEqual(result.historical_cash[0].amount_home, Decimal("250"))

    def test_error_is_atomic_no_partial_result(self) -> None:
        # A missing FX rate on the second event must not surface any
        # normalized collection content.
        case = _case(
            events=(
                _event(
                    "event_ok",
                    amount=Decimal("10"),
                    currency=CurrencyCode.IDR,
                    settlement_date="2026-01-05",
                    status=EventStatus.SETTLED,
                ),
                _event(
                    "event_bad",
                    direction=Direction.DEBIT,
                    amount=Decimal("10"),
                    currency=CurrencyCode.USD,
                    settlement_date="2026-01-20",
                    status=EventStatus.SCHEDULED,
                ),
            ),
            profile=_profile(home_currency=CurrencyCode.IDR),
        )
        with self.assertRaises(EventNormalizationError) as ctx:
            normalize_case_events(case, _resolution())
        self.assertEqual(ctx.exception.reason_code, "fx_rate_missing")
        self.assertIn("event_bad", ctx.exception.source_ids)


class ConservationTests(unittest.TestCase):
    """Phase 6: no silently unowned source and no duplicate cash roles."""

    def test_every_event_and_fact_has_one_decision(self) -> None:
        case = _case(
            messages=(_message("message_11"), _message("message_14")),
            events=(
                _event(
                    "event_1784",
                    direction=Direction.DEBIT,
                    amount=Decimal("8640"),
                    settlement_date="2025-12-15",
                    status=EventStatus.SETTLED,
                ),
                _event(
                    "event_1785",
                    event_type=EventType.REFUND,
                    direction=Direction.CREDIT,
                    amount=Decimal("8640"),
                    settlement_date="2026-02-14",
                    status=EventStatus.PENDING,
                    linked_event_id="event_1784",
                ),
            ),
        )
        fact = _fact(
            fact_id="message_11::confirmed_future_credit",
            fact_type=EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            sources=(SourceReference("message", "message_11"),),
            amount=Decimal("1661"),
            currency=CurrencyCode.ZAR,
            settlement_date=_d("2026-01-15"),
        )
        result = normalize_case_events(case, _resolution(facts=(fact,)))
        decisions = _decisions_by_subject(result)
        self.assertIn(("event", "event_1784"), decisions)
        self.assertIn(("event", "event_1785"), decisions)
        self.assertIn(("fact", fact.fact_id), decisions)

    def test_pending_reserve_is_not_duplicated_as_dated_effect(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_102",
                    direction=Direction.DEBIT,
                    amount=Decimal("567.6"),
                    settlement_date="2024-03-05",
                    status=EventStatus.PENDING,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        reserve_ids = {reserve.record_id for reserve in result.opening_reserves}
        effect_ids = {effect.record_id for effect in result.dated_cash_effects}
        history_ids = {record.record_id for record in result.historical_cash}
        self.assertFalse(reserve_ids & effect_ids)
        self.assertFalse(reserve_ids & history_ids)
        self.assertEqual(len(reserve_ids), len(result.opening_reserves))
        self.assertEqual(len(history_ids), len(result.historical_cash))
        self.assertEqual(len(effect_ids), len(result.dated_cash_effects))

    def test_order_preserved_within_collections(self) -> None:
        case = _case(
            events=(
                _event(
                    "event_a",
                    direction=Direction.DEBIT,
                    amount=Decimal("10"),
                    settlement_date="2026-02-01",
                    status=EventStatus.SCHEDULED,
                ),
                _event(
                    "event_b",
                    direction=Direction.DEBIT,
                    amount=Decimal("20"),
                    settlement_date="2026-02-02",
                    status=EventStatus.SCHEDULED,
                ),
            ),
        )
        result = normalize_case_events(case, _resolution())
        self.assertEqual(
            [effect.record_id for effect in result.dated_cash_effects],
            ["event:event_a", "event:event_b"],
        )

    def test_result_collections_are_immutable_tuples(self) -> None:
        case = _case(events=(_event("event_hist", amount=Decimal("250")),))
        result = normalize_case_events(case, _resolution())
        self.assertIsInstance(result.historical_cash, tuple)
        self.assertIsInstance(result.opening_reserves, tuple)
        self.assertIsInstance(result.dated_cash_effects, tuple)
        self.assertIsInstance(result.decisions, tuple)


class BlockedCorpusCaseTests(unittest.TestCase):
    """Grounded uncertainty stays conservative across upstream blocking."""

    def test_empty_events_with_upstream_block_stays_blocked(self) -> None:
        case = _case(messages=(_message("message_10"),))
        result = normalize_case_events(
            case,
            _resolution(
                diagnostics=(
                    EvidenceDiagnostic(
                        "message",
                        "message_10",
                        "unresolved_required_debit_blocks",
                        ("message_10",),
                        blocks_downstream=True,
                    ),
                ),
                blocks_downstream=True,
            ),
        )
        self.assertTrue(result.blocks_downstream)
        self.assertEqual(result.dated_cash_effects, ())


class ComponentCorpusTests(unittest.TestCase):
    """Component-level acceptance on accepted participant-facing samples."""

    @classmethod
    def setUpClass(cls) -> None:
        dataset = Path(__file__).resolve().parent.parent / "dataset"
        if not (dataset / "requests.csv").exists():
            raise unittest.SkipTest("dataset not available")
        from buy_or_wait.repository import DatasetRepository

        cls.repo = DatasetRepository.from_directory(dataset)
        cls.case_20 = cls.repo.load_request_case("request_20")
        cls.case_25 = cls.repo.load_request_case("request_25")

    def test_request_20_pending_refund_and_debits(self) -> None:
        from buy_or_wait.evidence import resolve_case_evidence

        resolution = resolve_case_evidence(self.case_20)
        result = normalize_case_events(self.case_20, resolution)
        events = {event.event_id: event for event in self.case_20.events}
        self.assertEqual(
            events["event_1785"].status,
            EventStatus.PENDING,
        )
        reserve_ids = {reserve.record_id for reserve in result.opening_reserves}
        effect_ids = {effect.record_id for effect in result.dated_cash_effects}
        history_ids = {record.record_id for record in result.historical_cash}
        # The pending refund event_1785 is unavailable, never cash.
        self.assertNotIn("event:event_1785", reserve_ids | effect_ids | history_ids)
        # The settled original purchase event_1784 is history only.
        self.assertIn("event:event_1784", history_ids)
        # Pending debits event_1786 (filled by image_05 at 822.05) and
        # event_1787 (4470) each become exactly one reserve.
        self.assertIn("event:event_1786", reserve_ids)
        self.assertIn("event:event_1787", reserve_ids)
        self.assertNotIn("event:event_1786", effect_ids)
        self.assertNotIn("event:event_1787", effect_ids)
        reserve_1786 = next(
            reserve
            for reserve in result.opening_reserves
            if reserve.record_id == "event:event_1786"
        )
        self.assertEqual(reserve_1786.amount_home, Decimal("822.05"))
        reserve_1787 = next(
            reserve
            for reserve in result.opening_reserves
            if reserve.record_id == "event:event_1787"
        )
        self.assertEqual(reserve_1787.amount_home, Decimal("4470"))
        # Every supplied event has exactly one decision.
        decisions = _decisions_by_subject(result)
        for event_id in events:
            self.assertIn(("event", event_id), decisions)

    def test_request_25_salary_fx_oracle(self) -> None:
        from buy_or_wait.evidence import resolve_case_evidence

        resolution = resolve_case_evidence(self.case_25)
        result = normalize_case_events(self.case_25, resolution)
        events = {event.event_id: event for event in self.case_25.events}
        # The five settled USD salary rows are history; event_2288 scheduled
        # converts exactly at its settlement-date directed rate.
        settled_usd = [
            event_id
            for event_id, event in events.items()
            if event.currency is CurrencyCode.USD and event.status is EventStatus.SETTLED
        ]
        self.assertEqual(len(settled_usd), 5)
        history_ids = {record.record_id for record in result.historical_cash}
        for event_id in settled_usd:
            self.assertIn(f"event:{event_id}", history_ids)
        scheduled = next(
            effect
            for effect in result.dated_cash_effects
            if effect.record_id == "event:event_2288"
        )
        self.assertEqual(scheduled.amount_home, Decimal("28499994.00"))
        self.assertEqual(scheduled.direction, Direction.CREDIT)
        self.assertEqual(scheduled.effect_date, _d("2024-03-15"))
        decisions = _decisions_by_subject(result)
        for event_id in events:
            self.assertIn(("event", event_id), decisions)
        self.assertFalse(result.blocks_downstream)


if __name__ == "__main__":
    unittest.main()

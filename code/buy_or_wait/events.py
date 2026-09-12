"""Deterministic lifecycle normalization and exact directed FX for one case.

WP-04 boundary: combine a validated ``RequestCase`` with its accepted
``EvidenceResolution`` into one source-accounted set of historical cash
records, opening debit reserves, and future dated cash effects in the
profile's home currency. Pure, standard library only: no file I/O, no clock,
no provider, no recurrence or forecast work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from buy_or_wait.domain import (
    CurrencyCode,
    Direction,
    EventRecord,
    EventStatus,
    EventType,
    ExchangeRateRecord,
    EvidenceFact,
    EvidenceFactType,
    Flexibility,
    RequestCase,
)
from buy_or_wait.evidence import EvidenceResolution

__all__ = [
    "EventNormalizationError",
    "EventNormalization",
    "NormalizationDecision",
    "NormalizedCashEffect",
    "NormalizedCashRecord",
    "NormalizedReserve",
    "normalize_case_events",
]

_AMENDMENT_FACT_TYPES = frozenset(
    {
        EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
        EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
        EvidenceFactType.RECURRENCE_CONFIRMATION,
        EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
        EvidenceFactType.RECURRENCE_STOP,
        EvidenceFactType.RECURRENCE_RESUME,
        EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
        EvidenceFactType.RECURRING_EXPENSE_NOTICE,
    }
)


class EventNormalizationError(ValueError):
    """Fail-closed error for an unrepresentable input contract.

    Carries a stable ``reason_code`` and safe source IDs only; never raw
    carrier content.
    """

    def __init__(self, reason_code: str, source_ids: tuple[str, ...] = ()) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.source_ids = source_ids


class Disposition(Enum):
    INCLUDED = "included"
    EXCLUDED = "excluded"
    REPLACED = "replaced"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class NormalizationDecision:
    """Complete audit index entry for one source event, fact, or diagnostic."""

    subject_kind: str
    subject_id: str
    disposition: str
    reason_code: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class NormalizedCashRecord:
    """One settled historical cash record already reflected in opening cash."""

    record_id: str
    direction: Direction
    amount_home: Decimal
    home_currency: CurrencyCode
    source_currency: CurrencyCode
    source_amount: Decimal
    settlement_date: date | None
    source_event_ids: tuple[str, ...]
    source_fact_ids: tuple[str, ...]
    category: str
    event_type: EventType
    status: EventStatus
    flexibility: Flexibility
    minimum_allowed_amount: Decimal | None


@dataclass(frozen=True)
class NormalizedReserve:
    """One pending-debit obligation reserved at opening.

    WP-05 reduces spendable cash by ``amount_home`` at opening, then releases
    the reserve while applying the actual debit at ``settlement_date``,
    producing zero additional spendable-cash change.
    """

    record_id: str
    direction: Direction
    amount_home: Decimal
    home_currency: CurrencyCode
    source_currency: CurrencyCode
    source_amount: Decimal
    reserved_on: date
    settlement_date: date | None
    source_event_ids: tuple[str, ...]
    source_fact_ids: tuple[str, ...]
    category: str
    event_type: EventType
    status: EventStatus
    flexibility: Flexibility
    minimum_allowed_amount: Decimal | None


@dataclass(frozen=True)
class NormalizedCashEffect:
    """One future dated cash effect (scheduled debit/credit or fact credit)."""

    record_id: str
    direction: Direction
    amount_home: Decimal
    home_currency: CurrencyCode
    source_currency: CurrencyCode
    source_amount: Decimal
    effect_date: date
    source_event_ids: tuple[str, ...]
    source_fact_ids: tuple[str, ...]
    category: str
    event_type: EventType
    status: EventStatus
    flexibility: Flexibility
    minimum_allowed_amount: Decimal | None


@dataclass(frozen=True)
class EventNormalization:
    """Immutable normalization outcome for one request case."""

    historical_cash: tuple[NormalizedCashRecord, ...]
    opening_reserves: tuple[NormalizedReserve, ...]
    dated_cash_effects: tuple[NormalizedCashEffect, ...]
    decisions: tuple[NormalizationDecision, ...]
    blocks_downstream: bool


def _event_decision(
    event: EventRecord, disposition: Disposition, reason_code: str
) -> NormalizationDecision:
    return NormalizationDecision(
        subject_kind="event",
        subject_id=event.event_id,
        disposition=disposition.value,
        reason_code=reason_code,
        source_ids=(event.event_id,),
    )


def _fact_decision(
    fact: EvidenceFact, disposition: Disposition, reason_code: str
) -> NormalizationDecision:
    return NormalizationDecision(
        subject_kind="fact",
        subject_id=fact.fact_id,
        disposition=disposition.value,
        reason_code=reason_code,
        source_ids=tuple(source.carrier_id for source in fact.sources),
    )


class _Normalizer:
    def __init__(self, case: RequestCase, evidence: EvidenceResolution) -> None:
        self.case = case
        self.evidence = evidence
        self.request_date = case.request.request_date
        self.home_currency = case.profile.home_currency
        self._rate_index: dict[tuple[date, CurrencyCode, CurrencyCode], Decimal] = {}
        self._event_amount_facts: dict[str, list[EvidenceFact]] = {}
        self._transfer_facts: dict[str, list[EvidenceFact]] = {}
        self._filled_amount_fact_ids: set[str] = set()
        self._filled_amount_event_ids: set[str] = set()
        self._other_facts: list[tuple[EvidenceFact, Disposition, str]] = []
        self.historical: list[NormalizedCashRecord] = []
        self.reserves: list[NormalizedReserve] = []
        self.effects: list[NormalizedCashEffect] = []
        self.decisions: list[NormalizationDecision] = []
        self.blocking = evidence.blocks_downstream

    # -- validation ---------------------------------------------------

    def _build_rate_index(self) -> None:
        for rate in self.case.relevant_rates:
            if not isinstance(rate, ExchangeRateRecord):
                raise EventNormalizationError("invalid_rate_record", ())
            key = (rate.rate_date, rate.from_currency, rate.to_currency)
            if key in self._rate_index and self._rate_index[key] != rate.rate:
                raise EventNormalizationError(
                    "fx_rate_conflict",
                    (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
                )
            if key in self._rate_index:
                continue
            if not rate.rate.is_finite() or rate.rate <= 0:
                raise EventNormalizationError(
                    "fx_rate_invalid",
                    (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
                )
            self._rate_index[key] = rate.rate

    def _validate(self) -> None:
        from buy_or_wait.domain import RequestCase as _RequestCase
        from buy_or_wait.evidence import EvidenceResolution as _EvidenceResolution

        if not isinstance(self.case, _RequestCase):
            raise EventNormalizationError("invalid_case", ())
        if not isinstance(self.evidence, _EvidenceResolution):
            raise EventNormalizationError("invalid_evidence", ())
        seen_events: set[str] = set()
        for event in self.case.events:
            if not isinstance(event, EventRecord):
                raise EventNormalizationError("invalid_event", ())
            if event.event_id in seen_events:
                raise EventNormalizationError(
                    "duplicate_event_id", (event.event_id,)
                )
            seen_events.add(event.event_id)
        seen_facts: set[str] = set()
        for fact in self.evidence.facts:
            if not isinstance(fact, EvidenceFact):
                raise EventNormalizationError("invalid_fact", ())
            if fact.fact_id in seen_facts:
                raise EventNormalizationError("duplicate_fact_id", (fact.fact_id,))
            seen_facts.add(fact.fact_id)
            for source in fact.sources:
                if source.carrier_type == "message":
                    if not any(
                        message.message_id == source.carrier_id
                        for message in self.case.messages
                    ):
                        raise EventNormalizationError(
                            "unknown_fact_carrier", (source.carrier_id,)
                        )
                elif source.carrier_type == "image":
                    if not any(
                        image.image_id == source.carrier_id
                        for image in self.case.images
                    ):
                        raise EventNormalizationError(
                            "unknown_fact_carrier", (source.carrier_id,)
                        )
                else:
                    raise EventNormalizationError(
                        "unknown_fact_carrier", (source.carrier_id,)
                    )
            if fact.target_event_id is not None:
                if fact.target_event_id not in seen_events:
                    raise EventNormalizationError(
                        "unknown_fact_target", (fact.fact_id,)
                    )
            if fact.fact_type is EvidenceFactType.EVENT_AMOUNT:
                self._event_amount_facts.setdefault(
                    fact.target_event_id or "", []
                ).append(fact)
                target = None
                if fact.target_event_id is not None:
                    target = next(
                        (
                            event
                            for event in self.case.events
                            if event.event_id == fact.target_event_id
                        ),
                        None,
                    )
                if target is not None and target.amount is not None:
                    raise EventNormalizationError(
                        "event_amount_target_not_blank",
                        (fact.fact_id, target.event_id),
                    )
            elif fact.fact_type is EvidenceFactType.INTERNAL_TRANSFER_PAIR:
                if fact.target_event_id is not None:
                    self._transfer_facts.setdefault(
                        fact.target_event_id, []
                    ).append(fact)
                else:
                    self._other_facts.append(
                        (fact, Disposition.UNRESOLVED, "transfer_pair_unresolved")
                    )
            elif fact.fact_type is EvidenceFactType.CONFIRMED_FUTURE_CREDIT:
                self._other_facts.append(
                    (fact, Disposition.INCLUDED, "fact_confirmed_future_credit")
                )
            elif fact.fact_type is EvidenceFactType.SETTLED_ONE_TIME_CREDIT:
                self._other_facts.append(
                    (fact, Disposition.INCLUDED, "fact_settled_one_time_credit")
                )
            elif fact.fact_type is EvidenceFactType.PENDING_CREDIT:
                # A pending credit fact records the stated amount without
                # making it available cash; the linked event's own lifecycle
                # disposition already excludes it from cash.
                self._other_facts.append(
                    (fact, Disposition.INCLUDED, "fact_pending_credit_unavailable")
                )
            elif fact.fact_type in (
                EvidenceFactType.UNAVAILABLE_CREDIT,
                EvidenceFactType.UNREALIZED_VALUE,
            ):
                self._other_facts.append(
                    (fact, Disposition.EXCLUDED, "fact_no_cash")
                )
            elif fact.fact_type in _AMENDMENT_FACT_TYPES:
                self._other_facts.append(
                    (fact, Disposition.EXCLUDED, "recurrence_amendment_no_direct_cash")
                )
            else:
                self._other_facts.append(
                    (fact, Disposition.EXCLUDED, "unsupported_fact_type")
                )
        self._build_rate_index()

    # -- FX -----------------------------------------------------------

    def _convert(
        self,
        source_amount: Decimal,
        source_currency: CurrencyCode,
        settlement_date: date | None,
        source_ids: tuple[str, ...],
    ) -> Decimal:
        if source_currency is self.home_currency:
            return source_amount
        if settlement_date is None:
            raise EventNormalizationError(
                "fx_settlement_date_missing", source_ids
            )
        key = (settlement_date, source_currency, self.home_currency)
        try:
            rate = self._rate_index[key]
        except KeyError:
            raise EventNormalizationError(
                "fx_rate_missing",
                source_ids + (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
            ) from None
        return source_amount * rate

    # -- event classification -----------------------------------------

    def _record_fields(self, event: EventRecord):
        return {
            "home_currency": self.home_currency,
            "source_currency": event.currency,
            "source_amount": event.amount,
            "category": event.category,
            "event_type": event.event_type,
            "status": event.status,
            "flexibility": event.flexibility,
            "minimum_allowed_amount": event.minimum_allowed_amount,
        }

    def _settled_boundary_check(self, event: EventRecord) -> date:
        settlement = event.settlement_date
        if settlement is None:
            raise EventNormalizationError(
                "inconsistent_settled_boundary", (event.event_id,)
            )
        if settlement > self.request_date:
            raise EventNormalizationError(
                "inconsistent_settled_boundary", (event.event_id,)
            )
        return settlement

    def _classify(self, event: EventRecord) -> None:
        status = event.status
        direction = event.direction
        if event.event_type is EventType.INVESTMENT_VALUATION or direction is Direction.NON_CASH:
            self.decisions.append(
                _event_decision(event, Disposition.EXCLUDED, "unrealized_non_cash")
            )
            return
        if status in (EventStatus.FAILED, EventStatus.CANCELLED):
            reason = "failed_no_cash" if status is EventStatus.FAILED else "cancelled_no_cash"
            self.decisions.append(_event_decision(event, Disposition.EXCLUDED, reason))
            return
        if status is EventStatus.SETTLED:
            settlement = self._settled_boundary_check(event)
            reason = (
                "investment_sale_cash"
                if event.event_type is EventType.INVESTMENT_SALE
                else (
                    "investment_purchase_cash"
                    if event.event_type is EventType.INVESTMENT_PURCHASE
                    else "historical_already_in_opening"
                )
            )
            if event.amount is None:
                # Missing settled history amount is history, not a new current
                # debit. Exactly one targeted, currency-matching EVENT_AMOUNT
                # fact may fill it as a historical record at the directed
                # settlement-date rate; no fact means unresolved non-blocking
                # history (image_04 contract). Never replayed into opening.
                amount = self._resolve_effect_amount(event)
                if amount is None:
                    self.decisions.append(
                        _event_decision(
                            event, Disposition.UNRESOLVED, "missing_settled_history_amount"
                        )
                    )
                    return
                fill_fact_ids = tuple(
                    fill_fact.fact_id
                    for fill_fact in self._event_amount_facts.get(event.event_id, ())
                )
                amount_home = self._convert(
                    amount, event.currency, settlement, (event.event_id,)
                )
                fields = self._record_fields(event)
                self.historical.append(
                    NormalizedCashRecord(
                        record_id=f"event:{event.event_id}",
                        direction=direction,
                        amount_home=amount_home,
                        settlement_date=settlement,
                        source_event_ids=(event.event_id,),
                        source_fact_ids=fill_fact_ids,
                        **fields,
                    )
                )
                self.decisions.append(_event_decision(event, Disposition.INCLUDED, reason))
                return
            amount = self._convert(
                event.amount, event.currency, settlement, (event.event_id,)
            )
            fill_fact_ids = tuple(
                fill_fact.fact_id
                for fill_fact in self._event_amount_facts.get(event.event_id, ())
            )
            fields = self._record_fields(event)
            self.historical.append(
                NormalizedCashRecord(
                    record_id=f"event:{event.event_id}",
                    direction=direction,
                    amount_home=amount,
                    settlement_date=settlement,
                    source_event_ids=(event.event_id,),
                    source_fact_ids=fill_fact_ids,
                    **fields,
                )
            )
            self.decisions.append(_event_decision(event, Disposition.INCLUDED, reason))
            return
        if status is EventStatus.PENDING:
            if direction is Direction.CREDIT:
                self.decisions.append(
                    _event_decision(event, Disposition.EXCLUDED, "pending_credit_unavailable")
                )
                return
            if direction is Direction.DEBIT:
                reason = (
                    "possible_duplicate_retained"
                    if event.linked_event_id is not None
                    else "pending_debit_reserved"
                )
                self._reserve(event, reason)
                return
            raise EventNormalizationError("pending_direction_invalid", (event.event_id,))
        if status is EventStatus.SCHEDULED:
            settlement = event.settlement_date
            if settlement is None:
                raise EventNormalizationError(
                    "fx_settlement_date_missing", (event.event_id,)
                )
            if settlement < self.request_date:
                raise EventNormalizationError(
                    "overdue_scheduled_unrouted", (event.event_id,)
                )
            amount = self._resolve_effect_amount(event)
            if amount is None:
                # Grounded uncertainty: a required future debit with no
                # supplied amount invents nothing and blocks certification.
                if direction is Direction.DEBIT:
                    self.blocking = True
                    self.decisions.append(
                        _event_decision(
                            event,
                            Disposition.UNRESOLVED,
                            "missing_required_debit_amount",
                        )
                    )
                else:
                    self.decisions.append(
                        _event_decision(
                            event,
                            Disposition.UNRESOLVED,
                            "missing_scheduled_credit_amount",
                        )
                    )
                return
            reason = "scheduled_debit" if direction is Direction.DEBIT else "scheduled_credit"
            if direction is Direction.DEBIT and event.event_type is EventType.INVESTMENT_PURCHASE:
                reason = "investment_purchase_cash"
            amount_home = self._convert(
                amount, event.currency, settlement, (event.event_id,)
            )
            fill_fact_ids = tuple(
                fill_fact.fact_id
                for fill_fact in self._event_amount_facts.get(event.event_id, ())
            )
            fields = self._record_fields(event)
            self.effects.append(
                NormalizedCashEffect(
                    record_id=f"event:{event.event_id}",
                    direction=direction,
                    amount_home=amount_home,
                    effect_date=settlement,
                    source_event_ids=(event.event_id,),
                    source_fact_ids=fill_fact_ids,
                    **fields,
                )
            )
            self.decisions.append(_event_decision(event, Disposition.INCLUDED, reason))
            return
        raise EventNormalizationError("unknown_event_status", (event.event_id,))

    def _reserve(self, event: EventRecord, reason: str) -> None:
        if event.settlement_date is None:
            raise EventNormalizationError(
                "fx_settlement_date_missing", (event.event_id,)
            )
        amount = self._resolve_effect_amount(event)
        if amount is None:
            self.blocking = True
            self.decisions.append(
                _event_decision(event, Disposition.UNRESOLVED, "missing_required_debit_amount")
            )
            return
        amount_home = self._convert(
            amount, event.currency, event.settlement_date, (event.event_id,)
        )
        fill_fact_ids = tuple(
            fill_fact.fact_id
            for fill_fact in self._event_amount_facts.get(event.event_id, ())
        )
        fields = self._record_fields(event)
        self.reserves.append(
            NormalizedReserve(
                record_id=f"event:{event.event_id}",
                direction=event.direction,
                amount_home=amount_home,
                reserved_on=self.request_date,
                settlement_date=event.settlement_date,
                source_event_ids=(event.event_id,),
                source_fact_ids=fill_fact_ids,
                **fields,
            )
        )
        self.decisions.append(_event_decision(event, Disposition.INCLUDED, reason))

    def _resolve_effect_amount(self, event: EventRecord) -> Decimal | None:
        if event.amount is not None:
            facts = self._event_amount_facts.get(event.event_id)
            if facts:
                raise EventNormalizationError(
                    "event_amount_target_not_blank", (event.event_id,)
                )
            return event.amount
        facts = self._event_amount_facts.get(event.event_id, [])
        if not facts:
            return None
        if len(facts) > 1:
            raise EventNormalizationError(
                "event_amount_conflict", (event.event_id,)
            )
        fact = facts[0]
        if fact.currency is not event.currency:
            raise EventNormalizationError(
                "event_amount_currency_mismatch", (event.event_id, fact.fact_id)
            )
        if fact.amount is None:
            raise EventNormalizationError(
                "event_amount_missing_value", (event.event_id, fact.fact_id)
            )
        self._filled_amount_fact_ids.add(fact.fact_id)
        self._filled_amount_event_ids.add(event.event_id)
        return fact.amount

    # -- fact-only credits ------------------------------------------------

    def _emit_fact_credit(self, fact: EvidenceFact) -> None:
        if fact.amount is None or fact.currency is None:
            raise EventNormalizationError(
                "fact_credit_ungrounded", (fact.fact_id,)
            )
        amount_home = self._convert(
            fact.amount, fact.currency, fact.settlement_date, (fact.fact_id,)
        )
        self.effects.append(
            NormalizedCashEffect(
                record_id=f"fact:{fact.fact_id}",
                direction=Direction.CREDIT,
                amount_home=amount_home,
                home_currency=self.home_currency,
                source_currency=fact.currency,
                source_amount=fact.amount,
                effect_date=fact.settlement_date,
                source_event_ids=(),
                source_fact_ids=(fact.fact_id,),
                category="evidence",
                event_type=EventType.INCOME,
                status=EventStatus.SCHEDULED,
                flexibility=Flexibility.FIXED,
                minimum_allowed_amount=None,
            )
        )

    # -- transfer pair validation --------------------------------------

    def _classify_transfer_pairs(self) -> None:
        if not self._transfer_facts:
            return
        events = list(self.case.events)
        for target_id, facts in self._transfer_facts.items():
            target = next(
                (event for event in events if event.event_id == target_id), None
            )
            if target is None:
                for fact in facts:
                    self.decisions.append(
                        _fact_decision(fact, Disposition.UNRESOLVED, "transfer_pair_unmatched")
                    )
                continue
            for fact in facts:
                counterpart = self._find_counterpart(target)
                if counterpart is None:
                    self.decisions.append(
                        _fact_decision(fact, Disposition.UNRESOLVED, "transfer_pair_unmatched")
                    )
                    continue
                for event in (target, counterpart):
                    if any(
                        decision.subject_kind == "event"
                        and decision.subject_id == event.event_id
                        for decision in self.decisions
                    ):
                        # Event already classified (possible duplicates of the
                        # same pair): never assign two active cash roles.
                        self.decisions.append(
                            _event_decision(
                                event,
                                Disposition.EXCLUDED,
                                "internal_transfer_neutral",
                            )
                        )
                    else:
                        self.decisions.append(
                            _event_decision(
                                event,
                                Disposition.EXCLUDED,
                                "internal_transfer_neutral",
                            )
                        )
                self.decisions.append(_fact_decision(fact, Disposition.INCLUDED, "internal_transfer_neutral"))

    def _find_counterpart(self, target: EventRecord) -> EventRecord | None:
        matches: list[EventRecord] = []
        for event in self.case.events:
            if event.event_id == target.event_id:
                continue
            if event.user_id != target.user_id:
                continue
            if event.currency != target.currency:
                continue
            if event.amount != target.amount:
                continue
            if event.settlement_date != target.settlement_date:
                continue
            if event.direction is target.direction:
                continue
            linked = (
                event.linked_event_id == target.event_id
                or target.linked_event_id == event.event_id
            )
            if not linked:
                continue
            matches.append(event)
        if len(matches) != 1:
            return None
        return matches[0]

    # -- ordering guard -------------------------------------------------

    def _remove_event_decision(self, event_id: str) -> list[NormalizationDecision]:
        kept = [
            decision
            for decision in self.decisions
            if not (decision.subject_kind == "event" and decision.subject_id == event_id)
        ]
        return kept

    # -- main entry ------------------------------------------------------

    def run(self) -> EventNormalization:
        self._validate()
        events_by_id = {event.event_id: event for event in self.case.events}
        # Classify all events in supplied order first.
        for event in self.case.events:
            self._classify(event)
        # Transfer-pair neutralization overrides the individual roles of the
        # two validated events; validated pairs must contain exactly the two
        # validated opposite-direction events.
        if self._transfer_facts:
            self._classify_transfer_pairs()
            self._strip_pair_effects()
        # Fact-only and amendment decisions; fact-only confirmed future
        # credits also emit one dated credit effect.
        for fact, disposition, reason in self._other_facts:
            if fact.fact_type is EvidenceFactType.CONFIRMED_FUTURE_CREDIT:
                self._emit_fact_credit(fact)
            self.decisions.append(_fact_decision(fact, disposition, reason))
        # Amount-fill facts own a decision even though they filled an event.
        for facts in self._event_amount_facts.values():
            for fact in facts:
                if fact.fact_id in self._filled_amount_fact_ids:
                    self.decisions.append(
                        _fact_decision(fact, Disposition.INCLUDED, "event_amount_fill")
                    )
        # Propagate upstream diagnostics by safe IDs/reason codes.
        for diagnostic in self.evidence.diagnostics:
            self.decisions.append(
                NormalizationDecision(
                    subject_kind="diagnostic",
                    subject_id=diagnostic.carrier_id,
                    disposition=Disposition.UNRESOLVED.value,
                    reason_code=diagnostic.reason_code,
                    source_ids=diagnostic.source_ids,
                )
            )
            if diagnostic.blocks_downstream:
                self.blocking = True
        self._check_conservation(events_by_id)
        return EventNormalization(
            historical_cash=tuple(self.historical),
            opening_reserves=tuple(self.reserves),
            dated_cash_effects=tuple(self.effects),
            decisions=tuple(self.decisions),
            blocks_downstream=self.blocking,
        )

    def _strip_pair_effects(self) -> None:
        neutral_ids = {
            decision.subject_id
            for decision in self.decisions
            if decision.subject_kind == "event"
            and decision.reason_code == "internal_transfer_neutral"
            and decision.disposition == Disposition.EXCLUDED.value
        }
        if not neutral_ids:
            return
        # A neutralized pair contributes no cash on either side: remove every
        # record the earlier classification produced (historical, reserve, or
        # dated effect) and drop stale event decisions before appending the
        # neutral ones.
        record_ids = {f"event:{eid}" for eid in neutral_ids}
        self.historical = [
            record
            for record in self.historical
            if record.record_id not in record_ids
        ]
        self.effects = [
            effect for effect in self.effects if effect.record_id not in record_ids
        ]
        self.reserves = [
            reserve for reserve in self.reserves if reserve.record_id not in record_ids
        ]
        for event_id in neutral_ids:
            self.decisions = self._remove_event_decision(event_id)
        # Re-append neutral event decisions once per neutralized event.
        for event_id in sorted(neutral_ids):
            self.decisions.append(
                NormalizationDecision(
                    subject_kind="event",
                    subject_id=event_id,
                    disposition=Disposition.EXCLUDED.value,
                    reason_code="internal_transfer_neutral",
                    source_ids=(event_id,),
                )
            )

    def _check_conservation(
        self, events_by_id: dict[str, EventRecord]
    ) -> None:
        owned: dict[str, str] = {}
        for record in self.historical:
            for event_id in record.source_event_ids:
                if event_id in owned:
                    raise EventNormalizationError(
                        "source_owns_two_roles", (event_id,)
                    )
                owned[event_id] = "historical"
        for reserve in self.reserves:
            for event_id in reserve.source_event_ids:
                if event_id in owned:
                    raise EventNormalizationError(
                        "source_owns_two_roles", (event_id,)
                    )
                owned[event_id] = "reserve"
        for effect in self.effects:
            for event_id in effect.source_event_ids:
                if event_id in owned:
                    raise EventNormalizationError(
                        "source_owns_two_roles", (event_id,)
                    )
                owned[event_id] = "dated_effect"
        decided = {
            decision.subject_id
            for decision in self.decisions
            if decision.subject_kind == "event"
        }
        missing = set(events_by_id) - decided
        if missing:
            raise EventNormalizationError(
                "unowned_event", tuple(sorted(missing))
            )
        decided_facts = {
            decision.subject_id
            for decision in self.decisions
            if decision.subject_kind == "fact"
        }
        missing_facts = {fact.fact_id for fact in self.evidence.facts} - decided_facts
        if missing_facts:
            raise EventNormalizationError(
                "unowned_fact", tuple(sorted(missing_facts))
            )
        for event_id, role in owned.items():
            decision = next(
                (
                    d
                    for d in self.decisions
                    if d.subject_kind == "event" and d.subject_id == event_id
                ),
                None,
            )
            if decision is None or decision.disposition not in (
                Disposition.INCLUDED.value,
                Disposition.UNRESOLVED.value,
            ):
                raise EventNormalizationError(
                    "role_decision_mismatch", (event_id,)
                )


def normalize_case_events(
    case: RequestCase, evidence: EvidenceResolution
) -> EventNormalization:
    """Normalize one validated case and its accepted evidence resolution.

    Pure: reads no files, environment, clock, model, or global cache and
    performs no output write. Fails closed via ``EventNormalizationError``
    for an unrepresentable input contract; grounded uncertainty instead
    produces unresolved decisions with ``blocks_downstream``.
    """
    return _Normalizer(case, evidence).run()

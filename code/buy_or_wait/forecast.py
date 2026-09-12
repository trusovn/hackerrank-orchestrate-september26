"""WP-05 baseline forecast: recurrence, variable spending, and ledger replay.

Deterministic, standard-library-only boundary that consumes one validated
``RequestCase``, its accepted ``EvidenceResolution``, and the WP-04
``EventNormalization`` built from those same inputs, then materializes one
reproducible baseline ledger from the request date through the selected
day-89/day-90 endpoint.

No payment capacity, candidate, ranking, plan, or output decision is made
here; WP-06 owns that replay over this result.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from buy_or_wait.domain import (
    CurrencyCode,
    Direction,
    EventStatus,
    EventType,
    EvidenceFact,
    EvidenceFactType,
    RequestCase,
)
from buy_or_wait.evidence import EvidenceResolution
from buy_or_wait.events import (
    EventNormalization,
    NormalizedCashRecord,
    NormalizedReserve,
    convert_exact,
)

_HOME_ZERO = Decimal("0")
_CENT = Decimal("0.01")


def _is_valid_nonnegative_money(value: object) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value >= 0


class ForecastBuildError(ValueError):
    """Fail-closed error for an unrepresentable forecast input contract."""

    def __init__(self, reason_code: str, source_ids: tuple[str, ...] = ()) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.source_ids = source_ids


class RecurrenceTiming(Enum):
    STRICT = "strict"
    TOLERANT_2_DAY = "tolerant_2_day"


class IncomeContinuation(Enum):
    I0_EXPLICIT_ONGOING = "i0_explicit_ongoing"
    I1_STRICT_RECENT_HISTORY = "i1_strict_recent_history"


class VariableSpending(Enum):
    V0_MAX_COMPLETE_MONTH = "v0_max_complete_month"
    V1_MAX_CADENCED_OCCURRENCE = "v1_max_cadenced_occurrence"
    V2_MEAN_COMPLETE_MONTH = "v2_mean_complete_month"


class HorizonEndpoint(Enum):
    DAY_89_INCLUSIVE = "day_89_inclusive"
    DAY_90_INCLUSIVE = "day_90_inclusive"


class UnknownSameDayOrder(Enum):
    DEBIT_CREDIT_PAYMENT = "debit_credit_payment"
    CREDIT_DEBIT_PAYMENT = "credit_debit_payment"


@dataclass(frozen=True)
class ForecastPolicy:
    recurrence_timing: RecurrenceTiming
    income_continuation: IncomeContinuation
    variable_spending: VariableSpending
    horizon_endpoint: HorizonEndpoint
    same_day_order: UnknownSameDayOrder


DEFAULT_FORECAST_POLICY = ForecastPolicy(
    recurrence_timing=RecurrenceTiming.STRICT,
    income_continuation=IncomeContinuation.I0_EXPLICIT_ONGOING,
    variable_spending=VariableSpending.V0_MAX_COMPLETE_MONTH,
    horizon_endpoint=HorizonEndpoint.DAY_90_INCLUSIVE,
    same_day_order=UnknownSameDayOrder.DEBIT_CREDIT_PAYMENT,
)


@dataclass(frozen=True)
class ForecastDiagnostic:
    reason_code: str
    source_ids: tuple[str, ...]
    blocks_downstream: bool


@dataclass(frozen=True)
class SeriesObservation:
    date: date
    home_amount: Decimal
    source_amount: Decimal | None
    source_currency: CurrencyCode
    record_id: str


@dataclass(frozen=True)
class SeriesTrace:
    family_id: str
    direction: Direction
    category: str
    observations: tuple[tuple[date, Decimal], ...]
    observation_record_ids: tuple[str, ...]
    cadence: str | None
    amount_rule: str
    applied_fact_ids: tuple[str, ...]
    generated_dates: tuple[date, ...]
    replacement_decisions: tuple[str, ...]
    reason_code: str


@dataclass(frozen=True)
class ProjectedOccurrence:
    family_id: str
    date: date
    direction: Direction
    source_amount: Decimal | None
    source_currency: CurrencyCode | None
    home_amount: Decimal
    origin: str
    source_event_ids: tuple[str, ...]
    source_fact_ids: tuple[str, ...]


@dataclass(frozen=True)
class Checkpoint:
    date: date
    kind: str
    cash_balance: Decimal
    reserved_balance: Decimal
    spendable_balance: Decimal
    headroom: Decimal
    delta: Decimal | None
    delta_kind: str | None
    family_id: str | None
    source_ids: tuple[str, ...]
    reason_code: str


@dataclass(frozen=True)
class BaselineForecast:
    request_id: str
    request_date: date
    horizon_end: date
    opening_cash: Decimal
    minimum_balance: Decimal
    opening_reserved: Decimal
    series_traces: tuple[SeriesTrace, ...]
    projected_occurrences: tuple[ProjectedOccurrence, ...]
    checkpoints: tuple[Checkpoint, ...]
    diagnostics: tuple[ForecastDiagnostic, ...]
    blocks_downstream: bool
    minimum_headroom: Decimal | None


_NON_RECURRENCE_EVENT_TYPES = frozenset(
    {
        EventType.REFUND,
        EventType.INVESTMENT_PURCHASE,
        EventType.INVESTMENT_VALUATION,
        EventType.INVESTMENT_SALE,
    }
)

_RECURRENCE_FACT_TYPES = frozenset(
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

_REQUIRED_TARGET_FACT_TYPES = frozenset(
    {
        EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
        EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
        EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
        EvidenceFactType.RECURRENCE_RESUME,
        EvidenceFactType.RECURRING_EXPENSE_NOTICE,
    }
)


def _canonical_description(description: str) -> str:
    cleaned = "".join(
        char if char.isalnum() else " " for char in description.casefold()
    )
    return " ".join(cleaned.split())


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + offset
    return total // 12, (total % 12) + 1


def _monthly_date(anchor_year: int, anchor_month: int, day: int, offset: int) -> date:
    year, month = _add_months(anchor_year, anchor_month, offset)
    return date(year, month, min(day, _last_day_of_month(year, month)))


def _detect_monthly(
    observations: list[SeriesObservation],
) -> tuple[str, int | None] | None:
    """Return ('month_end', None) or ('month_day', n) for a supported series."""
    if len(observations) < 3:
        return None
    for first, second in zip(observations, observations[1:]):
        if (second.date.year, second.date.month) != _add_months(
            first.date.year, first.date.month, 1
        ):
            return None
    if all(
        observation.date.day == _last_day_of_month(observation.date.year, observation.date.month)
        for observation in observations
    ):
        return ("month_end", None)
    anchor = observations[0].date.day
    for observation in observations:
        expected = min(
            anchor, _last_day_of_month(observation.date.year, observation.date.month)
        )
        if observation.date.day != expected:
            return None
    return ("month_day", anchor)


def _detect_weekly(
    observations: list[SeriesObservation], interval_days: int
) -> bool:
    if len(observations) < 3:
        return False
    for first, second in zip(observations, observations[1:]):
        if (second.date - first.date).days != interval_days:
            return False
    return True


def _detect_tolerant_monthly(observations: list[SeriesObservation]) -> bool:
    if len(observations) < 3:
        return False
    for first, second in zip(observations, observations[1:]):
        month_gap = (
            second.date.year * 12 + second.date.month
        ) - (first.date.year * 12 + first.date.month)
        if month_gap != 1:
            return False
    anchor_day = observations[0].date.day
    for observation in observations:
        if abs(observation.date.day - anchor_day) > 2:
            return False
    return True


def _detect_tolerant_weekly(
    observations: list[SeriesObservation], interval_days: int
) -> bool:
    if len(observations) < 3:
        return False
    anchor = observations[0].date
    for index, observation in enumerate(observations):
        expected = anchor + timedelta(days=index * interval_days)
        if abs((observation.date - expected).days) > 2:
            return False
    return True


def _tolerant_monthly_dates(
    anchor: SeriesObservation, horizon_end: date, timing: RecurrenceTiming
) -> list[date]:
    dates = []
    offset = 1
    while True:
        candidate = _monthly_date(anchor.date.year, anchor.date.month, anchor.date.day, offset)
        if candidate > horizon_end:
            break
        dates.append(candidate)
        offset += 1
    return dates


class _Series:
    """Mutable build-phase holder for one candidate recurring family."""

    def __init__(self, family_id: str, observations: list[SeriesObservation]) -> None:
        self.family_id = family_id
        self.observations = observations
        self.direction: Direction | None = None
        self.category: str | None = None
        self.cadence: str | None = None
        self.cadence_detail: int | None = None
        self.amount: Decimal | None = None
        self.source_amount: Decimal | None = None
        self.source_currency: CurrencyCode | None = None
        self.applied_fact_ids: tuple[str, ...] = ()
        self.replacement_decisions: list[str] = []
        self.reason_code = "supported"
        self.amount_rule = "unsupported_cadence"
        self.stopped = False
        self.confirm_next = False
        self.next_cycle_amount: Decimal | None = None
        self.date_replacement: date | None = None
        self.amendment_from: date | None = None
        self.pre_amendment_amount: Decimal | None = None
        self.has_explicit_ongoing = False
        self.resume_from: date | None = None
        self.tolerant_anchor_date: date | None = None
        self.tolerant_interval_days: int | None = None

    @property
    def anchor_record_id(self) -> str:
        return self.observations[-1].record_id


def _occurrence_key(item) -> tuple:
    return (item["date"], item["family_id"], item["kind"], item["record_id"])


class _Builder:
    def __init__(
        self,
        case: RequestCase,
        evidence,
        normalization: EventNormalization,
        policy: ForecastPolicy,
    ) -> None:
        self.case = case
        self.evidence = evidence
        self.normalization = normalization
        self.policy = policy
        self.request_date = case.request.request_date
        self.home_currency = case.profile.home_currency
        offset = 89 if policy.horizon_endpoint is HorizonEndpoint.DAY_89_INCLUSIVE else 90
        self.horizon_end = date.fromordinal(self.request_date.toordinal() + offset)
        self.diagnostics: list[ForecastDiagnostic] = []
        self.occurrences: list[ProjectedOccurrence] = []
        self.traces: list[SeriesTrace] = []
        self.dispositions: dict[str, str] = {}
        self._validate_boundary()
        self.blocks = normalization.blocks_downstream

    # -- phase 1 -------------------------------------------------------

    def _validate_boundary(self) -> None:
        from buy_or_wait.evidence import EvidenceResolution as _EvidenceResolution
        from buy_or_wait.events import (
            EventNormalization as _EventNormalization,
            NormalizedCashRecord as _NormalizedCashRecord,
            NormalizedReserve as _NormalizedReserve,
            NormalizedCashEffect as _NormalizedCashEffect,
        )

        if not isinstance(self.case, RequestCase):
            raise ForecastBuildError("invalid_case")
        if not isinstance(self.evidence, _EvidenceResolution):
            raise ForecastBuildError("invalid_evidence")
        if not isinstance(self.normalization, _EventNormalization):
            raise ForecastBuildError("invalid_normalization")
        request_user_id = self.case.request.user_id
        if self.case.profile.user_id != request_user_id:
            raise ForecastBuildError("user_id_mismatch")
        for record in (*self.case.events, *self.case.messages, *self.case.images):
            if record.user_id != request_user_id:
                raise ForecastBuildError("user_id_mismatch")
        for amount in (
            self.case.profile.current_available_balance,
            self.case.profile.minimum_balance_to_keep,
        ):
            if not _is_valid_nonnegative_money(amount):
                raise ForecastBuildError("invalid_monetary_input")

        event_ids = {event.event_id for event in self.case.events}
        fact_ids = {fact.fact_id for fact in self.evidence.facts}
        if len(event_ids) != len(self.case.events):
            raise ForecastBuildError("duplicate_event_id", tuple(sorted(event_ids)))
        if len(fact_ids) != len(self.evidence.facts):
            raise ForecastBuildError("duplicate_fact_id", tuple(sorted(fact_ids)))

        seen: set[str] = set()
        event_owners: dict[str, str] = {}
        fact_owners: dict[str, str] = {}
        for record in self.normalization.historical_cash:
            self._check_record(
                record,
                "historical",
                seen,
                event_ids,
                fact_ids,
                event_owners,
                fact_owners,
            )
        for reserve in self.normalization.opening_reserves:
            self._check_record(
                reserve,
                "reserve",
                seen,
                event_ids,
                fact_ids,
                event_owners,
                fact_owners,
            )
        for effect in self.normalization.dated_cash_effects:
            self._check_record(
                effect,
                "effect",
                seen,
                event_ids,
                fact_ids,
                event_owners,
                fact_owners,
            )

        for record in (
            *self.normalization.historical_cash,
            *self.normalization.opening_reserves,
            *self.normalization.dated_cash_effects,
        ):
            if not _is_valid_nonnegative_money(record.amount_home):
                raise ForecastBuildError(
                    "invalid_monetary_input", record.source_event_ids
                )

        self._rate_index = {}
        for rate in self.case.relevant_rates:
            key = (rate.rate_date, rate.from_currency, rate.to_currency)
            if key in self._rate_index and self._rate_index[key] != rate.rate:
                raise ForecastBuildError(
                    "fx_rate_conflict",
                    (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
                )
            if key in self._rate_index:
                continue
            if not isinstance(rate.rate, Decimal) or not rate.rate.is_finite() or rate.rate <= 0:
                raise ForecastBuildError(
                    "fx_rate_invalid",
                    (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
                )
            self._rate_index[key] = rate.rate

    def _check_record(
        self,
        record,
        role,
        seen,
        event_ids,
        fact_ids,
        event_owners,
        fact_owners,
    ) -> None:
        if record.record_id in seen:
            raise ForecastBuildError("duplicate_record_id", (record.record_id,))
        seen.add(record.record_id)
        if not record.source_event_ids and not record.source_fact_ids:
            raise ForecastBuildError("source_owner_missing", (record.record_id,))
        for event_id in record.source_event_ids:
            if event_id not in event_ids:
                raise ForecastBuildError("source_owner_missing", (record.record_id,))
            if event_id in event_owners:
                owner_role, owner_id = event_owners[event_id]
                if {owner_role, role} != {"historical", "effect"}:
                    raise ForecastBuildError(
                        "duplicate_source_owner", (owner_id, record.record_id)
                    )
            event_owners[event_id] = (role, record.record_id)
        for fact_id in record.source_fact_ids:
            if fact_id not in fact_ids:
                raise ForecastBuildError("source_owner_missing", (record.record_id,))
            if fact_id in fact_owners:
                owner_role, owner_id = fact_owners[fact_id]
                if {owner_role, role} != {"historical", "effect"}:
                    raise ForecastBuildError(
                        "duplicate_source_owner", (owner_id, record.record_id)
                    )
            fact_owners[fact_id] = (role, record.record_id)

    # -- phase 2 -------------------------------------------------------

    def _classify_histories(self) -> None:
        families: dict[tuple, list[NormalizedCashRecord]] = {}
        for record in self.normalization.historical_cash:
            if record.event_type in _NON_RECURRENCE_EVENT_TYPES:
                self.dispositions[record.record_id] = "non_recurring"
                continue
            if record.event_type is EventType.INCOME:
                self.dispositions[record.record_id] = "income_history"
                families.setdefault(
                    self._series_key(record), []
                ).append(record)
                continue
            if record.amount_home <= 0:
                self.dispositions[record.record_id] = "unresolved"
                continue
            families.setdefault(self._series_key(record), []).append(record)
        self._families = families
        self._series_map: dict[tuple, _Series] = {}

    def _series_key(self, record) -> tuple:
        descriptions = tuple(
            sorted(
                _canonical_description(event.description)
                for event in self.case.events
                if event.event_id in record.source_event_ids
            )
        )
        return (
            record.category,
            record.direction,
            record.event_type,
            record.source_currency,
            record.flexibility,
            record.minimum_allowed_amount,
            descriptions,
        )

    # -- phase 3 -------------------------------------------------------

    def _family_series(self, key, records: list[NormalizedCashRecord]) -> _Series | None:
        if key in self._series_map:
            return self._series_map[key]
        series = self._series_of(records)
        if series is not None:
            self._series_map[key] = series
        return series

    def _series_of(self, records: list[NormalizedCashRecord]) -> _Series | None:
        observations = [
            SeriesObservation(
                date=record.settlement_date,
                home_amount=record.amount_home,
                source_amount=record.source_amount,
                source_currency=record.source_currency,
                record_id=record.record_id,
            )
            for record in sorted(
                records, key=lambda r: (r.settlement_date, r.record_id)
            )
        ]
        if any(observation.date is None for observation in observations):
            return None
        if len({observation.date for observation in observations}) != len(observations):
            return None
        family_id = f"series:{observations[-1].record_id.split(':')[-1]}"
        series = _Series(family_id, observations)
        series.direction = records[0].direction
        series.category = records[0].category
        series.source_currency = records[0].source_currency
        series.source_amount = observations[-1].source_amount
        return series

    def _detect_cadence(self, series: _Series) -> bool:
        observations = series.observations
        monthly = _detect_monthly(observations)
        if monthly is not None:
            series.cadence, series.cadence_detail = monthly
            return True
        if _detect_weekly(observations, 7):
            series.cadence = "weekly_7"
            return True
        if _detect_weekly(observations, 14):
            series.cadence = "weekly_14"
            return True
        if (
            self.policy.recurrence_timing is RecurrenceTiming.TOLERANT_2_DAY
            and _detect_tolerant_weekly(observations, 7)
        ):
            series.cadence = "tolerant_weekly_7"
            series.tolerant_anchor_date = observations[0].date
            series.tolerant_interval_days = 7
            return True
        if (
            self.policy.recurrence_timing is RecurrenceTiming.TOLERANT_2_DAY
            and _detect_tolerant_weekly(observations, 14)
        ):
            series.cadence = "tolerant_weekly_14"
            series.tolerant_anchor_date = observations[0].date
            series.tolerant_interval_days = 14
            return True
        if (
            self.policy.recurrence_timing is RecurrenceTiming.TOLERANT_2_DAY
            and _detect_tolerant_monthly(observations)
        ):
            series.cadence = "tolerant_monthly"
            series.cadence_detail = observations[0].date.day
            return True
        series.reason_code = "unsupported_cadence"
        return False

    def _select_amount(self, series: _Series) -> bool:
        observations = series.observations
        tail_amount = observations[-1].home_amount
        suffix = 1
        for observation in reversed(observations[:-1]):
            if observation.home_amount == tail_amount:
                suffix += 1
            else:
                break
        if suffix >= 2:
            series.amount = tail_amount
            series.amount_rule = "equal_suffix"
            return True
        series.amount = None
        series.amount_rule = "varying_no_suffix"
        return False

    def _project_dates(self, series: _Series) -> list[date]:
        anchor = series.observations[-1]
        dates: list[date] = []
        if series.cadence in ("month_end", "tolerant_monthly", "month_day"):
            if series.cadence == "month_end":
                day = None
            else:
                day = series.cadence_detail
            offset = 1
            while True:
                candidate = _monthly_date(
                    anchor.date.year,
                    anchor.date.month,
                    day if day is not None else anchor.date.day,
                    offset,
                )
                if series.cadence == "month_end":
                    candidate = date(
                        *_add_months(anchor.date.year, anchor.date.month, offset),
                        1,
                    )
                    candidate = candidate.replace(
                        day=_last_day_of_month(candidate.year, candidate.month)
                    )
                elif series.cadence == "tolerant_monthly":
                    candidate = self._tolerant_shift(candidate, series.direction)
                if candidate > self.horizon_end:
                    break
                dates.append(candidate)
                offset += 1
        elif series.cadence in (
            "weekly_7",
            "weekly_14",
            "tolerant_weekly_7",
            "tolerant_weekly_14",
        ):
            step = 7 if series.cadence == "weekly_7" else 14
            if series.cadence.startswith("tolerant_"):
                step = series.tolerant_interval_days
                candidate = series.tolerant_anchor_date + timedelta(
                    days=len(series.observations) * step
                )
                candidate = self._tolerant_shift(candidate, series.direction)
            else:
                candidate = anchor.date + timedelta(days=step)
            while candidate <= self.horizon_end:
                dates.append(candidate)
                candidate += timedelta(days=step)
        return dates

    def _tolerant_shift(self, candidate: date, direction: Direction) -> date:
        shift = -2 if direction is Direction.DEBIT else 2
        return candidate + timedelta(days=shift)

    # -- phase 4 -------------------------------------------------------

    def _apply_facts(self, series_by_target: dict[str, list[_Series]]) -> None:
        for fact in self.evidence.facts:
            if fact.fact_type not in _RECURRENCE_FACT_TYPES:
                continue
            targets = self._resolve_targets(fact, series_by_target)
            if len(targets) != 1:
                if targets == [] and self._is_debit_series_target(fact):
                    self.diagnostics.append(
                        ForecastDiagnostic(
                            "amendment_target_unresolved",
                            tuple(source.carrier_id for source in fact.sources)
                            + ((fact.target_event_id,) if fact.target_event_id else ()),
                            True,
                        )
                    )
                    self.blocks = True
                elif targets == [] or len(targets) > 1:
                    self.diagnostics.append(
                        ForecastDiagnostic(
                            "amendment_target_ambiguous",
                            tuple(source.carrier_id for source in fact.sources),
                            False,
                        )
                    )
                continue
            series = targets[0]
            self._apply_fact(fact, series)

    def _is_debit_series_target(self, fact: EvidenceFact) -> bool:
        if fact.target_event_id is None:
            return fact.fact_type in _REQUIRED_TARGET_FACT_TYPES
        for event in self.case.events:
            if event.event_id == fact.target_event_id:
                return event.direction is Direction.DEBIT
        return fact.fact_type in _REQUIRED_TARGET_FACT_TYPES

    def _resolve_targets(
        self, fact: EvidenceFact, series_by_target: dict[str, list[_Series]]
    ) -> list[_Series]:
        if fact.target_event_id is None:
            return []
        matches = []
        for event in self.case.events:
            if event.event_id == fact.target_event_id:
                for series in series_by_target.get(event.event_id, []):
                    if series not in matches:
                        matches.append(series)
        return matches

    def _apply_fact(self, fact: EvidenceFact, series: _Series) -> None:
        series.applied_fact_ids = series.applied_fact_ids + (fact.fact_id,)
        fact_type = fact.fact_type
        if fact_type in (
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
        ):
            if fact.amount is None:
                if series.direction is Direction.DEBIT:
                    self.diagnostics.append(
                        ForecastDiagnostic(
                            "unbounded_recurring_debit",
                            (fact.fact_id,),
                            True,
                        )
                    )
                    self.blocks = True
                    series.reason_code = "unbounded_notice"
                    return
                return
            if series.amendment_from is None:
                series.pre_amendment_amount = series.amount
            series.amount = fact.amount
            series.source_amount = fact.amount
            series.source_currency = fact.currency or series.source_currency
            series.amount_rule = "recurring_amendment"
            if fact_type is EvidenceFactType.RECURRING_AMOUNT_AMENDMENT:
                series.has_explicit_ongoing = True
            if fact.effective_date is not None:
                series.amendment_from = fact.effective_date
            else:
                series.amendment_from = self.request_date
        elif fact_type is EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT:
            if fact.amount is not None:
                series.next_cycle_amount = fact.amount
                series.amount_rule = "next_cycle_amendment"
        elif fact_type is EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT:
            if fact.settlement_date is not None:
                series.date_replacement = fact.settlement_date
        elif fact_type is EvidenceFactType.RECURRENCE_STOP:
            series.stopped = True
            series.reason_code = "stopped"
        elif fact_type is EvidenceFactType.RECURRENCE_RESUME:
            if fact.amount is not None:
                series.stopped = False
                series.amount = fact.amount
                series.source_amount = fact.amount
                series.source_currency = fact.currency or series.source_currency
                series.amount_rule = "resume_amount"
                series.resume_from = fact.effective_date or self.request_date
                series.has_explicit_ongoing = True
        elif fact_type is EvidenceFactType.RECURRENCE_CONFIRMATION:
            series.confirm_next = True
        elif fact_type is EvidenceFactType.RECURRING_EXPENSE_NOTICE:
            if fact.amount is None:
                self.diagnostics.append(
                    ForecastDiagnostic("unbounded_recurring_debit", (fact.fact_id,), True)
                )
                self.blocks = True
                series.reason_code = "unbounded_notice"
                series.stopped = True

    # -- phase 5 -------------------------------------------------------

    def _merge_explicit_effects(self) -> None:
        for effect in self.normalization.dated_cash_effects:
            if effect.amount_home is None:
                continue
            matches = {
                series
                for event_id in effect.source_event_ids
                for series in self._series_by_target.get(event_id, ())
            }
            if len(matches) == 1:
                family_id = next(iter(matches)).family_id
                self.occurrences = [
                    occurrence
                    for occurrence in self.occurrences
                    if not (
                        occurrence.origin == "fixed_recurrence"
                        and occurrence.family_id == family_id
                        and occurrence.direction is effect.direction
                        and occurrence.date == effect.effect_date
                    )
                ]
            self.occurrences.append(
                ProjectedOccurrence(
                    family_id=effect.record_id,
                    date=effect.effect_date,
                    direction=effect.direction,
                    source_amount=effect.source_amount,
                    source_currency=effect.source_currency,
                    home_amount=effect.amount_home,
                    origin="explicit",
                    source_event_ids=effect.source_event_ids,
                    source_fact_ids=effect.source_fact_ids,
                )
            )

    # -- phase 6 -------------------------------------------------------

    def _project_variable(self) -> None:
        policy = self.policy.variable_spending
        residual: dict[tuple, list[NormalizedCashRecord]] = {}
        for record in self.normalization.historical_cash:
            if self.dispositions.get(record.record_id) != "variable":
                continue
            key = (record.category, record.home_currency, record.source_currency)
            residual.setdefault(key, []).append(record)

        if policy is VariableSpending.V1_MAX_CADENCED_OCCURRENCE:
            self._project_variable_v1(residual)
            return

        for (category, _home_currency, source_currency), records in sorted(
            residual.items(), key=lambda item: repr(item[0])
        ):
            months: dict[tuple[int, int], list[Decimal]] = {}
            incomplete = False
            for record in records:
                if record.settlement_date is None:
                    incomplete = True
                    break
                month_key = (record.settlement_date.year, record.settlement_date.month)
                months.setdefault(month_key, []).append(record.amount_home)
            request_month = (self.request_date.year, self.request_date.month)
            comparable = [
                month_key
                for month_key in sorted(months, reverse=True)
                if month_key < request_month
            ]
            usable = []
            for month_key in comparable[:3]:
                if incomplete:
                    break
                usable.append(month_key)
            if len(usable) < 2 or incomplete:
                self.diagnostics.append(
                    ForecastDiagnostic(
                        "variable_history_unbounded",
                        tuple(record.record_id for record in records[:3]),
                        True,
                    )
                )
                self.blocks = True
                continue
            totals = [sum(months[month_key], _HOME_ZERO) for month_key in usable]
            if policy is VariableSpending.V0_MAX_COMPLETE_MONTH:
                envelope = max(totals)
            else:
                mean = sum(totals, _HOME_ZERO) / Decimal(len(totals))
                envelope = (mean / _CENT).to_integral_value(
                    rounding="ROUND_UP"
                ) * _CENT
            family_id = f"variable:{category}:{source_currency.value}"
            self._emit_envelope(category, family_id, envelope)

    def _emit_envelope(self, category: str, family_id: str, envelope: Decimal) -> None:
        request_month = (self.request_date.year, self.request_date.month)
        months = [request_month]
        year, month = _add_months(*request_month, 1)
        while date(year, month, 1) <= self.horizon_end:
            months.append((year, month))
            year, month = _add_months(year, month, 1)
        for month_key in months:
            if month_key == request_month:
                day = self.request_date
            else:
                day = date(*month_key, 1)
            if day > self.horizon_end:
                continue
            self.occurrences.append(
                ProjectedOccurrence(
                    family_id=family_id,
                    date=day,
                    direction=Direction.DEBIT,
                    source_amount=None,
                    source_currency=self.home_currency,
                    home_amount=envelope,
                    origin="variable_envelope",
                    source_event_ids=(),
                    source_fact_ids=(),
                )
            )

    def _project_variable_v1(self, residual) -> None:
        families: dict[tuple, list[NormalizedCashRecord]] = {}
        for records in residual.values():
            for record in records:
                families.setdefault(self._series_key(record), []).append(record)
        for key, records in sorted(families.items(), key=lambda item: repr(item[0])):
            observations = sorted(
                records, key=lambda r: (r.settlement_date, r.record_id)
            )
            series = self._family_series(key, records)
            if series is None or series.cadence is None:
                continue
            max_amount = max(
                observation.home_amount for observation in series.observations
            )
            family_id = (
                f"variable:{key[0]}:{series.source_currency.value}:"
                f"{series.anchor_record_id.split(':')[-1]}"
            )
            for candidate in self._project_dates(series):
                if candidate > self.request_date:
                    self.occurrences.append(
                        ProjectedOccurrence(
                            family_id=family_id,
                            date=candidate,
                            direction=Direction.DEBIT,
                            source_amount=None,
                            source_currency=self.home_currency,
                            home_amount=max_amount,
                            origin="variable_series",
                            source_event_ids=(),
                            source_fact_ids=(),
                        )
                    )

    # -- phase 7 -------------------------------------------------------

    def _convert(
        self,
        source_amount: Decimal,
        source_currency: CurrencyCode,
        settlement_date: date | None,
        source_ids: tuple[str, ...],
        is_debit: bool,
    ) -> Decimal | None:
        if source_currency is self.home_currency:
            return source_amount
        if settlement_date is None:
            raise ForecastBuildError("fx_settlement_date_missing", source_ids)
        key = (settlement_date, source_currency, self.home_currency)
        try:
            rate = self._rate_index[key]
        except KeyError:
            if is_debit:
                self.diagnostics.append(
                    ForecastDiagnostic(
                        "fx_rate_missing_debit",
                        source_ids
                        + (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
                        True,
                    )
                )
                self.blocks = True
            else:
                self.diagnostics.append(
                    ForecastDiagnostic(
                        "fx_rate_missing_credit",
                        source_ids
                        + (f"{key[0].isoformat()}:{key[1].value}:{key[2].value}",),
                        False,
                    )
                )
            return None
        return source_amount * rate

    def _project_income_and_fx(self) -> None:
        income_families: dict[str, list[NormalizedCashRecord]] = {}
        for record in self.normalization.historical_cash:
            if self.dispositions.get(record.record_id) != "income_history":
                continue
            income_families.setdefault(self._series_key(record), []).append(record)

        for key, records in sorted(income_families.items(), key=lambda item: repr(item[0])):
            series = self._family_series(key, records)
            if series is None:
                continue
            self._project_income_series(series)

    def _project_income_series(self, series: _Series) -> None:
        try:
            if (
                self.policy.income_continuation
                is IncomeContinuation.I0_EXPLICIT_ONGOING
            ):
                if not series.has_explicit_ongoing:
                    series.reason_code = "no_explicit_ongoing"
                    return
                if series.stopped:
                    return
                if series.cadence is None or series.amount is None:
                    return
            else:
                if series.stopped:
                    return
                if series.cadence is None or series.amount is None:
                    return
                if not self._select_amount(series):
                    return
                expected = self._next_expected_after_anchor(series)
                if expected is not None and expected <= self.request_date:
                    series.reason_code = "stale_credit"
                    return
            candidates = [
                candidate
                for candidate in self._project_dates(series)
                if candidate > self.request_date
            ]
            generated: list[date] = []
            for candidate in candidates:
                amount = self._fixed_amount_for(series, candidate, len(generated))
                if amount is None:
                    continue
                source_amount = (
                    series.source_amount
                    if series.source_currency is not self.home_currency
                    and series.source_amount is not None
                    else amount
                )
                home = self._convert(
                    source_amount,
                    series.source_currency,
                    candidate,
                    (series.anchor_record_id.split(":")[-1],),
                    is_debit=False,
                )
                if home is None:
                    continue
                self.occurrences.append(
                    ProjectedOccurrence(
                        family_id=series.family_id,
                        date=candidate,
                        direction=Direction.CREDIT,
                        source_amount=source_amount,
                        source_currency=series.source_currency,
                        home_amount=home,
                        origin="fixed_recurrence",
                        source_event_ids=(series.anchor_record_id.split(":")[-1],),
                        source_fact_ids=series.applied_fact_ids,
                    )
                )
                generated.append(candidate)
                if series.confirm_next:
                    break
            series.generated_dates_list = generated
        finally:
            self._trace_income(series)

    def _trace_income(self, series: _Series) -> None:
        generated = getattr(series, "generated_dates_list", [])
        self.traces.append(
            SeriesTrace(
                family_id=series.family_id,
                direction=series.direction,
                category=series.category,
                observations=tuple(
                    (observation.date, observation.home_amount)
                    for observation in series.observations
                ),
                observation_record_ids=tuple(
                    observation.record_id for observation in series.observations
                ),
                cadence=series.cadence,
                amount_rule=series.amount_rule,
                applied_fact_ids=series.applied_fact_ids,
                generated_dates=tuple(generated),
                replacement_decisions=(),
                reason_code=series.reason_code,
            )
        )

    def _next_expected_after_anchor(self, series: _Series) -> date | None:
        anchor = series.observations[-1].date
        if series.cadence in ("month_end", "month_day"):
            offset = 1
            detail = (
                anchor.day
                if series.cadence == "month_day"
                else None
            )
            if detail is None:
                candidate = date(*_add_months(anchor.year, anchor.month, 1), 1)
                return candidate.replace(
                    day=_last_day_of_month(candidate.year, candidate.month)
                )
            return _monthly_date(anchor.year, anchor.month, detail, 1)
        if series.cadence == "weekly_7":
            return anchor + timedelta(days=7)
        if series.cadence == "weekly_14":
            return anchor + timedelta(days=14)
        if series.cadence in ("tolerant_weekly_7", "tolerant_weekly_14"):
            dates = self._project_dates(series)
            return dates[0] if dates else None
        return None

    def _first_future(self, series: _Series) -> date | None:
        dates = self._project_dates(series)
        return dates[0] if dates else None

    # -- fixed debit series projection ----------------------------------

    def _project_fixed_debits(self) -> None:
        for key, records in sorted(self._families.items(), key=lambda item: repr(item[0])):
            if records[0].direction is Direction.CREDIT:
                continue
            series = self._family_series(key, records)
            if series is None:
                for record in records:
                    self.dispositions.setdefault(record.record_id, "non_recurring")
                continue
            if series.cadence is None:
                for record in records:
                    self.dispositions.setdefault(
                        record.record_id,
                        "variable" if self._is_variable_candidate(records) else "non_recurring",
                    )
                self._trace(series)
                continue
            if series.amount is None:
                for record in records:
                    self.dispositions.setdefault(record.record_id, "variable")
                self._trace(series)
                continue
            for record in records:
                self.dispositions.setdefault(record.record_id, "fixed")
            if series.stopped:
                self._trace(series)
                continue
            candidates = self._project_dates(series)
            candidates = [d for d in candidates if d > self.request_date]
            if getattr(series, "resume_from", None) is not None:
                candidates = [d for d in candidates if d >= series.resume_from]
                if (
                    self.request_date < series.resume_from <= self.horizon_end
                    and (
                        not candidates or candidates[0] != series.resume_from
                    )
                ):
                    if self._resume_boundary_supported(series):
                        if candidates:
                            candidates.pop(0)
                        candidates.insert(0, series.resume_from)
            if not candidates:
                self._trace(series)
                continue
            replaced = self._apply_date_replacement(series, candidates)
            generated: list[date] = []
            for index, candidate in enumerate(candidates):
                if candidate <= self.request_date:
                    continue
                amount = self._fixed_amount_for(series, candidate, index)
                if amount is None:
                    continue
                home = self._convert(
                    amount,
                    series.source_currency,
                    candidate,
                    (series.anchor_record_id.split(":")[-1],),
                    is_debit=True,
                )
                if home is None:
                    continue
                self.occurrences.append(
                    ProjectedOccurrence(
                        family_id=series.family_id,
                        date=candidate,
                        direction=Direction.DEBIT,
                        source_amount=amount,
                        source_currency=series.source_currency,
                        home_amount=home,
                        origin="fixed_recurrence",
                        source_event_ids=(series.anchor_record_id.split(":")[-1],),
                        source_fact_ids=series.applied_fact_ids,
                    )
                )
                generated.append(candidate)
            self._trace(series, replaced, generated)

    def _resume_boundary_supported(self, series: _Series) -> bool:
        return getattr(series, "amount_rule", "") == "resume_amount"

    def _apply_date_replacement(self, series: _Series, candidates: list[date]) -> list[str]:
        replacement = getattr(series, "date_replacement", None)
        if replacement is None:
            return []
        decisions = []
        future = [candidate for candidate in candidates if candidate > self.request_date]
        if series.cadence in ("month_end", "month_day", "tolerant_monthly"):
            original = next(
                (
                    candidate
                    for candidate in future
                    if (candidate.year, candidate.month)
                    == (replacement.year, replacement.month)
                ),
                None,
            )
        else:
            original = min(
                future,
                key=lambda candidate: abs((candidate - replacement).days),
                default=None,
            )
        if original is not None:
            candidates.remove(original)
            decisions.append(
                f"date_replacement:{original.isoformat()}->{replacement.isoformat()}"
            )
        if replacement > self.request_date and replacement <= self.horizon_end:
            if replacement not in candidates:
                candidates.insert(0, replacement)
                candidates.sort()
        return decisions

    def _fixed_amount_for(
        self, series: _Series, candidate: date, index: int
    ) -> Decimal | None:
        amount = series.amount
        if amount is None:
            return None
        amendment_from = getattr(series, "amendment_from", None)
        if (
            amendment_from is not None
            and candidate < amendment_from
            and series.pre_amendment_amount is not None
        ):
            amount = series.pre_amendment_amount
        next_cycle = getattr(series, "next_cycle_amount", None)
        if next_cycle is not None:
            if index == 0:
                amount = next_cycle
            else:
                amount = (
                    max(next_cycle, series.amount)
                    if series.direction is Direction.DEBIT
                    else min(next_cycle, series.amount)
                )
        if amendment_from is not None and candidate >= amendment_from:
            amount = series.amount
        return amount

    def _is_variable_candidate(self, records: list[NormalizedCashRecord]) -> bool:
        amounts = {record.amount_home for record in records}
        return len(amounts) > 1

    def _trace(
        self,
        series: _Series,
        replacement_decisions: list[str] | None = None,
        generated_dates: list[date] | None = None,
    ) -> None:
        self.traces.append(
            SeriesTrace(
                family_id=series.family_id,
                direction=series.direction,
                category=series.category,
                observations=tuple(
                    (observation.date, observation.home_amount)
                    for observation in series.observations
                ),
                observation_record_ids=tuple(
                    observation.record_id for observation in series.observations
                ),
                cadence=series.cadence,
                amount_rule=series.amount_rule,
                applied_fact_ids=series.applied_fact_ids,
                generated_dates=tuple(generated_dates or ()),
                replacement_decisions=tuple(replacement_decisions or ()),
                reason_code=series.reason_code,
            )
        )

    # -- phase 8 -------------------------------------------------------

    def _build_ledger(self) -> list[Checkpoint]:
        checkpoints: list[Checkpoint] = []
        cash = self.case.profile.current_available_balance
        reserved = _HOME_ZERO
        minimum = self.case.profile.minimum_balance_to_keep

        def emit(
            day: date,
            kind: str,
            delta: Decimal | None,
            delta_kind: str | None,
            family_id: str | None,
            source_ids: tuple[str, ...],
            reason_code: str,
            cash_reserve_delta: Decimal = _HOME_ZERO,
            cash_delta: Decimal = _HOME_ZERO,
        ) -> None:
            nonlocal cash, reserved
            cash += cash_delta
            reserved += cash_reserve_delta
            spendable = cash - reserved
            headroom = spendable - minimum
            checkpoints.append(
                Checkpoint(
                    date=day,
                    kind=kind,
                    cash_balance=cash,
                    reserved_balance=reserved,
                    spendable_balance=spendable,
                    headroom=headroom,
                    delta=delta,
                    delta_kind=delta_kind,
                    family_id=family_id,
                    source_ids=source_ids,
                    reason_code=reason_code,
                )
            )

        emit(
            self.request_date,
            "opening",
            None,
            None,
            None,
            (),
            "opening",
        )

        for reserve in sorted(
            self.normalization.opening_reserves, key=lambda r: r.record_id
        ):
            emit(
                self.request_date,
                "reserve",
                -reserve.amount_home,
                "reserve",
                reserve.record_id,
                reserve.source_event_ids,
                "opening_reserve",
                cash_reserve_delta=reserve.amount_home,
            )

        dated: dict[date, list[dict]] = {}
        for reserve in self.normalization.opening_reserves:
            if (
                reserve.settlement_date is not None
                and self.request_date <= reserve.settlement_date <= self.horizon_end
            ):
                dated.setdefault(reserve.settlement_date, []).append(
                    {
                        "kind": "reserve_settlement",
                        "record_id": reserve.record_id,
                        "amount": reserve.amount_home,
                        "direction": reserve.direction,
                        "source_ids": reserve.source_event_ids,
                    }
                )
        for occurrence in self.occurrences:
            if self.request_date <= occurrence.date <= self.horizon_end:
                dated.setdefault(occurrence.date, []).append(
                    {
                        "kind": "occurrence",
                        "record_id": f"{occurrence.family_id}@{occurrence.date.isoformat()}",
                        "amount": occurrence.home_amount,
                        "direction": occurrence.direction,
                        "source_ids": occurrence.source_event_ids
                        + occurrence.source_fact_ids,
                        "family_id": occurrence.family_id,
                        "origin": occurrence.origin,
                    }
                )

        for day in sorted(dated):
            items = dated[day]
            debits = sorted(
                [
                item
                for item in items
                if item["direction"] is Direction.DEBIT
                or item["kind"] == "reserve_settlement"
                ],
                key=lambda item: item["record_id"],
            )
            credits = sorted(
                [item for item in items if item["direction"] is Direction.CREDIT],
                key=lambda item: item["record_id"],
            )
            if (
                self.policy.same_day_order
                is UnknownSameDayOrder.CREDIT_DEBIT_PAYMENT
            ):
                ordered = credits + debits
            else:
                ordered = debits + credits
            for item in ordered:
                if item["kind"] == "reserve_settlement":
                    emit(
                        day,
                        "reserve_settlement",
                        _HOME_ZERO,
                        "reserve_release",
                        item["record_id"],
                        item["source_ids"],
                        "reserve_settled",
                        cash_reserve_delta=-item["amount"],
                        cash_delta=-item["amount"],
                    )
                elif item["direction"] is Direction.DEBIT:
                    emit(
                        day,
                        "debit",
                        -item["amount"],
                        "debit",
                        item.get("family_id"),
                        item["source_ids"],
                        "projected_debit"
                        if item.get("origin") != "variable_envelope"
                        else "variable_envelope",
                        cash_delta=-item["amount"],
                    )
                else:
                    emit(
                        day,
                        "credit",
                        item["amount"],
                        "credit",
                        item.get("family_id"),
                        item["source_ids"],
                        "projected_credit",
                        cash_delta=item["amount"],
                    )
        return checkpoints

    def run(self) -> BaselineForecast:
        self._classify_histories()

        series_by_target: dict[str, list[_Series]] = {}
        for key, records in self._families.items():
            series = self._family_series(key, records)
            if series is None:
                continue
            if not self._detect_cadence(series):
                continue
            for record in records:
                series_by_target.setdefault(
                    record.record_id.split(":")[-1], []
                ).append(series)
            if records[0].direction is Direction.CREDIT:
                self._select_amount(series)
                continue
            if not self._select_amount(series):
                continue
            for record in records:
                self.dispositions[record.record_id] = "fixed"

        self._apply_facts(series_by_target)
        self._series_by_target = series_by_target

        for records in self._families.values():
            for record in records:
                if self.dispositions.get(record.record_id) is None:
                    self.dispositions[record.record_id] = "variable"

        self._project_variable()
        self._project_income_and_fx()
        self._project_fixed_debits()
        self._merge_explicit_effects()

        checkpoints = self._build_ledger()
        headroom_values = [checkpoint.headroom for checkpoint in checkpoints]
        minimum_headroom = (
            min(headroom_values) if headroom_values and not self.blocks else None
        )
        for trace in self.traces:
            pass
        return BaselineForecast(
            request_id=self.case.request.request_id,
            request_date=self.request_date,
            horizon_end=self.horizon_end,
            opening_cash=self.case.profile.current_available_balance,
            minimum_balance=self.case.profile.minimum_balance_to_keep,
            opening_reserved=sum(
                (reserve.amount_home for reserve in self.normalization.opening_reserves),
                _HOME_ZERO,
            ),
            series_traces=tuple(self.traces),
            projected_occurrences=tuple(
                sorted(
                    (
                        occurrence
                        for occurrence in self.occurrences
                        if occurrence.date <= self.horizon_end
                    ),
                    key=lambda occurrence: (
                        occurrence.date,
                        occurrence.family_id,
                    ),
                )
            ),
            checkpoints=tuple(checkpoints),
            diagnostics=tuple(self.diagnostics),
            blocks_downstream=self.blocks,
            minimum_headroom=minimum_headroom,
        )


def build_baseline_forecast(
    case: RequestCase,
    evidence,
    normalization: EventNormalization,
    policy: ForecastPolicy = DEFAULT_FORECAST_POLICY,
) -> BaselineForecast:
    """Build one deterministic baseline forecast for the validated inputs.

    Pure: reads no files, environment, clock, provider, or global cache and
    writes nothing. Fails closed via ``ForecastBuildError`` for an
    unrepresentable input contract; grounded uncertainty instead produces
    conservative diagnostics with ``blocks_downstream``.
    """
    return _Builder(case, evidence, normalization, policy).run()

"""WP-09B public-sample oracle, comparison, and baseline metrics.

Deterministic, offline, standard-library-only evaluation boundary. It loads
the 25 public ``sample_requests.csv`` solved columns strictly in the evaluation
layer only, predicts each repository sample case first through the accepted
``predict_case`` seam, then joins expected values by ``request_id`` and reports
per-row comparisons, a finite mismatch taxonomy, aggregate metrics, scenario
breakdowns, and separated optimism warnings.

Product predictions never read solved columns: ``DatasetRepository`` exposes
only the eight input fields for sample cases, and this module joins expected
values only after prediction. The default CLI is non-mutating, writes nothing,
prints deterministic JSON, and does not fail solely because a public value
differs; it exits nonzero for an incomplete report, an unmapped mismatch, or a
contract/safety failure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.domain import (  # noqa: E402
    AffordabilityStatus,
    CurrencyCode,
    Direction,
    EventType,
    EvidenceFactType,
    Flexibility,
    PaymentMethod,
    RequestCase,
    RequestScope,
)
from buy_or_wait.output import (  # noqa: E402
    OUTPUT_COLUMNS,
    OutputRow,
    OutputValidationError,
    parse_output_row,
    serialize_output_row,
    validate_output_row,
)
from buy_or_wait.pipeline import (  # noqa: E402
    DecisionPolicy,
    PredictionTrace,
    SELECTED_DECISION_POLICY,
    predict_case,
)
from buy_or_wait.repository import DatasetRepository  # noqa: E402

SCHEMA_VERSION = "wp-09b-v1"
OUTPUT_CONTRACT = "wp-08-accepted-2026-09-13"

# The physical sample file keeps its eight input columns plus the seven solved
# output columns. ``request_id`` is the join key and appears in both halves, so
# the 15-column header is exactly the 8 input columns followed by the 7 solved
# output fields (which together equal ``OUTPUT_COLUMNS`` with ``request_id``
# counted once).
SAMPLE_INPUT_COLUMNS: tuple[str, ...] = (
    "request_id",
    "user_id",
    "request_date",
    "request_type",
    "requested_amount",
    "desired_completion_date",
    "allows_partial_payment",
    "request_text",
)

SAMPLE_OUTPUT_COLUMNS: tuple[str, ...] = tuple(
    column for column in OUTPUT_COLUMNS if column != "request_id"
)

SAMPLE_HEADER: tuple[str, ...] = SAMPLE_INPUT_COLUMNS + SAMPLE_OUTPUT_COLUMNS

MISMATCH_CATEGORIES = ("policy", "evidence", "eligibility", "arithmetic", "formatting")
SCENARIOS = (
    "preference_only_capacity",
    "salary_change_stop",
    "pending_debit",
    "pending_credit",
    "fx",
    "image_evidence",
    "partial",
    "installments",
    "spending_changes",
)
OPTIMISM_WARNINGS = (
    "optimistic_safe_amount",
    "optimistic_earlier_date",
    "optimistic_newly_affordable",
)

_RECURRENCE_CHANGE_TYPES = frozenset(
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


class EvaluationError(ValueError):
    """Source-safe gate failure with a stable reason code and request/source IDs."""

    def __init__(self, reason_code: str, request_id: str | None = None) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.request_id = request_id


# --- expected solved rows ----------------------------------------------------


@dataclass(frozen=True)
class ExpectedSample:
    request_id: str
    raw: Mapping[str, str]
    row: OutputRow


def load_sample_oracle(dataset_root: Path) -> tuple[ExpectedSample, ...]:
    """Strictly load the 15-column sample header and one canonical expected row
    per unique request ID, in file order.

    Rejects a missing/wrong header, a duplicate or blank request ID, or a
    solved row that the accepted output codec cannot parse canonically.
    """
    path = Path(dataset_root) / "sample_requests.csv"
    if not path.is_file():
        raise EvaluationError("missing_sample_requests_file")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != SAMPLE_HEADER:
            raise EvaluationError("unexpected_sample_header")
        expected: list[ExpectedSample] = []
        seen: set[str] = set()
        for row in reader:
            request_id = row.get("request_id") or ""
            if not request_id:
                raise EvaluationError("blank_sample_request_id")
            if request_id in seen:
                raise EvaluationError("duplicate_sample_request_id", request_id)
            seen.add(request_id)
            raw = {column: row.get(column, "") for column in OUTPUT_COLUMNS}
            try:
                parsed = parse_output_row(raw)
            except OutputValidationError as error:
                raise EvaluationError(
                    f"unparseable_expected_row:{error.reason_code}", request_id
                ) from error
            expected.append(ExpectedSample(request_id, raw, parsed))
    return tuple(expected)


# --- per-row comparison ------------------------------------------------------


@dataclass(frozen=True)
class SampleComparison:
    request_id: str
    policy_id: str
    predicted: Mapping[str, str]
    expected: Mapping[str, str]
    mismatched: bool
    status_exact: bool
    method_exact: bool
    money_exact: bool
    signed_error: Decimal | None
    absolute_error: Decimal | None
    normalized_error: Decimal | None
    requested_amount: Decimal | None
    home_currency: CurrencyCode | None
    date_exact: bool
    date_empty_state: str
    signed_day_error: int | None
    absolute_day_error: int | None
    plan_raw_exact: bool
    plan_semantic_exact: bool
    plan_reason: str
    changes_raw_exact: bool
    changes_semantic_exact: bool
    changes_reason: str
    explanation_consistent: bool
    explanation_raw_equal: bool
    contract_valid: bool
    contract_failures: tuple[str, ...]
    formatting_issue: bool
    arithmetic_divergence: bool
    blocking_evidence: bool
    mismatch_reasons: tuple[tuple[str, str], ...]
    scenarios: frozenset[str]
    optimism: tuple[str, ...]


def _plan_reason(predicted: tuple[object, ...], expected: tuple[object, ...]) -> str:
    if predicted == expected:
        return "none"
    if len(predicted) != len(expected):
        return "payment_count_mismatch"
    return "payment_schedule_or_amount_mismatch"


def _changes_reason(predicted: tuple[object, ...], expected: tuple[object, ...]) -> str:
    if predicted == expected:
        return "none"
    if len(predicted) != len(expected):
        return "change_count_mismatch"
    return "change_membership_mismatch"


def _event_income_series_affected(baseline: BaselineForecast) -> bool:
    """True when any credit series trace was actively changed by evidence facts.

    Only credit (income) series that actually applied a recurrence amendment,
    stop, or one-cycle replacement count as salary change/stop evidence.
    """
    return any(
        series.direction is Direction.CREDIT
        and (series.applied_fact_ids or series.replacement_decisions)
        for series in baseline.series_traces
    )


def _event_recurrence_change_facts(trace: PredictionTrace, case: RequestCase) -> bool:
    """True when any evidence fact targets an income event with a recurrence change."""
    event_by_id = {event.event_id: event for event in case.events}
    return any(
        fact.fact_type in _RECURRENCE_CHANGE_TYPES
        and fact.target_event_id is not None
        and event_by_id.get(fact.target_event_id) is not None
        and event_by_id[fact.target_event_id].event_type is EventType.INCOME
        for fact in trace.evidence.facts
    )


def _event_pending_credit(trace: PredictionTrace, normalization: EventNormalization) -> bool:
    return any(
        effect.direction is Direction.CREDIT for effect in normalization.dated_cash_effects
    ) or any(
        fact.fact_type
        in (EvidenceFactType.PENDING_CREDIT, EvidenceFactType.CONFIRMED_FUTURE_CREDIT)
        for fact in trace.evidence.facts
    )


def _event_supports_installments(case: RequestCase) -> bool:
    """Installments are supported only when the user is willing to consider them.

    Membership is evidence metadata (the user's stated payment preferences in
    the profile), never an inference from the predicted method or a supplied
    option's mere presence.
    """
    return PaymentMethod.INSTALLMENTS in case.profile.payment_methods_user_will_consider


def _event_supports_partial(case: RequestCase) -> bool:
    """Partial payment is available only when both the request and the user allow it."""
    return case.request.allows_partial_payment and (
        PaymentMethod.PARTIAL_PAYMENT in case.profile.payment_methods_user_will_consider
    )


def _event_supports_spending_changes(case: RequestCase) -> bool:
    """Spending changes are supported when a non-protected, user-permitted,
    reducible-or-stoppable debit event exists in the case."""
    profile = case.profile
    protected = profile.expense_categories_to_protect
    reduce_categories = profile.expense_categories_user_is_willing_to_reduce
    stop_categories = profile.expense_categories_user_is_willing_to_stop
    for event in case.events:
        if event.direction is not Direction.DEBIT:
            continue
        if event.category in protected:
            continue
        reducible = event.flexibility in (
            Flexibility.REDUCIBLE,
            Flexibility.REDUCIBLE_OR_STOPPABLE,
        ) and event.category in reduce_categories
        stoppable = event.flexibility in (
            Flexibility.STOPPABLE,
            Flexibility.REDUCIBLE_OR_STOPPABLE,
        ) and event.category in stop_categories
        if reducible or stoppable:
            return True
    return False


def _scenarios(trace: PredictionTrace, case: RequestCase) -> frozenset[str]:
    """Scenario membership derived from supplied public evidence, not labels.

    Each predicate uses the case's financial/evidence facts (profile payment
    preferences, event lifecycle/status, evidence facts, and exchange rates).
    Plan-eligibility scenarios (partial, installments, spending changes, and
    preference-only capacity) are declared by the user's request/profile
    evidence and by the presence of the cited evidence facts, never by the
    predicted method, a supplied option's mere availability, or a predicted
    output label.
    """
    found: set[str] = set()
    normalization = trace.normalization
    baseline = trace.baseline
    home = case.profile.home_currency

    if case.images:
        found.add("image_evidence")

    any_fx = bool(case.relevant_rates) or any(
        record.source_currency != home
        for record in list(normalization.historical_cash)
        + list(normalization.opening_reserves)
        + list(normalization.dated_cash_effects)
    )
    if any_fx:
        found.add("fx")

    if normalization.opening_reserves:
        found.add("pending_debit")

    if _event_pending_credit(trace, normalization):
        found.add("pending_credit")

    if _event_recurrence_change_facts(trace, case) or _event_income_series_affected(baseline):
        found.add("salary_change_stop")

    if _event_supports_partial(case):
        found.add("partial")

    if _event_supports_installments(case):
        found.add("installments")

    if _event_supports_spending_changes(case):
        found.add("spending_changes")

    if _event_preference_only_capacity(case):
        found.add("preference_only_capacity")

    return frozenset(found)


def _event_preference_only_capacity(case: RequestCase) -> bool:
    """Preference-only capacity: the user has declined full payment, so a full
    amount cannot be authorized through a single accepted method regardless of
    whether available money exists.

    Declared from the user's stated payment preferences (full payment absent),
    which is FIN/EXP public evidence. Never derived from the predicted status,
    method, or safe amount.
    """
    return PaymentMethod.FULL_PAYMENT not in case.profile.payment_methods_user_will_consider


def _optimism(c: "SampleComparison") -> tuple[str, ...]:
    warnings: list[str] = []
    if c.signed_error is not None and c.signed_error > 0:
        warnings.append("optimistic_safe_amount")
    if (
        c.signed_day_error is not None
        and c.signed_day_error < 0
    ):
        warnings.append("optimistic_earlier_date")
    tier = {
        AffordabilityStatus.NOT_AFFORDABLE: 0,
        AffordabilityStatus.AFFORDABLE_LATER: 1,
        AffordabilityStatus.AFFORDABLE_WITH_PLAN: 2,
        AffordabilityStatus.AFFORDABLE_NOW: 3,
    }
    predicted_tier = tier.get(
        _predicted_status(c), tier.get(AffordabilityStatus.NOT_AFFORDABLE)
    )
    expected_tier = tier.get(
        _expected_status(c), tier.get(AffordabilityStatus.NOT_AFFORDABLE)
    )
    if predicted_tier >= 2 and expected_tier <= 1:
        warnings.append("optimistic_newly_affordable")
    return tuple(warnings)


def _predicted_status(c: "SampleComparison") -> AffordabilityStatus:
    return AffordabilityStatus(c.predicted["affordability_status"])


def _expected_status(c: "SampleComparison") -> AffordabilityStatus:
    return AffordabilityStatus(c.expected["affordability_status"])


def compare_sample(
    trace: PredictionTrace,
    expected: ExpectedSample,
    case: RequestCase | None = None,
) -> SampleComparison:
    """Compare one validated trace against one expected solved row.

    Pure, deterministic, offline. ``case`` is optional and supplies the
    requested amount, home currency, and scenario evidence; when absent,
    normalized money errors and scenario membership are omitted.
    """
    if trace.request_id != expected.request_id:
        raise EvaluationError("comparison_request_id_mismatch", trace.request_id)
    predicted_raw = serialize_output_row(trace.output_row)
    solved = SAMPLE_OUTPUT_COLUMNS
    predicted = {column: predicted_raw[column] for column in solved}
    expected_fields = {column: expected.raw[column] for column in solved}
    mismatched = any(predicted[column] != expected_fields[column] for column in solved)

    status_exact = predicted["affordability_status"] == expected_fields["affordability_status"]
    method_exact = (
        predicted["recommended_payment_method"]
        == expected_fields["recommended_payment_method"]
    )

    predicted_row = trace.output_row
    expected_row = expected.row

    requested_amount = case.request.requested_amount if case is not None else None
    home_currency = case.profile.home_currency if case is not None else None

    money_exact = predicted_row.amount_safe_to_pay == expected_row.amount_safe_to_pay
    signed_error = predicted_row.amount_safe_to_pay - expected_row.amount_safe_to_pay
    absolute_error = abs(signed_error)
    normalized_error = None
    if requested_amount is not None and requested_amount > 0:
        normalized_error = absolute_error / requested_amount

    pred_date = predicted_row.earliest_date_for_full_payment
    expected_date = expected_row.earliest_date_for_full_payment
    if pred_date is None and expected_date is None:
        date_empty_state = "both_empty"
        date_exact = True
    elif pred_date is None:
        date_empty_state = "predicted_empty"
        date_exact = False
    elif expected_date is None:
        date_empty_state = "expected_empty"
        date_exact = False
    else:
        date_empty_state = "both_present"
        date_exact = pred_date == expected_date
    signed_day_error = None
    absolute_day_error = None
    if pred_date is not None and expected_date is not None:
        signed_day_error = (pred_date - expected_date).days
        absolute_day_error = abs(signed_day_error)

    plan_raw_exact = predicted["payment_plan"] == expected_fields["payment_plan"]
    plan_semantic_exact = predicted_row.payment_plan == expected_row.payment_plan
    plan_reason = _plan_reason(predicted_row.payment_plan, expected_row.payment_plan)

    changes_raw_exact = (
        predicted["spending_changes_needed"] == expected_fields["spending_changes_needed"]
    )
    changes_semantic_exact = (
        predicted_row.spending_changes_needed == expected_row.spending_changes_needed
    )
    changes_reason = _changes_reason(
        predicted_row.spending_changes_needed, expected_row.spending_changes_needed
    )

    explanation_consistent = True  # predict_case ran the accepted validator
    explanation_raw_equal = (
        predicted["decision_explanation"] == expected_fields["decision_explanation"]
    )

    contract_valid = True
    contract_failures: tuple[str, ...] = ()

    formatting_issue = mismatched and predicted_row == expected_row
    arithmetic_divergence = (
        mismatched
        and predicted_row.amount_safe_to_pay != expected_row.amount_safe_to_pay
        and predicted_row.amount_safe_to_pay.quantize(Decimal("0.01"))
        == expected_row.amount_safe_to_pay.quantize(Decimal("0.01"))
    )
    blocking_evidence = (
        trace.normalization.blocks_downstream or trace.baseline.blocks_downstream
    )

    scenarios = _scenarios(trace, case) if case is not None else frozenset()

    comparison = SampleComparison(
        request_id=trace.request_id,
        policy_id=trace.policy_id,
        predicted=predicted,
        expected=expected_fields,
        mismatched=mismatched,
        status_exact=status_exact,
        method_exact=method_exact,
        money_exact=money_exact,
        signed_error=signed_error,
        absolute_error=absolute_error,
        normalized_error=normalized_error,
        requested_amount=requested_amount,
        home_currency=home_currency,
        date_exact=date_exact,
        date_empty_state=date_empty_state,
        signed_day_error=signed_day_error,
        absolute_day_error=absolute_day_error,
        plan_raw_exact=plan_raw_exact,
        plan_semantic_exact=plan_semantic_exact,
        plan_reason=plan_reason,
        changes_raw_exact=changes_raw_exact,
        changes_semantic_exact=changes_semantic_exact,
        changes_reason=changes_reason,
        explanation_consistent=explanation_consistent,
        explanation_raw_equal=explanation_raw_equal,
        contract_valid=contract_valid,
        contract_failures=contract_failures,
        formatting_issue=formatting_issue,
        arithmetic_divergence=arithmetic_divergence,
        blocking_evidence=blocking_evidence,
        mismatch_reasons=(),
        scenarios=scenarios,
        optimism=(),
    )
    reasons = classify_mismatch(comparison)
    return SampleComparison(
        request_id=comparison.request_id,
        policy_id=comparison.policy_id,
        predicted=comparison.predicted,
        expected=comparison.expected,
        mismatched=comparison.mismatched,
        status_exact=comparison.status_exact,
        method_exact=comparison.method_exact,
        money_exact=comparison.money_exact,
        signed_error=comparison.signed_error,
        absolute_error=comparison.absolute_error,
        normalized_error=comparison.normalized_error,
        requested_amount=comparison.requested_amount,
        home_currency=comparison.home_currency,
        date_exact=comparison.date_exact,
        date_empty_state=comparison.date_empty_state,
        signed_day_error=comparison.signed_day_error,
        absolute_day_error=comparison.absolute_day_error,
        plan_raw_exact=comparison.plan_raw_exact,
        plan_semantic_exact=comparison.plan_semantic_exact,
        plan_reason=comparison.plan_reason,
        changes_raw_exact=comparison.changes_raw_exact,
        changes_semantic_exact=comparison.changes_semantic_exact,
        changes_reason=comparison.changes_reason,
        explanation_consistent=comparison.explanation_consistent,
        explanation_raw_equal=comparison.explanation_raw_equal,
        contract_valid=comparison.contract_valid,
        contract_failures=comparison.contract_failures,
        formatting_issue=comparison.formatting_issue,
        arithmetic_divergence=comparison.arithmetic_divergence,
        blocking_evidence=comparison.blocking_evidence,
        mismatch_reasons=reasons,
        scenarios=comparison.scenarios,
        optimism=_optimism(comparison),
    )


def classify_mismatch(comparison: SampleComparison) -> tuple[tuple[str, str], ...]:
    """Assign exactly one stable category/reason to a mismatched comparison.

    Deterministic priority: formatting, evidence, arithmetic, eligibility,
    then policy. A matched comparison yields no reason.
    """
    if not comparison.mismatched:
        return ()
    if comparison.formatting_issue:
        return (("formatting", "expected_canonical_divergence"),)
    if comparison.blocking_evidence:
        return (("evidence", "blocking_unresolved_evidence"),)
    if comparison.arithmetic_divergence:
        return (("arithmetic", "cent_rounding_divergence"),)
    if not (
        comparison.status_exact
        and comparison.method_exact
        and comparison.plan_semantic_exact
        and comparison.changes_semantic_exact
    ):
        return (("eligibility", "decision_eligibility"),)
    if not (comparison.money_exact and comparison.date_exact):
        return (("policy", "amount_or_date_forecast"),)
    return (("formatting", "unmapped_mismatch"),)


# --- aggregate metrics -------------------------------------------------------


@dataclass(frozen=True)
class SampleReport:
    policy_id: str
    comparisons: tuple[SampleComparison, ...]
    metrics: Mapping[str, object]
    counts: Mapping[str, int]
    dataset_fingerprint: str

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "output_contract": OUTPUT_CONTRACT,
            "policy_id": self.policy_id,
            "dataset_fingerprint": self.dataset_fingerprint,
            "counts": dict(self.counts),
            "metrics": dict(self.metrics),
            "comparisons": [comparison_to_json(comparison) for comparison in self.comparisons],
        }


def _money_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def comparison_to_json(comparison: SampleComparison) -> dict[str, object]:
    return {
        "request_id": comparison.request_id,
        "policy_id": comparison.policy_id,
        "predicted": dict(comparison.predicted),
        "expected": dict(comparison.expected),
        "mismatched": comparison.mismatched,
        "status_exact": comparison.status_exact,
        "method_exact": comparison.method_exact,
        "money_exact": comparison.money_exact,
        "signed_error": _money_str(comparison.signed_error),
        "absolute_error": _money_str(comparison.absolute_error),
        "normalized_error": _money_str(comparison.normalized_error),
        "home_currency": (
            comparison.home_currency.value if comparison.home_currency is not None else None
        ),
        "date_exact": comparison.date_exact,
        "date_empty_state": comparison.date_empty_state,
        "signed_day_error": comparison.signed_day_error,
        "absolute_day_error": comparison.absolute_day_error,
        "plan_raw_exact": comparison.plan_raw_exact,
        "plan_semantic_exact": comparison.plan_semantic_exact,
        "plan_reason": comparison.plan_reason,
        "changes_raw_exact": comparison.changes_raw_exact,
        "changes_semantic_exact": comparison.changes_semantic_exact,
        "changes_reason": comparison.changes_reason,
        "explanation_consistent": comparison.explanation_consistent,
        "explanation_raw_equal": comparison.explanation_raw_equal,
        "contract_valid": comparison.contract_valid,
        "contract_failures": list(comparison.contract_failures),
        "mismatch_reasons": [
            {"category": category, "reason_code": reason_code}
            for category, reason_code in comparison.mismatch_reasons
        ],
        "scenarios": sorted(comparison.scenarios),
        "optimism": sorted(comparison.optimism),
    }


def _confusion_table(
    comparisons: Sequence[SampleComparison],
    field: str,
) -> dict[str, object]:
    """Return an exact raw-string confusion table for one output field."""
    values = sorted(
        {
            comparison.predicted[field]
            for comparison in comparisons
        }
        | {
            comparison.expected[field]
            for comparison in comparisons
        }
    )
    table: dict[str, object] = {}
    for row in values:
        table[row] = {
            column: sum(
                1
                for comparison in comparisons
                if comparison.predicted[field] == row
                and comparison.expected[field] == column
            )
            for column in values
        }
    return table


def _joint_confusion_table(comparisons: Sequence[SampleComparison]) -> dict[str, object]:
    def joint(fields: Mapping[str, str]) -> str:
        return (
            f"{fields['affordability_status']}|"
            f"{fields['recommended_payment_method']}"
        )

    values = sorted(
        {joint(comparison.predicted) for comparison in comparisons}
        | {joint(comparison.expected) for comparison in comparisons}
    )
    return {
        row: {
            column: sum(
                1
                for comparison in comparisons
                if joint(comparison.predicted) == row
                and joint(comparison.expected) == column
            )
            for column in values
        }
        for row in values
    }


def _money_by_currency(comparisons: Sequence[SampleComparison]) -> dict[str, object]:
    grouped: dict[str, list[SampleComparison]] = {}
    for comparison in comparisons:
        if comparison.home_currency is None:
            continue
        grouped.setdefault(comparison.home_currency.value, []).append(comparison)
    result: dict[str, object] = {}
    for currency, members in grouped.items():
        exact = sum(1 for member in members if member.money_exact)
        abs_errors = [member.absolute_error for member in members if member.absolute_error is not None]
        signed_errors = [member.signed_error for member in members if member.signed_error is not None]
        result[currency] = {
            "count": len(members),
            "exact_count": exact,
            "mean_absolute_error": (
                format(sum(abs_errors, Decimal("0")) / len(abs_errors), "f")
                if abs_errors
                else None
            ),
            "mean_signed_error": (
                format(sum(signed_errors, Decimal("0")) / len(signed_errors), "f")
                if signed_errors
                else None
            ),
        }
    return result


def summarize(comparisons: Sequence[SampleComparison]) -> dict[str, object]:
    """Aggregate metric arithmetic over the ordered comparison rows.

    Cross-currency raw money is never averaged; the only cross-currency
    aggregate is the mean of per-request normalized errors. Optimism signals,
    contract failures, and explanation consistency are kept separate from
    accuracy metrics.
    """
    total = len(comparisons)
    status_exact = sum(1 for c in comparisons if c.status_exact)
    method_exact = sum(1 for c in comparisons if c.method_exact)
    joint_exact = sum(1 for c in comparisons if c.status_exact and c.method_exact)
    money_exact = sum(1 for c in comparisons if c.money_exact)
    date_exact = sum(1 for c in comparisons if c.date_exact)

    empty_states = {"both_present": 0, "predicted_empty": 0, "expected_empty": 0, "both_empty": 0}
    for c in comparisons:
        empty_states[c.date_empty_state] += 1

    money_per_request: dict[str, object] = {}
    for c in comparisons:
        if c.requested_amount is None:
            continue
        money_per_request[c.request_id] = {
            "signed_error": _money_str(c.signed_error),
            "absolute_error": _money_str(c.absolute_error),
            "normalized_error": _money_str(c.normalized_error),
            "requested_amount": _money_str(c.requested_amount),
            "currency": c.home_currency.value if c.home_currency is not None else None,
        }
    normalized = [c.normalized_error for c in comparisons if c.normalized_error is not None]

    plan_raw = sum(1 for c in comparisons if c.plan_raw_exact)
    plan_semantic = sum(1 for c in comparisons if c.plan_semantic_exact)
    changes_raw = sum(1 for c in comparisons if c.changes_raw_exact)
    changes_semantic = sum(1 for c in comparisons if c.changes_semantic_exact)
    plan_reasons: dict[str, int] = {}
    changes_reasons: dict[str, int] = {}
    for c in comparisons:
        plan_reasons[c.plan_reason] = plan_reasons.get(c.plan_reason, 0) + 1
        changes_reasons[c.changes_reason] = changes_reasons.get(c.changes_reason, 0) + 1

    explanation_consistent = sum(1 for c in comparisons if c.explanation_consistent)
    explanation_raw_equal = sum(1 for c in comparisons if c.explanation_raw_equal)

    contract_failures = sum(1 for c in comparisons if not c.contract_valid)
    unmapped = sum(
        1
        for c in comparisons
        if c.mismatched
        and (not c.mismatch_reasons or c.mismatch_reasons[0][1] == "unmapped_mismatch")
    )
    invariant_failures: dict[str, int] = {}
    failed_request_ids: dict[str, list[str]] = {}
    for c in comparisons:
        for invariant in c.contract_failures:
            invariant_failures[invariant] = invariant_failures.get(invariant, 0) + 1
            failed_request_ids.setdefault(invariant, []).append(c.request_id)
    mismatch_categories: dict[str, int] = {}
    for c in comparisons:
        for category, _ in c.mismatch_reasons:
            mismatch_categories[category] = mismatch_categories.get(category, 0) + 1

    scenarios: dict[str, object] = {
        name: {
            "count": sum(1 for c in comparisons if name in c.scenarios),
            "denominator": total,
        }
        for name in SCENARIOS
    }

    optimism = {
        warning: sum(1 for c in comparisons if warning in c.optimism)
        for warning in OPTIMISM_WARNINGS
    }

    return {
        "total_rows": total,
        "contract": {
            "failures": contract_failures,
            "by_invariant": invariant_failures,
            "request_ids_by_invariant": failed_request_ids,
            "unmapped_mismatches": unmapped,
        },
        "categorical": {
            "status_exact": status_exact,
            "method_exact": method_exact,
            "joint_exact": joint_exact,
            "status_confusion": _confusion_table(comparisons, "affordability_status"),
            "method_confusion": _confusion_table(
                comparisons, "recommended_payment_method"
            ),
            "joint_confusion": _joint_confusion_table(comparisons),
        },
        "money": {
            "exact_count": money_exact,
            "per_request": money_per_request,
            "by_currency": _money_by_currency(comparisons),
            "aggregate_normalized": (
                {
                    "count": len(normalized),
                    "mean": format(sum(normalized, Decimal("0")) / len(normalized), "f"),
                    "sum": format(sum(normalized, Decimal("0")), "f"),
                }
                if normalized
                else None
            ),
        },
        "date": {
            "exact_count": date_exact,
            "empty_state": empty_states,
        },
        "plan": {
            "raw_exact": plan_raw,
            "semantic_exact": plan_semantic,
            "reasons": plan_reasons,
        },
        "changes": {
            "raw_exact": changes_raw,
            "semantic_exact": changes_semantic,
            "reasons": changes_reasons,
        },
        "explanation": {
            "trace_consistent": explanation_consistent,
            "raw_equal": explanation_raw_equal,
        },
        "mismatch_categories": mismatch_categories,
        "scenarios": scenarios,
        "optimism": optimism,
    }


# --- batch run ---------------------------------------------------------------


def _dataset_fingerprint(dataset_root: Path) -> str:
    digest = hashlib.sha256()
    for name in sorted(
        path.name for path in Path(dataset_root).iterdir() if path.is_file()
    ):
        digest.update(name.encode("utf-8"))
        with (Path(dataset_root) / name).open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()


def run_samples(
    dataset_root: Path,
    policy: DecisionPolicy = SELECTED_DECISION_POLICY,
) -> SampleReport:
    """Predict every sample case first, then join expected solved rows.

    Deterministic and offline. Product prediction reads only the repository's
    eight input columns; expected values are loaded only here. Rejects a
    missing/extra/duplicate/reordered join and propagates any contract or
    validator failure.
    """
    repository = DatasetRepository.from_directory(Path(dataset_root))
    traces: list[tuple[RequestCase, PredictionTrace]] = []
    for case in repository.iter_request_cases(RequestScope.SAMPLE):
        trace = predict_case(case, policy)
        validate_output_row(trace.output_row, case, trace.baseline, trace.decision)
        traces.append((case, trace))

    oracle = load_sample_oracle(dataset_root)
    predicted_ids = [trace.request_id for _, trace in traces]
    expected_ids_in_order = [expected.request_id for expected in oracle]
    if predicted_ids != expected_ids_in_order:
        raise EvaluationError("sample_oracle_join_order_mismatch")

    comparisons = [
        compare_sample(trace, expected, case)
        for (case, trace), expected in zip(traces, oracle, strict=True)
    ]

    if len(predicted_ids) != len(set(predicted_ids)):
        raise EvaluationError("duplicate_prediction_request_id")

    counts = {
        "predicted": len(predicted_ids),
        "expected": len(oracle),
        "missing": 0,
        "extra": 0,
        "duplicate": 0,
        "contract_failures": sum(1 for c in comparisons if not c.contract_valid),
        "unmapped_mismatches": sum(
            1
            for c in comparisons
            if c.mismatched
            and (
                not c.mismatch_reasons
                or c.mismatch_reasons[0][1] == "unmapped_mismatch"
            )
        ),
    }
    return SampleReport(
        policy_id=policy.id,
        comparisons=tuple(comparisons),
        metrics=summarize(comparisons),
        counts=counts,
        dataset_fingerprint=_dataset_fingerprint(Path(dataset_root)),
    )


def _write_atomic(path: Path, text: str) -> None:
    path = Path(path)
    temp_path = path.with_name(path.name + ".tmp")
    payload = text.encode("utf-8")
    try:
        with open(temp_path, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        if temp_path.exists():
            temp_path.unlink()
        raise


# --- CLI ---------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the 25 public samples with the selected decision policy."
    )
    parser.add_argument("--dataset", default="dataset", type=Path)
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Optional path to write deterministic JSON (default prints to stdout).",
    )
    args = parser.parse_args(argv)
    try:
        report = run_samples(args.dataset, SELECTED_DECISION_POLICY)
    except EvaluationError as error:
        print(f"evaluation gate failed: {error}", file=sys.stderr)
        return 1
    payload = report.to_json()
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output is not None:
        _write_atomic(args.output, text)
    print(text, end="")
    failed = report.counts["contract_failures"] or report.counts["unmapped_mismatches"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

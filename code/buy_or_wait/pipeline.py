"""WP-09A one-case product composition and trace seam.

Composes the accepted deterministic stages (evidence -> events -> forecast ->
planning -> output build/validate) behind one pure, single-case ``predict_case``
entry point under one explicit ``DecisionPolicy`` and returns a validated
``OutputRow`` plus a compact ``PredictionTrace``.

Deterministic, offline, single-case, and side-effect free: reads no files,
inspects no request scope, loads no expected answers, writes no CSV, catches no
stage errors, generates no run ID, and collects no usage. WP-10 owns batch/CLI
composition.
"""

from __future__ import annotations

from dataclasses import dataclass

from buy_or_wait.domain import RequestCase
from buy_or_wait.evidence import EvidenceResolution, resolve_case_evidence
from buy_or_wait.events import EventNormalization, normalize_case_events
from buy_or_wait.forecast import (
    DEFAULT_FORECAST_POLICY, BaselineForecast, ForecastPolicy, build_baseline_forecast,
)
from buy_or_wait.output import OutputRow, build_output_row, validate_output_row
from buy_or_wait.planning import PlanningDecision, plan_request


@dataclass(frozen=True)
class DecisionPolicy:
    """One explicit, canonical global decision configuration."""

    forecast: ForecastPolicy

    @property
    def id(self) -> str:
        f = self.forecast
        return f"rv={f.recurrence_timing.value};" \
               f"var={f.variable_spending.value};" \
               f"inc={f.income_continuation.value};" \
               f"date={f.horizon_endpoint.value};" \
               f"order={f.same_day_order.value}"


DEFAULT_DECISION_POLICY = DecisionPolicy(forecast=DEFAULT_FORECAST_POLICY)

SELECTED_DECISION_POLICY = DEFAULT_DECISION_POLICY


@dataclass(frozen=True)
class PredictionTrace:
    """Compact, source-safe record of one prediction and its policy."""

    request_id: str
    policy_id: str
    evidence: EvidenceResolution
    normalization: EventNormalization
    baseline: BaselineForecast
    decision: PlanningDecision
    output_row: OutputRow


def predict_case(
    case: RequestCase,
    policy: DecisionPolicy = DEFAULT_DECISION_POLICY,
) -> PredictionTrace:
    """Run one validated case through the accepted stages and return a trace.

    Pure, deterministic, offline, single-case. Stage and validator failures
    propagate; no row or file is published on failure.
    """
    if not isinstance(case, RequestCase):
        raise TypeError("invalid_case")
    evidence = resolve_case_evidence(case)
    normalization = normalize_case_events(case, evidence)
    baseline = build_baseline_forecast(case, evidence, normalization, policy.forecast)
    decision = plan_request(case, baseline)
    row = build_output_row(case, baseline, decision)
    validate_output_row(row, case, baseline, decision)
    return PredictionTrace(
        request_id=case.request.request_id,
        policy_id=policy.id,
        evidence=evidence,
        normalization=normalization,
        baseline=baseline,
        decision=decision,
        output_row=row,
    )

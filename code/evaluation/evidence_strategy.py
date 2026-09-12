"""Offline evidence-strategy assessment (WP-03 evaluation-only module).

Measures the accepted WP-02 deterministic resolver against its independent
data-only evidence oracle and records one reproducible strategy decision:
retain the zero-call offline path, or identify the exact carrier IDs that
justify a separately authorized provider trial. This module is imported only
by evaluation code and tests; it never performs a live model or network call
and never changes a financial fact. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from buy_or_wait.domain import RequestScope  # noqa: E402
from buy_or_wait.evidence import (  # noqa: E402
    EvidenceDiagnostic,
    EvidenceFact,
    EvidenceResolution,
    resolve_case_evidence,
)
from buy_or_wait.repository import DatasetRepository  # noqa: E402

SCHEMA_VERSION = "wp-03-v1"
RESOLVER_CONTRACT = "wp-02-accepted-2026-09-12"

# Conservative WP-02 reason codes that intentionally do not request a model:
# the information is not in the carrier, cannot be uniquely grounded, or is
# excluded by policy.
INTENTIONAL_CONSERVATIVE_CODES = frozenset(
    {
        "unavailable_credit_no_cash",
        "unavailable_image_review",
        "unresolved_transfer_pair",
        "pending_debit_reserved_no_cash",
    }
)
BLOCKING_UNBOUNDED_DEBIT_CODES = frozenset(
    {"unresolved_required_debit_blocks"}
)
# Grounded, policy-permitted facts the deterministic resolver could not
# extract or validate. Only these justify a provider-trial decision.
MODEL_ELIGIBLE_CODES = frozenset({"unresolved_extractable_amount"})

OPTIMISTIC_FORBIDDEN_PAIRS = {
    # A conservative "no cash" outcome must never surface as an accepted
    # credited fact.
    "unavailable_credit_no_cash": {
        "confirmed_future_credit",
        "pending_credit",
        "settled_one_time_credit",
    },
    "unavailable_image_review": {"event_amount"},
    "unresolved_transfer_pair": {"internal_transfer_pair"},
    "pending_debit_reserved_no_cash": {"pending_credit", "confirmed_future_credit"},
    "unresolved_required_debit_blocks": {"pending_credit", "confirmed_future_credit"},
}

FACT_TYPES_BY_CARRIER = ("event_amount",)


class AssessmentError(Exception):
    """Invalid assessment gate: a WP-02 defect, never a reason to add a model."""


@dataclass(frozen=True)
class CarrierRow:
    carrier_type: str
    carrier_id: str
    facts: tuple[EvidenceFact, ...]
    diagnostics: tuple[EvidenceDiagnostic, ...]
    classification: str


@dataclass(frozen=True)
class EvidenceStrategyReport:
    selected_strategy: str
    decision_reason: str
    rejected_alternative: str
    carrier_counts: dict[str, int]
    classifications: dict[str, int]
    oracle: dict[str, int]
    model_eligible: tuple[dict[str, str], ...]
    model_usage: dict[str, int | float]
    dataset_fingerprint: str
    resolver_contract: str

    def to_json(self) -> str:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "dataset_fingerprint": self.dataset_fingerprint,
            "resolver_contract": self.resolver_contract,
            "selected_strategy": self.selected_strategy,
            "decision_reason": self.decision_reason,
            "rejected_alternative": self.rejected_alternative,
            "carrier_counts": self.carrier_counts,
            "classifications": self.classifications,
            "oracle": self.oracle,
            "model_eligible_carriers": list(self.model_eligible),
            "model_usage": self.model_usage,
        }
        return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _fact_types(facts: Sequence[EvidenceFact]) -> set[str]:
    return {fact.fact_type.value for fact in facts}


def _classify_carrier(
    resolution: EvidenceResolution,
) -> str:
    """Assign one strategy classification to one carrier row."""
    reasons = {diagnostic.reason_code for diagnostic in resolution.diagnostics}
    if any(reason in MODEL_ELIGIBLE_CODES for reason in reasons):
        return "model_eligible_unresolved"
    if _fact_types(resolution.facts):
        return "validated_fact"
    if any(reason in BLOCKING_UNBOUNDED_DEBIT_CODES for reason in reasons):
        return "blocking_unbounded_debit"
    if any(reason in INTENTIONAL_CONSERVATIVE_CODES for reason in reasons):
        return "intentional_conservative"
    raise AssessmentError(
        f"unclassified_diagnostic_reason:{sorted(reasons)!r}"
    )


def _check_optimistic_facts(
    rows: Mapping[tuple[str, str], CarrierRow],
) -> None:
    for (carrier_type, carrier_id), row in rows.items():
        if row.classification != "validated_fact":
            continue
        for diagnostic in row.diagnostics:
            forbidden = OPTIMISTIC_FORBIDDEN_PAIRS.get(
                diagnostic.reason_code, frozenset()
            )
            overlap = _fact_types(row.facts) & forbidden
            if overlap:
                raise AssessmentError(
                    "incorrect_optimistic_fact:"
                    f"{carrier_type}:{carrier_id}:{sorted(overlap)!r}"
                )


def _oracle_carriers(oracle: Mapping[str, object]) -> dict[tuple[str, str], dict]:
    """Build the expected-decision index from the independent WP-02 fixture."""
    expected: dict[tuple[str, str], dict] = {}
    message_oracle = oracle.get("sample_messages", {})
    if not isinstance(message_oracle, Mapping):
        raise AssessmentError("malformed_message_oracle")
    for carrier_id, entry in message_oracle.items():
        if carrier_id in {key[1] for key in expected}:
            raise AssessmentError(f"duplicate_oracle_carrier:{carrier_id}")
        expected[("message", carrier_id)] = dict(entry)
    image_oracle = oracle.get("images", {})
    if not isinstance(image_oracle, Mapping):
        raise AssessmentError("malformed_image_oracle")
    for carrier_id, entry in image_oracle.items():
        key = ("image", carrier_id)
        if key in expected:
            raise AssessmentError(f"duplicate_oracle_carrier:{carrier_id}")
        expected[key] = dict(entry)
    return expected


def _entry_facts(entry: Mapping[str, object]) -> list[dict]:
    """Normalize oracle entry fact data for both message and image shapes."""
    facts = entry.get("facts")
    if isinstance(facts, list) and facts:
        return [dict(item) for item in facts]
    if entry.get("fact_type"):
        return [dict(entry)]
    return []


def _expected_decision(entry: Mapping[str, object]) -> str:
    facts = _entry_facts(entry)
    if facts:
        return "fact"
    diagnostics = entry.get("diagnostics") or (
        [entry["diagnostic"]] if entry.get("diagnostic") else []
    )
    if not diagnostics:
        raise AssessmentError("malformed_oracle_entry")
    return "|".join(sorted(diagnostics))


def _resolved_decision(row: CarrierRow) -> str:
    if row.facts:
        return "fact"
    codes = sorted({diagnostic.reason_code for diagnostic in row.diagnostics})
    if not codes:
        raise AssessmentError(f"missing_disposition:{row.carrier_id}")
    return "|".join(codes)


def _oracle_value_mismatch(
    entry: Mapping[str, object], row: CarrierRow
) -> str:
    """Compare every value field the oracle records against resolved facts.

    Expected facts are matched to resolved facts in declaration order; the
    exact fact-type comparison already rejects different type multisets, and
    duplicates in type-preserving order keep positions stable. Every recorded
    field must match exactly; unrecorded resolved fields are WP-02 surface and
    are intentionally not compared here.
    """
    expected_facts = _entry_facts(entry)
    if len(expected_facts) != len(row.facts):
        return "fact_count"
    for expected, fact in zip(expected_facts, row.facts):
        for field_name in (
            "amount",
            "currency",
            "effective_date",
            "target_event_id",
        ):
            want = expected.get(field_name)
            if field_name == "target_event_id":
                got = fact.target_event_id
            elif field_name == "effective_date":
                got = str(fact.effective_date) if fact.effective_date else None
            elif field_name == "currency":
                got = fact.currency.value if fact.currency else None
            else:
                got = None if fact.amount is None else str(fact.amount)
            if want is None and got is None:
                continue
            if want is None or got is None:
                return f"{fact.fact_id}:{field_name}:{got!r}!={want!r}"
            if str(want) != str(got):
                return f"{fact.fact_id}:{field_name}:{got!r}!={want!r}"
    return ""


def _oracle_matches(
    rows: Mapping[tuple[str, str], CarrierRow],
    oracle: Mapping[str, object],
    extra_allowed: frozenset[tuple[str, str]] = frozenset(),
) -> tuple[int, int]:
    """Exact-oracle match of decisions, fact types, and reason codes.

    Carriers outside the oracle but present in the supplied repository carrier
    set (``extra_allowed``) still get one disposition; only unaccounted extras
    fail the gate.
    """
    expected = _oracle_carriers(oracle)
    match = 0
    mismatch: list[str] = []
    for key, entry in sorted(expected.items()):
        row = rows.get(key)
        if row is None:
            mismatch.append(f"missing:{key[1]}")
            continue
        resolved = _resolved_decision(row)
        want = _expected_decision(entry)
        if resolved != want:
            mismatch.append(f"{key[1]}:{resolved}!={want}")
            continue
        want_types = sorted(
            item["fact_type"]
            for item in _entry_facts(entry)
            if item.get("fact_type")
        )
        got_types = sorted(_fact_types(row.facts))
        if want_types != got_types:
            mismatch.append(f"{key[1]}:types:{got_types}!={want_types}")
            continue
        value_mismatch = _oracle_value_mismatch(entry, row)
        if value_mismatch:
            mismatch.append(f"{key[1]}:values:{value_mismatch}")
            continue
        want_diags = sorted(
            entry.get("diagnostics")
            or ([entry["diagnostic"]] if entry.get("diagnostic") else [])
        )
        got_diags = sorted(
            {diagnostic.reason_code for diagnostic in row.diagnostics}
        )
        if want_diags != got_diags:
            mismatch.append(f"{key[1]}:diags:{got_diags}!={want_diags}")
            continue
        match += 1
    if mismatch:
        raise AssessmentError("oracle_mismatch:" + ";".join(mismatch))
    extra = sorted(
        key[1]
        for key in rows
        if key not in expected and key not in extra_allowed
    )
    if extra:
        raise AssessmentError("unknown_extra_carrier:" + ";".join(extra))
    return match, 0


def assess_evidence_strategy(
    resolutions: Mapping[tuple[str, str], EvidenceResolution],
    oracle: Mapping[str, object],
    *,
    dataset_fingerprint: str,
    resolver_contract: str = RESOLVER_CONTRACT,
    extra_allowed: frozenset[tuple[str, str]] = frozenset(),
) -> EvidenceStrategyReport:
    """Pure assessment of carrier resolutions against the independent oracle."""
    if not resolutions:
        raise AssessmentError("empty_carrier_set")
    rows: dict[tuple[str, str], CarrierRow] = {}
    classifications = {
        "validated_fact": 0,
        "intentional_conservative": 0,
        "model_eligible_unresolved": 0,
        "blocking_unbounded_debit": 0,
        "incorrect_optimistic": 0,
    }
    for key, resolution in resolutions.items():
        carrier_type, carrier_id = key
        if key in rows:
            raise AssessmentError(f"duplicate_carrier:{carrier_id}")
        classification = _classify_carrier(resolution)
        rows[key] = CarrierRow(
            carrier_type=carrier_type,
            carrier_id=carrier_id,
            facts=resolution.facts,
            diagnostics=resolution.diagnostics,
            classification=classification,
        )
        classifications[classification] += 1
    _check_optimistic_facts(rows)
    match, mismatch = _oracle_matches(rows, oracle, extra_allowed)
    counts = {
        "total": len(rows),
        "message": sum(1 for key in rows if key[0] == "message"),
        "image": sum(1 for key in rows if key[0] == "image"),
    }
    eligible = sorted(
        (
            {
                "source_id": row.carrier_id,
                "reason_code": sorted(
                    {
                        diagnostic.reason_code
                        for diagnostic in row.diagnostics
                        if diagnostic.reason_code in MODEL_ELIGIBLE_CODES
                    }
                )[0],
            }
            for row in rows.values()
            if row.classification == "model_eligible_unresolved"
        ),
        key=lambda item: item["source_id"],
    )
    if mismatch or classifications["incorrect_optimistic"]:
        raise AssessmentError("invalid_gate")
    if eligible:
        strategy = "provider_trial_required"
        reason = (
            f"{len(eligible)} carrier(s) contain grounded, policy-permitted "
            "facts the deterministic resolver cannot extract or validate; a "
            "bounded provider trial is the only path to recover them."
        )
    else:
        strategy = "offline"
        reason = (
            "Every carrier has an explicit accepted disposition and the "
            "independent oracle matches exactly with zero incorrect "
            "optimistic facts and zero model-eligible unresolved carriers; "
            "a provider trial has no measured validated coverage to add."
        )
    rejected = (
        "offline (already selected; a provider trial would add cost and "
        "risk with no measured coverage gain)"
        if strategy == "offline"
        else "offline (it would silently drop grounded extractable facts)"
    )
    return EvidenceStrategyReport(
        selected_strategy=strategy,
        decision_reason=reason,
        rejected_alternative=rejected,
        carrier_counts=counts,
        classifications=classifications,
        oracle={"match": match, "mismatch": mismatch},
        model_eligible=tuple(eligible),
        model_usage={
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
        },
        dataset_fingerprint=dataset_fingerprint,
        resolver_contract=resolver_contract,
    )


def write_strategy_report(report: EvidenceStrategyReport, output_path: Path) -> None:
    """Write UTF-8 JSON atomically via a sibling temporary file."""
    output_path = Path(output_path)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    payload = report.to_json().encode("utf-8")
    try:
        with open(temp_path, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, output_path)
    except BaseException:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _dataset_fingerprint(dataset_root: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for name in sorted(
        path.name for path in dataset_root.iterdir() if path.is_file()
    ):
        digest.update(name.encode("utf-8"))
        with (dataset_root / name).open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _load_oracles(oracle_dir: Path) -> dict[str, object]:
    oracle: dict[str, object] = {}
    for name in ("message_oracle.json", "image_oracle.json"):
        path = oracle_dir / name
        if not path.exists():
            raise AssessmentError(f"missing_oracle_fixture:{name}")
        oracle.update(json.loads(path.read_text(encoding="utf-8")))
    return oracle


def run_assessment(
    dataset_root: Path, oracle_dir: Path
) -> EvidenceStrategyReport:
    """Resolve every evaluation and sample case through the accepted resolver."""
    repo = DatasetRepository.from_directory(Path(dataset_root))
    facts_by_carrier: dict[tuple[str, str], list[EvidenceFact]] = {}
    diags_by_carrier: dict[tuple[str, str], list[EvidenceDiagnostic]] = {}
    for scope in (RequestScope.EVALUATION, RequestScope.SAMPLE):
        for case in repo.iter_request_cases(scope):
            resolution = resolve_case_evidence(case)
            for fact in resolution.facts:
                for source in fact.sources:
                    key = (source.carrier_type, source.carrier_id)
                    facts_by_carrier.setdefault(key, []).append(fact)
            for diagnostic in resolution.diagnostics:
                key = (diagnostic.carrier_type, diagnostic.carrier_id)
                diags_by_carrier.setdefault(key, []).append(diagnostic)
    resolutions = {
        key: EvidenceResolution(
            facts=tuple(facts_by_carrier.get(key, ())),
            diagnostics=tuple(diags_by_carrier.get(key, ())),
            blocks_downstream=any(
                diagnostic.blocks_downstream
                for diagnostic in diags_by_carrier.get(key, ())
            ),
        )
        for key in set(facts_by_carrier) | set(diags_by_carrier)
    }
    index = repo._index
    supplied: set[tuple[str, str]] = {
        ("message", record.message_id)
        for records in index.messages_by_user.values()
        for record in records
    } | {
        ("image", record.image_id)
        for records in index.images_by_user.values()
        for record in records
    }
    missing = sorted(key[1] for key in supplied - set(resolutions))
    if missing:
        raise AssessmentError("missing_carrier:" + ";".join(missing))
    oracle = _load_oracles(Path(oracle_dir))
    return assess_evidence_strategy(
        resolutions,
        oracle,
        dataset_fingerprint=_dataset_fingerprint(Path(dataset_root)),
        extra_allowed=frozenset(supplied),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess the offline evidence strategy (WP-03 gate)."
    )
    parser.add_argument("--dataset", default="dataset", type=Path)
    parser.add_argument(
        "--oracles",
        default=Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "evidence",
        type=Path,
    )
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parent / "evidence_strategy.json",
        type=Path,
    )
    args = parser.parse_args(argv)
    try:
        report = run_assessment(args.dataset, args.oracles)
        write_strategy_report(report, args.output)
    except AssessmentError as error:
        print(f"assessment gate failed: {error}", file=sys.stderr)
        return 1
    print(
        f"strategy={report.selected_strategy} "
        f"carriers={report.carrier_counts['total']} "
        f"oracle_match={report.oracle['match']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
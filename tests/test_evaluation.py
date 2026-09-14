"""WP-09B focused contracts for the isolated public-sample evaluator."""

from __future__ import annotations

import csv
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

import main as evaluation  # noqa: E402


def _raw_row(request_id: str = "request_01", amount: str = "10") -> dict[str, str]:
    return {
        "request_id": request_id,
        "amount_safe_to_pay": amount,
        "affordability_status": "affordable_now",
        "recommended_payment_method": "full_payment",
        "payment_plan": "2026-01-01:10",
        "earliest_date_for_full_payment": "2026-01-01",
        "spending_changes_needed": "none",
        "decision_explanation": "Grounded explanation.",
    }


def _comparison(**changes: object) -> evaluation.SampleComparison:
    base = evaluation.SampleComparison(
        request_id="request_01",
        policy_id="baseline",
        predicted={column: value for column, value in _raw_row().items() if column != "request_id"},
        expected={column: value for column, value in _raw_row().items() if column != "request_id"},
        mismatched=False,
        status_exact=True,
        method_exact=True,
        money_exact=True,
        signed_error=Decimal("0"),
        absolute_error=Decimal("0"),
        normalized_error=Decimal("0"),
        requested_amount=Decimal("10"),
        home_currency=evaluation.CurrencyCode.USD,
        date_exact=True,
        date_empty_state="both_present",
        signed_day_error=0,
        absolute_day_error=0,
        plan_raw_exact=True,
        plan_semantic_exact=True,
        plan_reason="none",
        changes_raw_exact=True,
        changes_semantic_exact=True,
        changes_reason="none",
        explanation_consistent=True,
        explanation_raw_equal=True,
        contract_valid=True,
        contract_failures=(),
        formatting_issue=False,
        arithmetic_divergence=False,
        blocking_evidence=False,
        mismatch_reasons=(),
        scenarios=frozenset({"pending_debit"}),
        optimism=(),
    )
    return replace(base, **changes)


class SampleOracleIsolationTests(unittest.TestCase):
    def _write_sample(self, root: Path, rows: list[dict[str, str]]) -> None:
        with (root / "sample_requests.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=evaluation.SAMPLE_HEADER)
            writer.writeheader()
            for row in rows:
                writer.writerow({**{column: "input" for column in evaluation.SAMPLE_INPUT_COLUMNS}, **row})

    def test_oracle_reads_only_solved_columns_and_label_changes_remain_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_sample(root, [_raw_row()])
            original = evaluation.load_sample_oracle(root)[0]
            self._write_sample(root, [_raw_row(amount="9")])
            poisoned = evaluation.load_sample_oracle(root)[0]
        self.assertEqual(original.request_id, poisoned.request_id)
        self.assertEqual(original.row.amount_safe_to_pay, Decimal("10"))
        self.assertEqual(poisoned.row.amount_safe_to_pay, Decimal("9"))

    def test_oracle_rejects_duplicate_ids_and_wrong_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write_sample(root, [_raw_row(), _raw_row()])
            with self.assertRaisesRegex(evaluation.EvaluationError, "duplicate_sample_request_id"):
                evaluation.load_sample_oracle(root)
            (root / "sample_requests.csv").write_text("request_id\nrequest_01\n", encoding="utf-8")
            with self.assertRaisesRegex(evaluation.EvaluationError, "unexpected_sample_header"):
                evaluation.load_sample_oracle(root)

    def test_poisoned_solved_columns_do_not_change_predictions_but_change_comparisons(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            dataset_root = Path(temporary) / "dataset"
            shutil.copytree(ROOT / "dataset", dataset_root)
            baseline = evaluation.run_samples(dataset_root)
            sample_path = dataset_root / "sample_requests.csv"
            with sample_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = tuple(rows[0])
            for row in rows:
                row.update({
                    "amount_safe_to_pay": "1",
                    "affordability_status": "not_affordable",
                    "recommended_payment_method": "not_recommended",
                    "payment_plan": "none",
                    "earliest_date_for_full_payment": "",
                    "spending_changes_needed": "none",
                    "decision_explanation": "Poisoned public label.",
                })
            with sample_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            poisoned = evaluation.run_samples(dataset_root)
        self.assertEqual(
            [comparison.predicted for comparison in baseline.comparisons],
            [comparison.predicted for comparison in poisoned.comparisons],
        )
        self.assertNotEqual(
            [comparison.expected for comparison in baseline.comparisons],
            [comparison.expected for comparison in poisoned.comparisons],
        )

    def test_reordered_oracle_rejects_join(self) -> None:
        source_repository = evaluation.DatasetRepository.from_directory(ROOT / "dataset")
        cases = tuple(source_repository.iter_request_cases(evaluation.RequestScope.SAMPLE))

        class FixedRepository:
            def iter_request_cases(self, scope: evaluation.RequestScope):
                self_scope = scope
                if self_scope is not evaluation.RequestScope.SAMPLE:
                    raise AssertionError("unexpected scope")
                return iter(cases)

        with tempfile.TemporaryDirectory() as temporary:
            dataset_root = Path(temporary) / "dataset"
            shutil.copytree(ROOT / "dataset", dataset_root)
            sample_path = dataset_root / "sample_requests.csv"
            with sample_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                fieldnames = tuple(rows[0])
            rows[0], rows[1] = rows[1], rows[0]
            with sample_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            with patch.object(
                evaluation.DatasetRepository,
                "from_directory",
                return_value=FixedRepository(),
            ):
                with self.assertRaisesRegex(
                    evaluation.EvaluationError, "sample_oracle_join_order_mismatch"
                ):
                    evaluation.run_samples(dataset_root)


class SampleMetricTests(unittest.TestCase):
    def test_metrics_use_raw_status_and_method_values_and_never_average_currencies(self) -> None:
        altered = _comparison(
            request_id="request_02",
            predicted={
                **_comparison().predicted,
                "affordability_status": "affordable_later",
                "recommended_payment_method": "wait",
            },
            expected=_comparison().expected,
            mismatched=True,
            status_exact=False,
            method_exact=False,
            money_exact=False,
            signed_error=Decimal("2"),
            absolute_error=Decimal("2"),
            normalized_error=Decimal("0.2"),
            requested_amount=Decimal("10"),
            home_currency=evaluation.CurrencyCode.EUR,
            mismatch_reasons=(("policy", "amount_or_date_forecast"),),
        )
        metrics = evaluation.summarize((_comparison(), altered))
        self.assertEqual(metrics["categorical"]["status_exact"], 1)
        self.assertEqual(metrics["categorical"]["status_confusion"]["affordable_later"]["affordable_now"], 1)
        self.assertEqual(metrics["money"]["by_currency"]["USD"]["count"], 1)
        self.assertEqual(metrics["money"]["by_currency"]["EUR"]["mean_absolute_error"], "2")
        self.assertEqual(metrics["money"]["aggregate_normalized"], {"count": 2, "mean": "0.1", "sum": "0.2"})


class MismatchReasonTests(unittest.TestCase):
    def test_reason_priority_and_optimism_are_one_category_and_separate(self) -> None:
        formatting = _comparison(mismatched=True, formatting_issue=True, blocking_evidence=True)
        self.assertEqual(evaluation.classify_mismatch(formatting), (("formatting", "expected_canonical_divergence"),))
        evidence = _comparison(mismatched=True, blocking_evidence=True)
        self.assertEqual(evaluation.classify_mismatch(evidence), (("evidence", "blocking_unresolved_evidence"),))
        arithmetic = _comparison(mismatched=True, arithmetic_divergence=True)
        self.assertEqual(evaluation.classify_mismatch(arithmetic), (("arithmetic", "cent_rounding_divergence"),))
        eligibility = _comparison(mismatched=True, status_exact=False)
        self.assertEqual(evaluation.classify_mismatch(eligibility), (("eligibility", "decision_eligibility"),))
        policy = _comparison(mismatched=True, money_exact=False, signed_error=Decimal("1"))
        self.assertEqual(evaluation.classify_mismatch(policy), (("policy", "amount_or_date_forecast"),))
        self.assertEqual(evaluation._optimism(policy), ("optimistic_safe_amount",))

"""Focused tests for the offline evidence-strategy assessment (WP-03)."""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

import evidence_strategy as strategy_module  # noqa: E402
from buy_or_wait.evidence import (  # noqa: E402
    EvidenceDiagnostic,
    EvidenceResolution,
)

ORACLE_DIR = ROOT / "tests" / "fixtures" / "evidence"


def _fact(
    carrier_id: str,
    fact_type: str,
    amount: str | None = None,
    currency: str | None = None,
    effective_date: str | None = None,
    target_event_id: str | None = None,
):
    from datetime import date

    from buy_or_wait.domain import CurrencyCode, EvidenceFact, EvidenceFactType, SourceReference

    return EvidenceFact(
        fact_id=f"fact_{carrier_id}",
        fact_type=EvidenceFactType(fact_type),
        sources=(SourceReference("message", carrier_id),),
        amount=Decimal(amount) if amount else None,
        currency=CurrencyCode[currency] if currency else None,
        effective_date=date.fromisoformat(effective_date) if effective_date else None,
        target_event_id=target_event_id,
    )


def _diag(carrier_id: str, reason_code: str, blocks: bool = False):
    return EvidenceDiagnostic(
        carrier_type="message",
        carrier_id=carrier_id,
        reason_code=reason_code,
        source_ids=(carrier_id,),
        blocks_downstream=blocks,
    )


def _key(carrier_id: str) -> tuple[str, str]:
    return ("image" if carrier_id.startswith("image_") else "message", carrier_id)


def _resolution(
    facts=(), diagnostics=()
) -> EvidenceResolution:
    blocks = any(
        getattr(d, "blocks_downstream", False) for d in diagnostics
    )
    return EvidenceResolution(
        facts=tuple(facts), diagnostics=tuple(diagnostics), blocks_downstream=blocks
    )


def _oracle_resolutions(
    oracle: dict, overrides: dict[str, EvidenceResolution] | None = None
) -> dict[tuple[str, str], EvidenceResolution]:
    """Build a full fake carrier set whose decisions mirror the oracle data."""
    overrides = overrides or {}
    resolutions: dict[tuple[str, str], EvidenceResolution] = {}
    for carrier_id, entry in oracle["sample_messages"].items():
        if carrier_id in overrides:
            resolutions[_key(carrier_id)] = overrides[carrier_id]
            continue
        facts = tuple(
            _fact(
                carrier_id,
                fact["fact_type"],
                fact["amount"],
                fact.get("currency"),
                fact.get("effective_date"),
                fact.get("target_event_id"),
            )
            for fact in entry["facts"]
        )
        diagnostics = tuple(
            _diag(
                carrier_id,
                code,
                code == "unresolved_required_debit_blocks",
            )
            for code in entry["diagnostics"]
        )
        resolutions[_key(carrier_id)] = _resolution(facts, diagnostics)
    for carrier_id, entry in oracle["images"].items():
        if carrier_id in overrides:
            resolutions[_key(carrier_id)] = overrides[carrier_id]
            continue
        if entry["fact_type"] is None:
            resolutions[_key(carrier_id)] = _resolution(
                (), (_diag(carrier_id, entry["diagnostic"]),)
            )
        else:
            resolutions[_key(carrier_id)] = _resolution(
                (
                    _fact(
                        carrier_id,
                        entry["fact_type"],
                        entry["amount"],
                        entry.get("currency"),
                        None,
                        entry.get("target_event_id"),
                    ),
                )
            )
    return resolutions


class StrategyTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.strategy = strategy_module
        self.tmp = Path(__file__).resolve().parent / "__strategy_tmp__"
        self.tmp.mkdir(exist_ok=True)
        self.output = self.tmp / "report.json"
        if self.output.exists():
            self.output.unlink()
        self.oracle = json.loads(
            (ORACLE_DIR / "message_oracle.json").read_text(encoding="utf-8")
        )
        self.oracle["images"] = json.loads(
            (ORACLE_DIR / "image_oracle.json").read_text(encoding="utf-8")
        )["images"]

    def tearDown(self) -> None:
        if self.output.exists():
            self.output.unlink()
        if self.tmp.exists() and not any(self.tmp.iterdir()):
            self.tmp.rmdir()

    def assess(self, overrides=None, **kwargs):
        resolutions = _oracle_resolutions(self.oracle, overrides)
        return self.strategy.assess_evidence_strategy(
            resolutions,
            self.oracle,
            dataset_fingerprint="0" * 64,
            **kwargs,
        )

    def write(self, report) -> None:
        self.strategy.write_strategy_report(report, self.output)


class DecisionRuleTests(StrategyTestBase):
    """Ordered decision rules and conservative classifications."""

    def test_offline_selected_for_full_accepted_set(self) -> None:
        report = self.assess()
        self.assertEqual(report.selected_strategy, "offline")
        self.assertEqual(report.model_usage["calls"], 0)
        self.assertEqual(report.classifications["incorrect_optimistic"], 0)
        self.assertEqual(report.oracle, {"match": 33, "mismatch": 0})

    def test_pack_conservative_cases_do_not_trigger_ai(self) -> None:
        report = self.assess()
        # message_03/07/13/16 plus image_04 are intentional conservative.
        self.assertEqual(report.classifications["intentional_conservative"], 5)
        # message_10 yields a validated resume fact plus a blocking diagnostic,
        # so it classifies as validated_fact; blocking is preserved in its row.
        self.assertEqual(report.classifications["model_eligible_unresolved"], 0)

    def test_message_10_mix_fact_plus_blocking_diagnostic(self) -> None:
        report = self.assess()
        self.assertEqual(report.classifications["blocking_unbounded_debit"], 0)
        self.assertEqual(report.model_eligible, ())

    def test_corrupted_oracle_fact_value_fails_the_gate(self) -> None:
        corrupted = json.loads(json.dumps(self.oracle))
        entry = corrupted["sample_messages"]["message_04"]["facts"][0]
        self.assertEqual(entry["amount"], "1037.52")
        entry["amount"] = "999999"
        overrides = {
            "message_04": _resolution(
                (
                    _fact(
                        "message_04",
                        "next_cycle_amount_amendment",
                        "1037.52",
                        None,
                        None,
                        "event_471",
                    ),
                )
            )
        }
        resolutions = _oracle_resolutions(corrupted, overrides)
        with self.assertRaises(self.strategy.AssessmentError) as ctx:
            self.strategy.assess_evidence_strategy(
                resolutions, corrupted, dataset_fingerprint="0" * 64
            )
        self.assertIn("message_04", str(ctx.exception))

    def test_corrupted_oracle_currency_fails_the_gate(self) -> None:
        corrupted = json.loads(json.dumps(self.oracle))
        corrupted["sample_messages"]["message_01"]["facts"][0]["currency"] = "USD"
        resolutions = _oracle_resolutions(self.oracle)
        with self.assertRaises(self.strategy.AssessmentError) as ctx:
            self.strategy.assess_evidence_strategy(
                resolutions, corrupted, dataset_fingerprint="0" * 64
            )
        self.assertIn("message_01", str(ctx.exception))

    def test_corrupted_oracle_target_fails_the_gate(self) -> None:
        corrupted = json.loads(json.dumps(self.oracle))
        corrupted["images"]["image_01"]["target_event_id"] = "event_9999"
        overrides = {
            "image_01": _resolution(
                (
                    _fact(
                        "image_01",
                        "event_amount",
                        "4365000",
                        "IDR",
                        None,
                        "event_253",
                    ),
                )
            )
        }
        resolutions = _oracle_resolutions(corrupted, overrides)
        with self.assertRaises(self.strategy.AssessmentError) as ctx:
            self.strategy.assess_evidence_strategy(
                resolutions, corrupted, dataset_fingerprint="0" * 64
            )
        self.assertIn("image_01", str(ctx.exception))

    def test_corrupted_oracle_diagnostic_code_fails_the_gate(self) -> None:
        corrupted = json.loads(json.dumps(self.oracle))
        corrupted["sample_messages"]["message_13"]["diagnostics"] = [
            "unresolved_transfer_pair_typo"
        ]
        resolutions = _oracle_resolutions(corrupted)
        with self.assertRaises(self.strategy.AssessmentError):
            self.strategy.assess_evidence_strategy(
                resolutions, corrupted, dataset_fingerprint="0" * 64
            )

    def test_model_eligible_unresolved_requires_provider_trial(self) -> None:
        oracle = json.loads(json.dumps(self.oracle))
        oracle["sample_messages"]["message_03"] = {
            "facts": [],
            "diagnostics": ["unresolved_extractable_amount"],
        }
        overrides = {"message_03": _resolution((), (_diag("message_03", "unresolved_extractable_amount"),))}
        resolutions = _oracle_resolutions(oracle, overrides)
        report = self.strategy.assess_evidence_strategy(
            resolutions, oracle, dataset_fingerprint="0" * 64
        )
        self.assertEqual(report.selected_strategy, "provider_trial_required")
        self.assertEqual(
            report.model_eligible,
            ({"source_id": "message_03", "reason_code": "unresolved_extractable_amount"},),
        )
        self.assertEqual(report.model_usage["calls"], 0)

    def test_incorrect_optimistic_fact_fails_the_gate(self) -> None:
        with self.assertRaises(self.strategy.AssessmentError):
            self.assess(
                {
                    "message_03": _resolution(
                        (_fact("message_03", "pending_credit", "500"),)
                    )
                }
            )

    def test_oracle_mismatch_fails_the_gate(self) -> None:
        with self.assertRaises(self.strategy.AssessmentError):
            self.assess(
                {
                    "message_01": _resolution(
                        (_fact("message_01", "recurrence_stop"),)
                    )
                }
            )


class CarrierAccountingTests(StrategyTestBase):
    """AC-02: strict one-row-per-carrier accounting; failures never replace."""

    def test_missing_carrier_fails(self) -> None:
        resolutions = _oracle_resolutions(self.oracle)
        del resolutions[_key("message_01")]
        with self.assertRaises(self.strategy.AssessmentError):
            self.strategy.assess_evidence_strategy(
                resolutions, self.oracle, dataset_fingerprint="0" * 64
            )

    def test_duplicate_oracle_carrier_fails(self) -> None:
        duplicate = json.loads(json.dumps(self.oracle))
        duplicate["sample_messages"]["message_01b"] = (
            duplicate["sample_messages"]["message_01"]
        )
        resolutions = _oracle_resolutions(self.oracle)
        resolutions[_key("message_01b")] = _resolution()
        with self.assertRaises(self.strategy.AssessmentError):
            self.strategy.assess_evidence_strategy(
                resolutions, duplicate, dataset_fingerprint="0" * 64
            )

    def test_unknown_extra_carrier_fails(self) -> None:
        resolutions = _oracle_resolutions(self.oracle)
        resolutions[_key("message_zz")] = _resolution()
        with self.assertRaises(self.strategy.AssessmentError):
            self.strategy.assess_evidence_strategy(
                resolutions, self.oracle, dataset_fingerprint="0" * 64
            )


class WriterAndDeterminismTests(StrategyTestBase):
    """AC-06/AC-07: atomic writes, deterministic bytes, redaction."""

    def _report(self):
        return self.assess()

    def test_write_is_deterministic_and_atomic(self) -> None:
        self.write(self._report())
        first = self.output.read_bytes()
        self.write(self._report())
        self.assertEqual(first, self.output.read_bytes())
        self.assertTrue(first.endswith(b"\n"))
        self.assertEqual(
            json.loads(first.decode("utf-8"))["schema_version"], "wp-03-v1"
        )
        self.assertFalse(list(self.tmp.glob("*.tmp")))

    def test_failure_preserves_prior_report_bytes(self) -> None:
        self.write(self._report())
        good = self.output.read_bytes()
        with self.assertRaises(self.strategy.AssessmentError):
            self.write(self.assess({"message_03": _resolution()}))
        self.assertEqual(self.output.read_bytes(), good)

    def test_report_is_redacted(self) -> None:
        self.write(self._report())
        text = self.output.read_text(encoding="utf-8")
        self.assertNotIn(str(ROOT), text)
        self.assertNotIn("/Users/", text)
        for forbidden in ("message_text", "Dear", "invoice", "request_text"):
            self.assertNotIn(forbidden, text)


class OfflineBoundaryTests(StrategyTestBase):
    """AC-05: no provider dependency and zero model usage."""

    def test_module_has_no_provider_import(self) -> None:
        source = (ROOT / "code" / "evaluation" / "evidence_strategy.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import openai", source)
        self.assertNotIn("FakeModelProvider", source)
        self.assertNotIn("from buy_or_wait.ai_boundary", source)

    def test_usage_totals_are_zero(self) -> None:
        report = self.assess()
        self.assertEqual(
            report.model_usage,
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0},
        )


class CurrentDatasetSmokeTests(unittest.TestCase):
    """End-to-end over the real dataset with the real resolver and oracles."""

    @classmethod
    def setUpClass(cls) -> None:
        if not (ROOT / "dataset" / "messages.csv").exists():
            raise unittest.SkipTest("dataset not available")
        cls.strategy = strategy_module
        cls.report = strategy_module.run_assessment(ROOT / "dataset", ORACLE_DIR)

    def test_full_carrier_set_offline(self) -> None:
        self.assertEqual(
            self.report.carrier_counts, {"total": 231, "message": 215, "image": 16}
        )
        self.assertEqual(self.report.selected_strategy, "offline")

    def test_oracle_matches_exactly(self) -> None:
        self.assertEqual(self.report.oracle, {"match": 33, "mismatch": 0})

    def test_no_model_usage(self) -> None:
        self.assertEqual(self.report.model_usage["calls"], 0)


if __name__ == "__main__":
    unittest.main()
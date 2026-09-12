"""Focused tests for the deterministic typed-evidence boundary."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from buy_or_wait.domain import (  # noqa: E402
    CurrencyCode,
    Direction,
    EventRecord,
    EventStatus,
    EventType,
    EvidenceFactType,
    Flexibility,
    ImageRecord,
    MessageRecord,
    PaymentMethod,
    RequestRecord,
    RequestScope,
    RequestType,
    RequestCase,
    ProfileRecord,
    CarrierSourceType,
)
from buy_or_wait.evidence import (  # noqa: E402
    EvidenceDiagnostic,
    EvidenceFactCandidate,
    EvidenceResolution,
    resolve_case_evidence,
)


def _date(value: str):
    from datetime import date

    return date.fromisoformat(value)


def _request(
    request_id: str = "request_01",
    user_id: str = "user_01",
    request_date: str = "2026-01-10",
) -> RequestRecord:
    return RequestRecord(
        request_id=request_id,
        user_id=user_id,
        request_date=_date(request_date),
        request_type=RequestType.PURCHASE,
        requested_amount=Decimal("100"),
        desired_completion_date=_date("2026-03-01"),
        allows_partial_payment=True,
        scope=RequestScope.SAMPLE,
    )


def _profile(user_id: str = "user_01") -> ProfileRecord:
    return ProfileRecord(
        user_id=user_id,
        home_currency=CurrencyCode.ZAR,
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
    user_id: str = "user_01",
    event_type: EventType = EventType.INCOME,
    category: str = "salary",
    direction: Direction = Direction.CREDIT,
    amount: Decimal | None = Decimal("100"),
    currency: CurrencyCode = CurrencyCode.ZAR,
    event_date: str = "2025-12-15",
    status: EventStatus = EventStatus.SETTLED,
) -> EventRecord:
    return EventRecord(
        event_id=event_id,
        user_id=user_id,
        event_type=event_type,
        description="Payroll credit",
        category=category,
        direction=direction,
        amount=amount,
        currency=currency,
        event_date=_date(event_date),
        settlement_date=None,
        status=status,
        linked_event_id=None,
        flexibility=Flexibility.FIXED,
        minimum_allowed_amount=None,
    )


def _message(
    message_id: str,
    user_id: str = "user_01",
    request_id: str | None = None,
    related_event_id: str | None = None,
) -> MessageRecord:
    return MessageRecord(
        message_id=message_id,
        user_id=user_id,
        request_id=request_id,
        related_event_id=related_event_id,
        sent_at="2025-12-20T09:00:00Z",
        source_type=CarrierSourceType.EMPLOYER,
    )


def _image(
    image_id: str,
    user_id: str = "user_01",
    request_id: str = "request_01",
    related_event_id: str = "event_900",
) -> ImageRecord:
    return ImageRecord(
        image_id=image_id,
        user_id=user_id,
        request_id=request_id,
        related_event_id=related_event_id,
    )


def _case(
    *,
    messages: tuple[MessageRecord, ...] = (),
    images: tuple[ImageRecord, ...] = (),
    events: tuple[EventRecord, ...] = (),
    request: RequestRecord | None = None,
) -> RequestCase:
    return RequestCase(
        request=request or _request(),
        profile=_profile(),
        events=events,
        payment_options=(),
        messages=messages,
        images=images,
        relevant_rates=(),
    )


class CarrierCoverageTests(unittest.TestCase):
    """AC-01: every supplied carrier resolves with an explicit disposition."""

    @classmethod
    def setUpClass(cls) -> None:
        from buy_or_wait.repository import DatasetRepository

        dataset = Path(__file__).resolve().parent.parent / "dataset"
        if not (dataset / "messages.csv").exists():
            raise unittest.SkipTest("dataset not available")
        cls.repo = DatasetRepository.from_directory(dataset)
        cls.dispositions: dict[str, tuple[str, str]] = {}
        cls.carrier_ids: set[str] = set()
        cls.blocks: set[str] = set()
        for scope in (RequestScope.EVALUATION, RequestScope.SAMPLE):
            for case in cls.repo.iter_request_cases(scope):
                resolution = resolve_case_evidence(case)
                for fact in resolution.facts:
                    for source in fact.sources:
                        cls.dispositions[source.carrier_id] = (
                            source.carrier_type,
                            "fact",
                        )
                        cls.carrier_ids.add(source.carrier_id)
                for diagnostic in resolution.diagnostics:
                    cls.dispositions[diagnostic.carrier_id] = (
                        diagnostic.carrier_type,
                        diagnostic.reason_code,
                    )
                    cls.carrier_ids.add(diagnostic.carrier_id)
                    if diagnostic.blocks_downstream:
                        cls.blocks.add(diagnostic.carrier_id)

    def test_all_messages_have_one_explicit_disposition(self) -> None:
        import csv

        dataset = Path(__file__).resolve().parent.parent / "dataset"
        with (dataset / "messages.csv").open(newline="", encoding="utf-8") as handle:
            supplied = {row["message_id"] for row in csv.DictReader(handle)}
        message_ids = {
            carrier_id
            for carrier_id in self.carrier_ids
            if carrier_id.startswith("message_")
        }
        self.assertEqual(supplied, message_ids)

    def test_all_images_have_one_explicit_disposition(self) -> None:
        import csv

        dataset = Path(__file__).resolve().parent.parent / "dataset"
        with (dataset / "images.csv").open(newline="", encoding="utf-8") as handle:
            supplied = {row["image_id"] for row in csv.DictReader(handle)}
        image_ids = {
            carrier_id
            for carrier_id in self.carrier_ids
            if carrier_id.startswith("image_")
        }
        self.assertEqual(supplied, image_ids)
        self.assertIn("image_04", image_ids)

    def test_image_04_remains_unresolved(self) -> None:
        self.assertEqual(
            self.dispositions.get("image_04", ("", ""))[1],
            "unavailable_image_review",
        )

    def test_blocking_debits_are_first_class_diagnostics(self) -> None:
        # message_10's childcare notice is the pack's unresolved required debit.
        self.assertIn("message_10", self.blocks)
        for carrier_id in self.blocks:
            self.assertEqual(
                self.dispositions[carrier_id][1],
                "unresolved_required_debit_blocks",
            )

    def test_resolution_flag_matches_diagnostics(self) -> None:
        case = self.repo.load_request_case("request_14")
        resolution = resolve_case_evidence(case)
        self.assertTrue(resolution.blocks_downstream)
        clean = resolve_case_evidence(self.repo.load_request_case("request_01"))
        self.assertFalse(clean.blocks_downstream)


class SampleMessageOracleTests(unittest.TestCase):
    """AC-02: the 17 sample messages match the evidence decision pack."""

    @classmethod
    def setUpClass(cls) -> None:
        from buy_or_wait.repository import DatasetRepository

        dataset = Path(__file__).resolve().parent.parent / "dataset"
        if not (dataset / "messages.csv").exists():
            raise unittest.SkipTest("dataset not available")
        cls.repo = DatasetRepository.from_directory(dataset)
        cls.facts: dict[str, list] = {}
        cls.diagnostics: dict[str, list[str]] = {}
        for scope in (RequestScope.EVALUATION, RequestScope.SAMPLE):
            for case in cls.repo.iter_request_cases(scope):
                resolution = resolve_case_evidence(case)
                for fact in resolution.facts:
                    for source in fact.sources:
                        cls.facts.setdefault(source.carrier_id, []).append(fact)
                for diagnostic in resolution.diagnostics:
                    cls.diagnostics.setdefault(diagnostic.carrier_id, []).append(
                        diagnostic.reason_code
                    )

    def _fact_ids(self, message_id: str) -> set[str]:
        return {fact.fact_type.value for fact in self.facts.get(message_id, [])}

    def test_message_01_salary_increase_amendment(self) -> None:
        facts = self.facts["message_01"]
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual(fact.fact_type, EvidenceFactType.RECURRING_AMOUNT_AMENDMENT)
        self.assertEqual(fact.amount, Decimal("42750000"))
        self.assertEqual(fact.currency, CurrencyCode.IDR)
        self.assertEqual(str(fact.effective_date), "2025-08-15")
        self.assertEqual(fact.target_event_id, "event_136")

    def test_message_02_recurrence_confirmation_no_amount(self) -> None:
        facts = self.facts["message_02"]
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual(fact.fact_type, EvidenceFactType.RECURRENCE_CONFIRMATION)
        self.assertIsNone(fact.amount)
        self.assertEqual(fact.target_event_id, "event_253")

    def test_message_03_bonus_unavailable(self) -> None:
        self.assertIn("unavailable_credit_no_cash", self.diagnostics["message_03"])
        self.assertNotIn("message_03", self.facts)

    def test_message_04_next_cycle_reduction(self) -> None:
        fact = self.facts["message_04"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT)
        self.assertEqual(fact.amount, Decimal("1037.52"))
        self.assertEqual(fact.target_event_id, "event_471")

    def test_message_05_date_replacement_only(self) -> None:
        fact = self.facts["message_05"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT)
        self.assertEqual(str(fact.effective_date), "2024-09-23")
        self.assertIsNone(fact.amount)
        self.assertEqual(fact.target_event_id, "event_578")

    def test_message_06_next_cycle_reduction(self) -> None:
        fact = self.facts["message_06"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT)
        self.assertEqual(fact.amount, Decimal("1422.85"))
        self.assertEqual(fact.target_event_id, "event_643")

    def test_message_07_gig_payout_pending(self) -> None:
        self.assertIn("unavailable_credit_no_cash", self.diagnostics["message_07"])
        self.assertNotIn("message_07", self.facts)

    def test_message_08_base_salary_amendment(self) -> None:
        fact = self.facts["message_08"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.RECURRING_AMOUNT_AMENDMENT)
        self.assertEqual(fact.amount, Decimal("38760000"))
        self.assertEqual(fact.target_event_id, "event_941")

    def test_message_09_seasonal_stop(self) -> None:
        fact = self.facts["message_09"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.RECURRENCE_STOP)
        self.assertEqual(fact.target_event_id, "event_1002")

    def test_message_10_resume_plus_unbounded_childcare(self) -> None:
        types = self._fact_ids("message_10")
        self.assertEqual(types, {"recurrence_resume"})
        resume = self.facts["message_10"][0]
        self.assertEqual(resume.amount, Decimal("2717"))
        self.assertEqual(str(resume.effective_date), "2025-08-15")
        self.assertEqual(resume.target_event_id, "event_1192")
        self.assertIn(
            "unresolved_required_debit_blocks", self.diagnostics["message_10"]
        )

    def test_message_11_confirmed_future_credit(self) -> None:
        fact = self.facts["message_11"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.CONFIRMED_FUTURE_CREDIT)
        self.assertEqual(fact.amount, Decimal("1661"))
        self.assertEqual(str(fact.effective_date if fact.effective_date else ""), "")
        self.assertIsNone(fact.target_event_id)

    def test_message_12_rent_amendment(self) -> None:
        fact = self.facts["message_12"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.RECURRING_EXPENSE_AMENDMENT)
        self.assertEqual(fact.amount, Decimal("63952"))
        self.assertEqual(fact.target_event_id, "event_1371")

    def test_message_13_transfer_pair_unresolved(self) -> None:
        self.assertIn("unresolved_transfer_pair", self.diagnostics["message_13"])
        self.assertNotIn("message_13", self.facts)

    def test_message_14_refund_pending(self) -> None:
        fact = self.facts["message_14"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.PENDING_CREDIT)
        self.assertEqual(fact.amount, Decimal("8640"))
        self.assertEqual(fact.target_event_id, "event_1785")

    def test_message_15_valuation_non_cash(self) -> None:
        fact = self.facts["message_15"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.UNREALIZED_VALUE)
        self.assertEqual(fact.amount, Decimal("369.6"))
        self.assertEqual(fact.target_event_id, "event_1960")

    def test_message_16_prize_processing(self) -> None:
        self.assertIn("unavailable_credit_no_cash", self.diagnostics["message_16"])
        self.assertNotIn("message_16", self.facts)

    def test_message_17_prize_settled_one_time(self) -> None:
        fact = self.facts["message_17"][0]
        self.assertEqual(fact.fact_type, EvidenceFactType.SETTLED_ONE_TIME_CREDIT)
        self.assertEqual(fact.amount, Decimal("33550"))
        self.assertEqual(fact.target_event_id, "event_2165")


class ImageOracleTests(unittest.TestCase):
    """AC-03: 15 accepted image amounts plus the image_04 failure."""

    EXPECTED: dict[str, tuple[str, str, str]] = {
        "image_01": ("event_253", "4365000", "IDR"),
        "image_02": ("event_1442", "100000", "INR"),
        "image_03": ("event_1545", "41272", "INR"),
        "image_05": ("event_1786", "822.05", "INR"),
        "image_06": ("event_3051", "1995", "INR"),
        "image_07": ("event_3231", "8528.10", "INR"),
        "image_08": ("event_4535", "15339", "INR"),
        "image_09": ("event_5170", "723", "INR"),
        "image_10": ("event_6033", "79679.26", "INR"),
        "image_11": ("event_6859", "3650", "INR"),
        "image_12": ("event_7307", "33.50", "USD"),
        "image_13": ("event_7941", "2298", "INR"),
        "image_14": ("event_9421", "4543", "INR"),
        "image_15": ("event_9806", "9968", "INR"),
        "image_16": ("event_10521", "393.22", "INR"),
    }

    @classmethod
    def setUpClass(cls) -> None:
        from buy_or_wait.repository import DatasetRepository

        dataset = Path(__file__).resolve().parent.parent / "dataset"
        if not (dataset / "images.csv").exists():
            raise unittest.SkipTest("dataset not available")
        cls.repo = DatasetRepository.from_directory(dataset)
        cls.image_facts: dict[str, object] = {}
        for scope in (RequestScope.EVALUATION, RequestScope.SAMPLE):
            for case in cls.repo.iter_request_cases(scope):
                resolution = resolve_case_evidence(case)
                for fact in resolution.facts:
                    for source in fact.sources:
                        if source.carrier_type == "image":
                            cls.image_facts[source.carrier_id] = fact

    def test_fifteen_accepted_amounts(self) -> None:
        for image_id, (event_id, amount, currency) in self.EXPECTED.items():
            self.assertIn(image_id, self.image_facts, image_id)
            fact = self.image_facts[image_id]
            self.assertEqual(fact.fact_type, EvidenceFactType.EVENT_AMOUNT, image_id)
            self.assertEqual(fact.target_event_id, event_id, image_id)
            self.assertEqual(fact.amount, Decimal(amount), image_id)
            self.assertEqual(fact.currency, CurrencyCode[currency], image_id)


class TargetingAndDurationTests(unittest.TestCase):
    """AC-04: exact links win; ambiguity fails closed."""

    def _resolve_amendment(
        self, events: tuple[EventRecord, ...], related_event_id: str | None = None
    ):
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._MESSAGE_FACTS
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            amount="150",
            currency="ZAR",
        )
        evidence_module._MESSAGE_FACTS = {
            "test_msg": (candidate,),
        }
        try:
            case = _case(
                messages=(_message("test_msg", related_event_id=related_event_id),),
                events=events,
            )
            return resolve_case_evidence(case)
        finally:
            evidence_module._MESSAGE_FACTS = original

    def test_exact_event_link_wins(self) -> None:
        import buy_or_wait.evidence as evidence_module

        resolution = self._resolve_amendment(
            (
                _event("event_1", event_type=EventType.EXPENSE, category="rent", direction=Direction.DEBIT),
                _event("event_2", event_type=EventType.EXPENSE, category="rent", direction=Direction.DEBIT),
            ),
            related_event_id="event_2",
        )
        self.assertEqual(len(resolution.facts), 1)
        self.assertEqual(resolution.facts[0].target_event_id, "event_2")

    def test_unique_series_target(self) -> None:
        resolution = self._resolve_amendment(
            (
                _event("event_1", event_type=EventType.EXPENSE, category="rent", direction=Direction.DEBIT, event_date="2025-10-01"),
                _event("event_2", event_type=EventType.EXPENSE, category="rent", direction=Direction.DEBIT, event_date="2025-11-01"),
            )
        )
        self.assertEqual(len(resolution.facts), 1)
        self.assertEqual(resolution.facts[0].target_event_id, "event_2")

    def test_foreign_user_target_is_rejected(self) -> None:
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._MESSAGE_FACTS
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            amount="150",
            currency="ZAR",
            target_event_id="event_far",
        )
        evidence_module._MESSAGE_FACTS = {"test_msg": (candidate,)}
        try:
            case = _case(
                messages=(_message("test_msg", related_event_id="event_far"),),
                events=(
                    _event(
                        "event_far",
                        user_id="user_02",
                        event_type=EventType.EXPENSE,
                        category="rent",
                        direction=Direction.DEBIT,
                    ),
                ),
            )
            resolution = resolve_case_evidence(case)
        finally:
            evidence_module._MESSAGE_FACTS = original
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unknown_or_foreign_target"],
        )

    def test_unknown_target_id_fails_closed(self) -> None:
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._MESSAGE_FACTS
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            amount="150",
            currency="ZAR",
            target_event_id="event_ghost",
        )
        evidence_module._MESSAGE_FACTS = {"test_msg": (candidate,)}
        try:
            case = _case(messages=(_message("test_msg"),))
            resolution = resolve_case_evidence(case)
        finally:
            evidence_module._MESSAGE_FACTS = original
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unknown_or_foreign_target"],
        )

    def test_series_resolver_requires_history(self) -> None:
        # A single observed row cannot establish a unique cadence series.
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._MESSAGE_FACTS
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            amount="150",
            currency="ZAR",
        )
        evidence_module._MESSAGE_FACTS = {"test_msg": (candidate,)}
        try:
            case = _case(
                messages=(_message("test_msg"),),
                events=(
                    _event(
                        "event_1",
                        event_type=EventType.EXPENSE,
                        category="rent",
                        direction=Direction.DEBIT,
                    ),
                ),
            )
            resolution = resolve_case_evidence(case)
        finally:
            evidence_module._MESSAGE_FACTS = original
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unresolved_series_target"],
        )


class FailClosedValidationTests(unittest.TestCase):
    """AC-05: malformed candidates and wrong context never become facts."""

    def _resolve_candidate(self, candidate: EvidenceFactCandidate, **case_kwargs):
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._MESSAGE_FACTS
        evidence_module._MESSAGE_FACTS = {"test_msg": (candidate,)}
        try:
            case = _case(messages=(_message("test_msg"),), **case_kwargs)
            return resolve_case_evidence(case)
        finally:
            evidence_module._MESSAGE_FACTS = original

    def test_unknown_fact_type_carrier_rejected(self) -> None:
        candidate = EvidenceFactCandidate(
            "carrier", "test_msg", "user_01", EvidenceFactType.EVENT_AMOUNT
        )
        resolution = self._resolve_candidate(candidate)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unknown_carrier_type"],
        )

    def test_wrong_currency_fails_closed(self) -> None:
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="100",
            currency="JPY",
            settlement_date="2026-02-15",
        )
        resolution = self._resolve_candidate(candidate)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unsupported_currency"],
        )

    def test_negative_amount_fails_closed(self) -> None:
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="-5",
            currency="ZAR",
            settlement_date="2026-02-15",
        )
        resolution = self._resolve_candidate(candidate)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["invalid_amount"],
        )

    def test_malformed_date_fails_closed(self) -> None:
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="100",
            currency="ZAR",
            effective_date="15/01/2026",
        )
        resolution = self._resolve_candidate(candidate)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["invalid_date"],
        )

    def test_missing_required_amount_fails_closed(self) -> None:
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            settlement_date="2026-02-15",
        )
        resolution = self._resolve_candidate(candidate)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["missing_required_field"],
        )

    def test_unsupported_extra_field_fails_closed(self) -> None:
        candidate = EvidenceFactCandidate(
            "message",
            "test_msg",
            "user_01",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="100",
            currency="ZAR",
            settlement_date="2026-02-15",
            effective_date="2026-01-15",
        )
        resolution = self._resolve_candidate(candidate)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unsupported_extra_field"],
        )

    def test_wrong_image_currency_fails_closed(self) -> None:
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._IMAGE_FACTS
        candidate = EvidenceFactCandidate(
            "image",
            "test_img",
            "user_01",
            EvidenceFactType.EVENT_AMOUNT,
            amount="500",
            currency="USD",
            target_event_id="event_900",
            target_request_id="request_01",
        )
        evidence_module._IMAGE_FACTS = {"test_img": (candidate,)}
        try:
            case = _case(
                images=(_image("test_img", related_event_id="event_900"),),
                events=(
                    _event(
                        "event_900",
                        event_type=EventType.EXPENSE,
                        category="groceries",
                        direction=Direction.DEBIT,
                        amount=None,
                        currency=CurrencyCode.INR,
                    ),
                ),
            )
            resolution = resolve_case_evidence(case)
        finally:
            evidence_module._IMAGE_FACTS = original
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["event_currency_mismatch"],
        )

    def test_image_with_non_blank_event_fails_closed(self) -> None:
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._IMAGE_FACTS
        candidate = EvidenceFactCandidate(
            "image",
            "test_img",
            "user_01",
            EvidenceFactType.EVENT_AMOUNT,
            amount="500",
            currency="ZAR",
            target_event_id="event_900",
            target_request_id="request_01",
        )
        evidence_module._IMAGE_FACTS = {"test_img": (candidate,)}
        try:
            case = _case(
                images=(_image("test_img"),),
                events=(
                    _event(
                        "event_900",
                        event_type=EventType.EXPENSE,
                        category="groceries",
                        direction=Direction.DEBIT,
                        amount=Decimal("400"),
                    ),
                ),
            )
            resolution = resolve_case_evidence(case)
        finally:
            evidence_module._IMAGE_FACTS = original
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["event_amount_not_blank"],
        )

    def test_duplicate_fact_rejected(self) -> None:
        import buy_or_wait.evidence as evidence_module

        original = evidence_module._IMAGE_FACTS
        candidate = EvidenceFactCandidate(
            "image",
            "test_img",
            "user_01",
            EvidenceFactType.EVENT_AMOUNT,
            amount="500",
            currency="ZAR",
            target_event_id="event_900",
            target_request_id="request_01",
        )
        evidence_module._IMAGE_FACTS = {"test_img": (candidate, candidate)}
        try:
            case = _case(
                images=(_image("test_img"),),
                events=(
                    _event(
                        "event_900",
                        event_type=EventType.EXPENSE,
                        category="groceries",
                        direction=Direction.DEBIT,
                        amount=None,
                    ),
                ),
            )
            resolution = resolve_case_evidence(case)
        finally:
            evidence_module._IMAGE_FACTS = original
        self.assertEqual(len(resolution.facts), 1)
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["duplicate_fact"],
        )

    def test_provider_error_outcome_cannot_be_a_fact(self) -> None:
        # An empty/failed provider result maps to the explicit conservative
        # diagnostic path; nothing becomes a fact (offline boundary: the same
        # path an unclassified carrier takes).
        case = _case(messages=(_message("message_ghost"),))
        resolution = resolve_case_evidence(case)
        self.assertEqual(resolution.facts, ())
        self.assertEqual(
            [d.reason_code for d in resolution.diagnostics],
            ["unclassified_carrier"],
        )


class CarrierLocalGroundingTests(unittest.TestCase):
    """Every cached amount must be grounded in the carrier's own row context.

    Regression for F-01: template-level value reuse across users. Each cached
    amount must either appear in the carrier's own ``message_text`` or equal
    the amount of the carrier's own supplied ``related_event_id`` row. The
    single documented exception is the pack-approved 12%-lease arithmetic on
    the carrier user's own settled rent series (``message_12``).
    """

    GROUNDING_EXCEPTIONS: dict[str, str] = {
        "message_12": "pack-approved 12% lease increase on the carrier's own rent series",
    }

    @classmethod
    def setUpClass(cls) -> None:
        import csv
        import re

        cls.texts: dict[str, str] = {}
        cls.related_events: dict[str, str] = {}
        dataset = Path(__file__).resolve().parent.parent / "dataset"
        messages_path = dataset / "messages.csv"
        if not messages_path.exists():
            raise unittest.SkipTest("dataset not available")
        with messages_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                cls.texts[row["message_id"]] = row["message_text"]
                cls.related_events[row["message_id"]] = row["related_event_id"]
        cls.event_amounts: dict[str, tuple[str, str]] = {}
        with (dataset / "financial_events.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            for row in csv.DictReader(handle):
                cls.event_amounts[row["event_id"]] = (
                    row["amount"],
                    row["currency"],
                )
        cls._re = re

    def _grounded_in_own_row(self, message_id: str, amount: str, currency: str) -> bool:
        text = self.texts.get(message_id, "")
        for match in self._re.finditer(
            r"(IDR|INR|ZAR|USD|EUR)\s*([\d.,]+)", text
        ):
            raw = match.group(2).rstrip(".")
            try:
                value = Decimal(raw)
            except Exception:
                value = Decimal(raw.replace(",", ""))
            if match.group(1) == currency and value == Decimal(amount):
                return True
        return False

    def test_every_cached_amount_is_carrier_local(self) -> None:
        import buy_or_wait.evidence as evidence_module

        for message_id, candidates in evidence_module._MESSAGE_FACTS.items():
            self.assertIn(message_id, self.texts, message_id)
            for candidate in candidates:
                if candidate.amount is None:
                    continue
                if self._grounded_in_own_row(
                    message_id, candidate.amount, candidate.currency
                ):
                    continue
                event_id = self.related_events.get(message_id) or ""
                event = self.event_amounts.get(event_id)
                if event and event == (candidate.amount, candidate.currency):
                    continue
                self.assertIn(
                    message_id,
                    self.GROUNDING_EXCEPTIONS,
                    f"{message_id} amount {candidate.currency} "
                    f"{candidate.amount} is not grounded in its own row",
                )


class TrustBoundaryTests(unittest.TestCase):
    """AC-06: diagnostics are redacted and embedded instructions are inert."""

    def test_diagnostics_carry_no_raw_carrier_text(self) -> None:
        from buy_or_wait.repository import DatasetRepository

        dataset = Path(__file__).resolve().parent.parent / "dataset"
        if not (dataset / "messages.csv").exists():
            raise unittest.SkipTest("dataset not available")
        repo = DatasetRepository.from_directory(dataset)
        forbidden_tokens = ("Gaji", "salary will", "Pay the release charge")
        for scope in (RequestScope.EVALUATION, RequestScope.SAMPLE):
            for case in repo.iter_request_cases(scope):
                resolution = resolve_case_evidence(case)
                for diagnostic in resolution.diagnostics:
                    blob = repr(diagnostic)
                    for token in forbidden_tokens:
                        self.assertNotIn(token, blob)

    def test_diagnostics_are_dataclasses_with_safe_fields(self) -> None:
        diagnostic = EvidenceDiagnostic(
            "message", "message_01", "unavailable_credit_no_cash", ("message_01",)
        )
        self.assertEqual(diagnostic.carrier_type, "message")
        self.assertEqual(diagnostic.reason_code, "unavailable_credit_no_cash")
        self.assertFalse(diagnostic.blocks_downstream)


class BoundaryPreservationTests(unittest.TestCase):
    """AC-07: no FX, forecasting, affordability, plans, or provider calls."""

    def test_module_has_no_provider_or_io_surface(self) -> None:
        import buy_or_wait.evidence as evidence_module

        forbidden = ("urllib", "requests", "httpx", "socket", "open(")
        source = Path(evidence_module.__file__).read_text(encoding="utf-8")
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_resolution_is_immutable(self) -> None:
        case = _case(messages=(_message("message_ghost"),))
        resolution = resolve_case_evidence(case)
        with self.assertRaises(Exception):
            resolution.facts = ()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
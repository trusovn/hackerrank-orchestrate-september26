"""Focused WP-01 tests: positive loading, sample isolation, and fail-fast
validation of the strict dataset repository."""

import csv
import datetime
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "code"))

from buy_or_wait.domain import (  # noqa: E402
    PaymentMethod,
    RequestScope,
)
from buy_or_wait.repository import (  # noqa: E402
    DatasetRepository,
    RepositoryValidationError,
)

DATASET = REPO_ROOT / "dataset"

# Only the eight product-input columns are copied from sample rows; solved
# output columns are deliberately dropped so no answer can leak into fixtures.
SAMPLE_INPUT_COLUMNS = [
    "request_id",
    "user_id",
    "request_date",
    "request_type",
    "requested_amount",
    "desired_completion_date",
    "allows_partial_payment",
    "request_text",
]

SAMPLE_OUTPUT_COLUMNS = [
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]

FILE_COLUMNS = {
    "requests.csv": SAMPLE_INPUT_COLUMNS,
    # The physical sample file keeps its 15 solved columns, but fixtures leave
    # every solved output field empty and product code reads only the eight
    # input columns, so no solved value can reach a RequestCase.
    "sample_requests.csv": SAMPLE_INPUT_COLUMNS + SAMPLE_OUTPUT_COLUMNS,
    "financial_profiles.csv": [
        "user_id",
        "home_currency",
        "current_available_balance",
        "minimum_balance_to_keep",
        "financial_priorities",
        "expense_categories_to_protect",
        "expense_categories_user_is_willing_to_reduce",
        "expense_categories_user_is_willing_to_stop",
        "payment_methods_user_will_consider",
        "max_installment_months",
    ],
    "financial_events.csv": [
        "event_id",
        "user_id",
        "event_type",
        "description",
        "category",
        "direction",
        "amount",
        "currency",
        "event_date",
        "settlement_date",
        "status",
        "linked_event_id",
        "flexibility",
        "minimum_allowed_amount",
    ],
    "exchange_rates.csv": [
        "rate_date",
        "from_currency",
        "to_currency",
        "rate",
    ],
    "request_payment_options.csv": [
        "payment_option_id",
        "request_id",
        "payment_method",
        "payment_amount",
        "number_of_payments",
        "first_payment_date",
        "payment_frequency_days",
        "financing_fee",
        "total_payable_amount",
    ],
    "messages.csv": [
        "message_id",
        "user_id",
        "request_id",
        "related_event_id",
        "sent_at",
        "source_type",
        "message_text",
    ],
    "images.csv": ["image_id", "user_id", "request_id", "related_event_id"],
}


def _read(filename: str) -> list[dict[str, str]]:
    with (DATASET / filename).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_minimal_dataset(tmp: Path) -> dict[str, list[dict[str, str]]]:
    """Join-derived minimal fixture selected from the real dataset.

    Picks one sample request and, via source joins, exactly the rows it needs:
    its profile, its own events (including one blank-amount image-linked event),
    its options, carriers, and applicable rate rows. No solved output field is
    copied and no financial answer is hardcoded.
    """
    rows: dict[str, list[dict[str, str]]] = {}

    sample_rows = _read("sample_requests.csv")
    messages = _read("messages.csv")
    images = _read("images.csv")
    message_users = {row["user_id"] for row in messages}
    image_users = {row["user_id"] for row in images}
    target = next(
        row
        for row in sample_rows
        if row["user_id"] in message_users and row["user_id"] in image_users
    )
    user_id = target["user_id"]
    request_id = target["request_id"]

    rows["sample_requests.csv"] = [
        {column: row[column] for column in SAMPLE_INPUT_COLUMNS} for row in [target]
    ]
    rows["financial_profiles.csv"] = [
        row for row in _read("financial_profiles.csv") if row["user_id"] == user_id
    ]

    all_events = _read("financial_events.csv")
    user_events = [row for row in all_events if row["user_id"] == user_id]
    blank_ids = {row["event_id"] for row in user_events if row["amount"] == ""}
    image_rows = [
        row
        for row in images
        if row["user_id"] == user_id and row["request_id"] == request_id
    ]
    image_event_ids = {row["related_event_id"] for row in image_rows}
    message_rows = [row for row in messages if row["user_id"] == user_id]
    message_event_ids = {
        row["related_event_id"] for row in message_rows if row["related_event_id"]
    }
    keep_ids = set(blank_ids) | image_event_ids | message_event_ids
    non_blank_ids = {row["event_id"] for row in user_events if row["amount"] != ""}
    keep_ids |= non_blank_ids
    # Close lifecycle links so kept events only reference kept same-user events.
    changed = True
    while changed:
        changed = False
        for row in user_events:
            link = row["linked_event_id"]
            if link and link not in keep_ids:
                keep_ids.add(link)
                changed = True
    rows["financial_events.csv"] = [
        row for row in user_events if row["event_id"] in keep_ids
    ]
    rows["images.csv"] = image_rows

    rows["request_payment_options.csv"] = [
        row for row in _read("request_payment_options.csv") if row["request_id"] == request_id
    ]
    rows["messages.csv"] = message_rows
    rows["exchange_rates.csv"] = []
    rows["requests.csv"] = []

    # A second sample request from a different user exercises cross-user
    # link validation (wrong-user carrier links, one-request-per-user).
    other = next(
        row
        for row in sample_rows
        if row["user_id"] != user_id
    )
    rows["sample_requests.csv"] = rows["sample_requests.csv"] + [
        {column: other[column] for column in SAMPLE_INPUT_COLUMNS}
    ]
    rows["financial_profiles.csv"] = rows["financial_profiles.csv"] + [
        row
        for row in _read("financial_profiles.csv")
        if row["user_id"] == other["user_id"]
    ]
    rows["request_payment_options.csv"] = rows["request_payment_options.csv"] + [
        row
        for row in _read("request_payment_options.csv")
        if row["request_id"] == other["request_id"]
    ]

    write_dataset(tmp, rows)
    return rows


def write_dataset(tmp: Path, rows: dict[str, list[dict[str, str]]]) -> None:
    for filename in FILE_COLUMNS:
        columns = FILE_COLUMNS[filename]
        data = rows.get(filename)
        if data is None:
            data = read_tmp(tmp, filename)
        path = tmp / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in data:
                writer.writerow({column: row.get(column, "") for column in columns})


def mutate(
    tmp: Path, filename: str, row_index: int, column: str, value: str | None
) -> None:
    rows = read_tmp(tmp, filename)
    if value is None:
        rows[row_index][column] = ""
    else:
        rows[row_index][column] = value
    write_dataset(tmp, {filename: rows})


def read_tmp(tmp: Path, filename: str) -> list[dict[str, str]]:
    with (tmp / filename).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class FullDatasetLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = DatasetRepository.from_directory(DATASET)

    def test_ac01_all_275_cases_load_in_source_order(self) -> None:
        evaluation = list(self.repository.iter_request_cases(RequestScope.EVALUATION))
        samples = list(self.repository.iter_request_cases(RequestScope.SAMPLE))
        self.assertEqual(250, len(evaluation))
        self.assertEqual(25, len(samples))
        combined = list(self.repository.iter_request_cases(RequestScope.EVALUATION)) + list(
            self.repository.iter_request_cases(RequestScope.SAMPLE)
        )
        self.assertEqual(275, len(combined))
        request_ids = [case.request.request_id for case in combined]
        self.assertEqual(len(request_ids), len(set(request_ids)))
        source_order = [row["request_id"] for row in _read("requests.csv")]
        self.assertEqual(source_order, [c.request.request_id for c in evaluation])

    def test_ac01_each_case_has_one_profile_and_owned_records(self) -> None:
        for case in self.repository.iter_request_cases(RequestScope.EVALUATION):
            with self.subTest(request_id=case.request.request_id):
                self.assertEqual(case.request.user_id, case.profile.user_id)
                self.assertTrue(all(e.user_id == case.request.user_id for e in case.events))
                self.assertTrue(
                    all(o.request_id == case.request.request_id for o in case.payment_options)
                )
                self.assertTrue(
                    all(m.user_id == case.request.user_id for m in case.messages)
                )
                self.assertTrue(all(i.user_id == case.request.user_id for i in case.images))
                self.assertGreaterEqual(len(case.payment_options), 1)

    def test_ac01_repeated_reads_do_not_reopen_csvs(self) -> None:
        from buy_or_wait import repository as repository_module

        opened_before = repository_module.csv.reader
        calls = []

        def counting_reader(*args, **kwargs):
            calls.append(1)
            return opened_before(*args, **kwargs)

        repository_module.csv.reader = counting_reader
        try:
            first = self.repository.load_request_case("request_100")
            second = self.repository.load_request_case("request_100")
            self.assertEqual(first, second)
            self.assertEqual([], calls)
        finally:
            repository_module.csv.reader = opened_before

    def test_ac02_sample_case_is_isolated(self) -> None:
        case = self.repository.load_request_case("request_03")
        self.assertEqual("user_03", case.request.user_id)
        self.assertEqual(["message_02"], [m.message_id for m in case.messages])
        self.assertEqual(["image_01"], [i.image_id for i in case.images])
        for event in case.events:
            self.assertEqual("user_03", event.user_id)
        blank_events = [e for e in case.events if e.amount is None]
        self.assertEqual(1, len(blank_events))
        self.assertIsNone(blank_events[0].amount)

    def test_ac03_exact_parsing_reaches_domain_types(self) -> None:
        case = self.repository.load_request_case("request_01")
        self.assertEqual(25256, case.request.requested_amount)
        self.assertEqual(18000, case.profile.minimum_balance_to_keep)
        self.assertEqual(PaymentMethod.FULL_PAYMENT, case.payment_options[0].payment_method)
        blank_events = [e for e in case.events if e.amount is None]
        for event in blank_events:
            self.assertIsNone(event.amount)


class ValidationFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        build_minimal_dataset(self._tmp)

    def assert_reason(self, expected_code: str) -> None:
        with self.assertRaises(RepositoryValidationError) as caught:
            DatasetRepository.from_directory(self._tmp)
        self.assertEqual(expected_code, caught.exception.reason_code)
        self.assertIn(expected_code, str(caught.exception))
        self.assertNotIn("request_text", str(caught.exception))

    def test_missing_required_value(self) -> None:
        mutate(self._tmp, "financial_profiles.csv", 0, "current_available_balance", None)
        self.assert_reason("missing_required_value")

    def test_invalid_decimal(self) -> None:
        mutate(self._tmp, "financial_profiles.csv", 0, "current_available_balance", "abc")
        self.assert_reason("invalid_decimal")

    def test_nan_decimal(self) -> None:
        mutate(self._tmp, "financial_profiles.csv", 0, "current_available_balance", "NaN")
        self.assert_reason("invalid_decimal")

    def test_infinite_decimal(self) -> None:
        mutate(self._tmp, "financial_profiles.csv", 0, "current_available_balance", "Infinity")
        self.assert_reason("invalid_decimal")

    def test_negative_decimal(self) -> None:
        mutate(self._tmp, "financial_profiles.csv", 0, "current_available_balance", "-5")
        self.assert_reason("negative_amount")

    def test_invalid_boolean(self) -> None:
        mutate(self._tmp, "sample_requests.csv", 0, "allows_partial_payment", "yes")
        self.assert_reason("invalid_boolean")

    def test_invalid_date(self) -> None:
        mutate(self._tmp, "sample_requests.csv", 0, "request_date", "2024-3-3")
        self.assert_reason("invalid_date")

    def test_completion_before_request(self) -> None:
        request_date = datetime.date.fromisoformat(
            read_tmp(self._tmp, "sample_requests.csv")[0]["request_date"]
        )
        before = (request_date - datetime.timedelta(days=1)).isoformat()
        mutate(self._tmp, "sample_requests.csv", 0, "desired_completion_date", before)
        self.assert_reason("completion_before_request_date")

    def test_invalid_request_type_enum(self) -> None:
        mutate(self._tmp, "sample_requests.csv", 0, "request_type", "vacation")
        self.assert_reason("invalid_enum_value")

    def test_duplicate_event_id(self) -> None:
        rows = read_tmp(self._tmp, "financial_events.csv")
        rows.append(dict(rows[0]))
        write_dataset(self._tmp, {"financial_events.csv": rows})
        self.assert_reason("duplicate_event_id")

    def test_duplicate_message_id(self) -> None:
        rows = read_tmp(self._tmp, "messages.csv")
        if not rows:
            self.skipTest("fixture user has no messages")
        duplicate = dict(rows[0])
        # Distinct links so only the key uniqueness invariant can fire.
        duplicate["request_id"] = ""
        duplicate["related_event_id"] = ""
        rows.append(duplicate)
        write_dataset(self._tmp, {"messages.csv": rows})
        self.assert_reason("duplicate_message_id")

    def test_duplicate_message_id_with_distinct_links(self) -> None:
        rows = read_tmp(self._tmp, "messages.csv")
        if not rows:
            self.skipTest("fixture user has no messages")
        duplicate = dict(rows[0])
        events = read_tmp(self._tmp, "financial_events.csv")
        other_event = next(
            (row["event_id"] for row in events if row["event_id"] != rows[0]["related_event_id"]),
            None,
        )
        if other_event is None:
            self.skipTest("fixture user has no second event")
        duplicate["related_event_id"] = other_event
        rows.append(duplicate)
        write_dataset(self._tmp, {"messages.csv": rows})
        self.assert_reason("duplicate_message_id")

    def test_duplicate_image_id(self) -> None:
        rows = read_tmp(self._tmp, "images.csv")
        if not rows:
            self.skipTest("fixture user has no images")
        rows.append(dict(rows[0]))
        write_dataset(self._tmp, {"images.csv": rows})
        self.assert_reason("duplicate_image_id")

    def test_duplicate_image_id_with_distinct_event_link(self) -> None:
        rows = read_tmp(self._tmp, "images.csv")
        if not rows:
            self.skipTest("fixture user has no images")
        events = read_tmp(self._tmp, "financial_events.csv")
        blank_ids = [row["event_id"] for row in events if row["amount"] == ""]
        if len(blank_ids) < 2:
            self.skipTest("fixture user has fewer than two blank-amount events")
        duplicate = dict(rows[0])
        duplicate["related_event_id"] = next(
            blank_id for blank_id in blank_ids if blank_id != rows[0]["related_event_id"]
        )
        rows.append(duplicate)
        write_dataset(self._tmp, {"images.csv": rows})
        self.assert_reason("duplicate_image_id")

    def test_unknown_linked_event(self) -> None:
        rows = read_tmp(self._tmp, "financial_events.csv")
        rows[0]["linked_event_id"] = "event_missing"
        write_dataset(self._tmp, {"financial_events.csv": rows})
        self.assert_reason("unknown_linked_event")

    def test_self_linked_event(self) -> None:
        rows = read_tmp(self._tmp, "financial_events.csv")
        rows[0]["linked_event_id"] = rows[0]["event_id"]
        write_dataset(self._tmp, {"financial_events.csv": rows})
        self.assert_reason("self_linked_event")

    def test_unknown_profile_for_request(self) -> None:
        mutate(self._tmp, "sample_requests.csv", 0, "user_id", "user_missing")
        self.assert_reason("unknown_profile")

    def test_wrong_user_message_request_link(self) -> None:
        rows = read_tmp(self._tmp, "messages.csv")
        if not rows:
            self.skipTest("fixture user has no messages")
        # The fixture's second sample row belongs to a different user, so a
        # known but foreign request link triggers the wrong-user failure.
        foreign_request = read_tmp(self._tmp, "sample_requests.csv")[1]["request_id"]
        rows[0]["request_id"] = foreign_request
        write_dataset(self._tmp, {"messages.csv": rows})
        self.assert_reason("wrong_user_request_link")

    def test_unknown_image_event_link(self) -> None:
        rows = read_tmp(self._tmp, "images.csv")
        if not rows:
            self.skipTest("fixture user has no images")
        rows[0]["related_event_id"] = "event_missing"
        write_dataset(self._tmp, {"images.csv": rows})
        self.assert_reason("unknown_event_link")

    def test_image_links_to_non_blank_event(self) -> None:
        rows = read_tmp(self._tmp, "images.csv")
        if not rows:
            self.skipTest("fixture user has no images")
        events = read_tmp(self._tmp, "financial_events.csv")
        non_blank = next(row["event_id"] for row in events if row["amount"] != "")
        rows[0]["related_event_id"] = non_blank
        write_dataset(self._tmp, {"images.csv": rows})
        self.assert_reason("image_links_to_non_blank_event")

    def test_blank_event_without_image(self) -> None:
        rows = read_tmp(self._tmp, "images.csv")
        if not rows:
            self.skipTest("fixture user has no images")
        blank_id = rows[0]["related_event_id"]
        write_dataset(self._tmp, {"images.csv": []})
        events = read_tmp(self._tmp, "financial_events.csv")
        for row in events:
            if row["event_id"] == blank_id:
                row["amount"] = "100"
        write_dataset(self._tmp, {"financial_events.csv": events})
        # restore blank event to force the blank-without-image failure
        events = read_tmp(self._tmp, "financial_events.csv")
        for row in events:
            if row["event_id"] == blank_id:
                row["amount"] = ""
        write_dataset(self._tmp, {"financial_events.csv": events})
        self.assert_reason("blank_event_without_image")

    def test_missing_installment_cap(self) -> None:
        mutate(self._tmp, "financial_profiles.csv", 0, "max_installment_months", None)
        rows = read_tmp(self._tmp, "financial_profiles.csv")
        methods = rows[0]["payment_methods_user_will_consider"]
        if "installments" not in methods:
            rows[0]["payment_methods_user_will_consider"] = "full_payment|installments"
            write_dataset(self._tmp, {"financial_profiles.csv": rows})
        self.assert_reason("missing_installment_cap")

    def test_unexpected_installment_cap(self) -> None:
        rows = read_tmp(self._tmp, "financial_profiles.csv")
        rows[0]["payment_methods_user_will_consider"] = "full_payment"
        rows[0]["max_installment_months"] = "6"
        write_dataset(self._tmp, {"financial_profiles.csv": rows})
        self.assert_reason("unexpected_installment_cap")

    def test_protected_category_is_reducible(self) -> None:
        rows = read_tmp(self._tmp, "financial_profiles.csv")
        categories = rows[0]["expense_categories_to_protect"]
        first = categories.split("|")[0] if categories else "rent"
        rows[0]["expense_categories_to_protect"] = first
        rows[0]["expense_categories_user_is_willing_to_reduce"] = first
        write_dataset(self._tmp, {"financial_profiles.csv": rows})
        self.assert_reason("protected_category_is_reducible")

    def test_invalid_pipe_list_duplicate(self) -> None:
        rows = read_tmp(self._tmp, "financial_profiles.csv")
        first = rows[0]["expense_categories_to_protect"].split("|")[0] or "rent"
        rows[0]["expense_categories_user_is_willing_to_reduce"] = f"{first}|{first}"
        write_dataset(self._tmp, {"financial_profiles.csv": rows})
        self.assert_reason("pipe_list_has_duplicate")

    def test_invalid_pipe_list_on_payment_methods(self) -> None:
        rows = read_tmp(self._tmp, "financial_profiles.csv")
        methods = rows[0]["payment_methods_user_will_consider"].split("|")
        rows[0]["payment_methods_user_will_consider"] = f"{methods[0]}|{methods[0]}"
        write_dataset(self._tmp, {"financial_profiles.csv": rows})
        self.assert_reason("pipe_list_has_duplicate")

    def test_empty_pipe_token_on_payment_methods(self) -> None:
        rows = read_tmp(self._tmp, "financial_profiles.csv")
        rows[0]["payment_methods_user_will_consider"] = "|full_payment"
        write_dataset(self._tmp, {"financial_profiles.csv": rows})
        self.assert_reason("pipe_list_has_empty_token")

    def test_missing_minimum_allowed_amount(self) -> None:
        events = read_tmp(self._tmp, "financial_events.csv")
        flexible = next(
            (i for i, row in enumerate(events) if row["flexibility"] == "reducible"),
            None,
        )
        if flexible is None:
            self.skipTest("fixture user has no reducible events")
        events[flexible]["minimum_allowed_amount"] = ""
        write_dataset(self._tmp, {"financial_events.csv": events})
        self.assert_reason("missing_minimum_allowed_amount")

    def test_option_total_mismatch(self) -> None:
        rows = read_tmp(self._tmp, "request_payment_options.csv")
        index = next(
            i
            for i, row in enumerate(rows)
            if row["payment_method"] == "installments"
        )
        mutate(
            self._tmp,
            "request_payment_options.csv",
            index,
            "total_payable_amount",
            "1.00",
        )
        self.assert_reason("option_total_mismatch")

    def test_full_payment_amount_mismatch(self) -> None:
        rows = read_tmp(self._tmp, "request_payment_options.csv")
        index = next(
            i for i, row in enumerate(rows) if row["payment_method"] == "full_payment"
        )
        mutate(
            self._tmp,
            "request_payment_options.csv",
            index,
            "payment_amount",
            "2.00",
        )
        self.assert_reason("full_payment_amount_mismatch")

    def test_missing_full_payment_option(self) -> None:
        rows = read_tmp(self._tmp, "request_payment_options.csv")
        keep = [row for row in rows if row["payment_method"] != "full_payment"]
        write_dataset(self._tmp, {"request_payment_options.csv": keep})
        self.assert_reason("missing_full_payment_option")

    def test_installment_option_without_frequency(self) -> None:
        rows = read_tmp(self._tmp, "request_payment_options.csv")
        index = next(
            (
                i
                for i, row in enumerate(rows)
                if row["payment_method"] == "installments"
            ),
            None,
        )
        if index is None:
            self.skipTest("fixture request has no installments option")
        mutate(self._tmp, "request_payment_options.csv", index, "payment_frequency_days", None)
        self.assert_reason("missing_frequency_installments")

    def test_unexpected_header(self) -> None:
        path = self._tmp / "financial_profiles.csv"
        content = path.read_text(encoding="utf-8").replace(
            "user_id,home_currency,", "user_id,drifted_header,home_currency,"
        )
        path.write_text(content, encoding="utf-8")
        self.assert_reason("unexpected_header")


class RedactionTests(unittest.TestCase):
    def test_error_message_carries_no_carrier_content(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            build_minimal_dataset(tmp)
            rows = read_tmp(tmp, "sample_requests.csv")
            rows[0]["request_text"] = "SECRET-TEXT-should-not-appear"
            write_dataset(tmp, {"sample_requests.csv": rows})
            rows[0]["request_type"] = "bogus_type"
            write_dataset(tmp, {"sample_requests.csv": rows})
            with self.assertRaises(RepositoryValidationError) as caught:
                DatasetRepository.from_directory(tmp)
            self.assertNotIn("SECRET-TEXT", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
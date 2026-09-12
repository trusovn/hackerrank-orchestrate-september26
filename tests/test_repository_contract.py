import csv
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HEADERS = {
    "exchange_rates.csv": ["rate_date", "from_currency", "to_currency", "rate"],
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
    "images.csv": ["image_id", "user_id", "request_id", "related_event_id"],
    "messages.csv": [
        "message_id",
        "user_id",
        "request_id",
        "related_event_id",
        "sent_at",
        "source_type",
        "message_text",
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
    "requests.csv": [
        "request_id",
        "user_id",
        "request_date",
        "request_type",
        "requested_amount",
        "desired_completion_date",
        "allows_partial_payment",
        "request_text",
    ],
    "output.csv": [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ],
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class RepositoryContractTests(unittest.TestCase):
    def test_required_dataset_files_have_authoritative_headers(self) -> None:
        dataset_dir = REPO_ROOT / "dataset"
        for filename, expected_header in EXPECTED_HEADERS.items():
            with self.subTest(filename=filename):
                with (dataset_dir / filename).open(encoding="utf-8", newline="") as handle:
                    actual_header = next(csv.reader(handle))
                self.assertEqual(expected_header, actual_header)

    def test_output_template_covers_each_evaluation_request_once(self) -> None:
        dataset_dir = REPO_ROOT / "dataset"
        request_ids = [row["request_id"] for row in read_rows(dataset_dir / "requests.csv")]
        output_ids = [row["request_id"] for row in read_rows(dataset_dir / "output.csv")]

        self.assertEqual(250, len(request_ids))
        self.assertEqual(len(request_ids), len(set(request_ids)))
        self.assertEqual(request_ids, output_ids)

    def test_each_declared_image_file_exists(self) -> None:
        dataset_dir = REPO_ROOT / "dataset"
        for row in read_rows(dataset_dir / "images.csv"):
            image_path = dataset_dir / "media" / "images" / f'{row["image_id"]}.png'
            with self.subTest(image_id=row["image_id"]):
                self.assertTrue(image_path.is_file(), image_path)

    def test_required_submission_source_locations_exist(self) -> None:
        self.assertTrue((REPO_ROOT / "code" / "main.py").is_file())
        self.assertTrue(
            (REPO_ROOT / "code" / "evaluation" / "usage_report.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()


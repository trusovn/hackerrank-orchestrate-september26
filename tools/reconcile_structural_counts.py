"""Reproduce the IA-007 structural reconciliation counts (REC-01/02/03/04/13).

Deterministic, read-only, standard-library only. Prints a JSON report to
stdout and writes nothing. Scope, formulas, and verdicts are recorded in
docs/initial-analysis/06-structural-reconciliation.md.
"""
import csv
import hashlib
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = REPO_ROOT / "dataset"


def _rows(name):
    with (DATASET / name).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _date(value):
    return date.fromisoformat(value) if value else None


def _installment_end(first_payment_date, number_of_payments, frequency_days):
    return first_payment_date + timedelta(
        days=(number_of_payments - 1) * (frequency_days or 0)
    )


def _months_elapsed(first, end):
    months = (end.year - first.year) * 12 + (end.month - first.month)
    if end.day < first.day:
        months -= 1
    return max(months, 0)


def compute():
    requests = _rows("requests.csv")
    samples = _rows("sample_requests.csv")
    profiles = _rows("financial_profiles.csv")
    events = _rows("financial_events.csv")
    options = _rows("request_payment_options.csv")
    messages = _rows("messages.csv")
    images = _rows("images.csv")
    rates = _rows("exchange_rates.csv")

    fingerprint = {}
    for path in sorted(p for p in DATASET.rglob("*") if p.is_file()):
        fingerprint[str(path.relative_to(DATASET))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    sample_ids = {r["request_id"] for r in samples}
    sample_users = {r["user_id"] for r in samples}
    request_by_id = {r["request_id"]: r for r in requests}
    request_by_id.update({r["request_id"]: r for r in samples})
    profile_by_user = {p["user_id"]: p for p in profiles}
    user_of_request = {rid: r["user_id"] for rid, r in request_by_id.items()}
    request_of_user = {u: rid for rid, u in user_of_request.items()}
    request_users = set(request_of_user)
    if set(request_of_user) != {e["user_id"] for e in events}:
        raise ValueError("event users do not map 1:1 onto requests")
    if len(request_of_user) != len(requests) + len(samples):
        raise ValueError("users and requests are not 1:1")

    report = {
        "fingerprint": {
            "git_revision_note": "record in the derived report; tool is file-based only",
            "files": fingerprint,
            "row_counts": {
                "requests": len(requests),
                "sample_requests": len(samples),
                "financial_profiles": len(profiles),
                "financial_events": len(events),
                "request_payment_options": len(options),
                "messages": len(messages),
                "images": len(images),
                "exchange_rates": len(rates),
            },
        }
    }

    option_request_ids = {o["request_id"] for o in options}
    numeric_ids = sorted(option_request_ids, key=lambda x: int(x.split("_")[1]))
    per_request = Counter(o["request_id"] for o in options)
    report["rec02"] = {
        "options_total": len(options),
        "distinct_requests_covered": len(option_request_ids),
        "numeric_request_range": [numeric_ids[0], numeric_ids[-1]],
        "options_per_request_distribution": dict(Counter(per_request.values())),
        "sample_requests_with_options": len(option_request_ids & sample_ids),
        "eval_requests_total": len(requests),
        "eval_requests_with_options": len(
            (option_request_ids & set(request_by_id)) - sample_ids
        ),
        "eval_requests_missing_options": sorted(
            set(request_by_id) - option_request_ids
        ),
        "full_payment_options": sum(
            1 for o in options if o["payment_method"] == "full_payment"
        ),
    }

    installments = [o for o in options if o["payment_method"] == "installments"]
    late = Counter()
    over_cap = Counter()
    elapsed_over_cap = 0
    blank_cap = 0
    installment_scope = Counter(
        "sample" if o["request_id"] in sample_ids else "eval" for o in installments
    )
    for o in installments:
        scope = "sample" if o["request_id"] in sample_ids else "eval"
        first = date.fromisoformat(o["first_payment_date"])
        count = int(o["number_of_payments"])
        frequency = int(o["payment_frequency_days"])
        end = _installment_end(first, count, frequency)
        deadline = date.fromisoformat(
            request_by_id[o["request_id"]]["desired_completion_date"]
        )
        if end > deadline:
            late[scope] += 1
            late["total"] += 1
        cap_raw = profile_by_user[user_of_request[o["request_id"]]][
            "max_installment_months"
        ]
        if not cap_raw:
            blank_cap += 1
            continue
        if count > int(cap_raw):
            over_cap[scope] += 1
            over_cap["total"] += 1
        if _months_elapsed(first, end) > int(cap_raw):
            elapsed_over_cap += 1
    report["rec01"] = {
        "installment_options": dict(installment_scope) | {"total": len(installments)},
        "deadline_formula": "end = first_payment_date + (number_of_payments - 1) * payment_frequency_days",
        "finishing_after_deadline": dict(late),
        "max_month_formula": "number_of_payments > max_installment_months (populated caps only)",
        "max_month_alternative_rejected": "elapsed months between first and last payment > cap",
        "exceeding_max_months": dict(over_cap),
        "exceeding_max_months_elapsed_duration_alternative": elapsed_over_cap,
        "installments_with_blank_max_installment_months": blank_cap,
    }

    future_types = Counter()
    future_directions = Counter()
    future_status = Counter()
    future_rows_scope = Counter()
    future_users_scope = {"sample": set(), "eval": set()}
    future_users_all = set()
    scheduled_income_rows = 0
    scheduled_income_users = {"sample": set(), "eval": set()}
    for e in events:
        if e["status"] not in ("pending", "scheduled"):
            continue
        scope = "sample" if e["user_id"] in sample_users else "eval"
        settle = _date(e["settlement_date"])
        request_date = _date(
            request_by_id[request_of_user[e["user_id"]]]["request_date"]
        )
        if settle is None or settle <= request_date:
            continue
        future_status[e["status"]] += 1
        future_types[e["event_type"]] += 1
        future_directions[e["direction"]] += 1
        future_rows_scope[scope] += 1
        future_users_scope[scope].add(e["user_id"])
        future_users_all.add(e["user_id"])
        if e["event_type"] == "income":
            scheduled_income_rows += 1
            scheduled_income_users[scope].add(e["user_id"])
    report["rec03"] = {
        "future_definition": "status pending/scheduled and settlement_date > request_date",
        "rows_total": sum(future_status.values()),
        "users_total": len(future_users_all),
        "rows_by_scope": dict(future_rows_scope),
        "users_by_scope": {
            "sample": len(future_users_scope["sample"]),
            "eval": len(future_users_scope["eval"]),
        },
        "status": dict(future_status),
        "event_type": dict(future_types),
        "direction": dict(future_directions),
        "scheduled_income_rows": scheduled_income_rows,
        "scheduled_income_users_by_scope": {
            "sample": len(scheduled_income_users["sample"]),
            "eval": len(scheduled_income_users["eval"]),
        },
    }

    on_event_date = Counter()
    on_event_date_types = Counter()
    on_settlement_date = 0
    for e in events:
        request_date = _date(
            request_by_id[request_of_user[e["user_id"]]]["request_date"]
        )
        scope = "sample" if e["user_id"] in sample_users else "eval"
        if e["event_date"] and _date(e["event_date"]) == request_date:
            on_event_date[scope] += 1
            on_event_date["total"] += 1
            on_event_date_types[e["event_type"]] += 1
        if e["settlement_date"] and _date(e["settlement_date"]) == request_date:
            on_settlement_date += 1
    report["rec04"] = {
        "event_date_equals_request_date": dict(on_event_date),
        "event_date_equals_request_date_types": dict(on_event_date_types),
        "settlement_date_equals_request_date": on_settlement_date,
    }

    image_event_ids = {i["related_event_id"] for i in images}
    blank_amount_events = [e for e in events if not e["amount"]]
    image_users = {e["user_id"] for e in events if e["event_id"] in image_event_ids}
    report["rec13"] = {
        "images": len(images),
        "image_links_resolved": len(image_event_ids & {e["event_id"] for e in events}),
        "blank_amount_events": len(blank_amount_events),
        "blank_amounts_without_image": sorted(
            e["event_id"] for e in blank_amount_events
            if e["event_id"] not in image_event_ids
        ),
        "image_backed_share_of_all_events_pct": round(
            100.0 * len(image_event_ids) / len(events), 4
        ),
        "images_over_messages_pct": round(100.0 * len(images) / len(messages), 2),
        "sample_users_with_image_events": len(image_users & sample_users),
        "claimed_7_4_pct": 7.4,
    }
    return report


def main():
    print(json.dumps(compute(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
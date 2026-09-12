"""Deterministic typed-evidence boundary for carrier-to-fact resolution.

``resolve_case_evidence`` converts every supplied message and image carrier on
a ``RequestCase`` into validated, provenance-bearing ``EvidenceFact`` values or
explicit conservative diagnostics. The module is offline and deterministic: it
performs no FX conversion, no recurrence projection, no affordability
arithmetic, no plan selection, no output writing, and no provider/network
calls. Embedded carrier instructions are inert.

Carrier text is not reachable through the approved repository boundary
(``MessageRecord`` intentionally discards raw ``message_text``). Message
classification therefore consumes participant-derived validated extracted facts
keyed by the exact ``message_id``, in the same way the 16 reviewed image
outcomes are keyed by ``image_id``. An unknown or changed carrier never
inherits a cached value by position or similarity: every cached row is
re-validated against the actual case links, currencies, directions, and
statuses at resolve time, and any mismatch fails closed to a diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from .domain import (
    CurrencyCode,
    Direction,
    EventRecord,
    EventStatus,
    EventType,
    EvidenceFact,
    EvidenceFactType,
    ImageRecord,
    MessageRecord,
    RequestCase,
    SourceReference,
)

__all__ = [
    "EvidenceDiagnostic",
    "EvidenceFactCandidate",
    "EvidenceResolution",
    "resolve_case_evidence",
]

# --------------------------------------------------------------------------
# Public result types
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceDiagnostic:
    """Safe, redacted outcome for an ignored, unresolved, or invalid carrier.

    Diagnostics carry a stable reason code and supplied source IDs only. Raw
    carrier text, image content, model responses, and extracted excerpts never
    appear in a diagnostic.
    """

    carrier_type: str
    carrier_id: str
    reason_code: str
    source_ids: tuple[str, ...]
    blocks_downstream: bool = False

@dataclass(frozen=True)
class EvidenceFactCandidate:
    """Participant-derived validated extracted fact for one exact carrier.

    Only supplied, review-accepted values are stored. ``target_event_id`` and
    ``target_request_id`` are hints that ``resolve_case_evidence`` re-validates
    against the actual case before acceptance.
    """

    carrier_type: str
    carrier_id: str
    user_id: str
    fact_type: EvidenceFactType
    amount: str | None = None
    currency: str | None = None
    effective_date: str | None = None
    settlement_date: str | None = None
    recurrence_duration_months: int | None = None
    target_event_id: str | None = None
    target_request_id: str | None = None
    secondary: bool = False
    notes: str = ""

@dataclass(frozen=True)
class EvidenceResolution:
    """Immutable case-level evidence outcome.

    ``facts`` and ``diagnostics`` are in deterministic source order (messages
    first by supplied carrier order, then images). ``blocks_downstream`` is
    true when any carrier produced an unresolved required debit that invents no
    amount and blocks downstream certification.
    """

    facts: tuple[EvidenceFact, ...]
    diagnostics: tuple[EvidenceDiagnostic, ...]
    blocks_downstream: bool = field(default=False)

    def __post_init__(self) -> None:
        if self.blocks_downstream != any(
            diagnostic.blocks_downstream for diagnostic in self.diagnostics
        ):
            raise ValueError("blocking_flag_inconsistent")

# --------------------------------------------------------------------------
# Cached participant-derived validated extracted facts
# --------------------------------------------------------------------------
#
# Message facts: the 17 sample-message decisions from the evidence decision
# pack plus the evaluation-message scenario families classified deterministically
# from the same finite template catalogue. Each row is keyed by exact carrier
# ID and re-validated against the case at resolve time.
#
# Image facts: the 16 reviewed image decisions (15 accepted ``event_amount``
# values with their exact decimals and ``FIN-015`` field labels; ``image_04``
# preserved as unresolved).

_MESSAGE_FACTS: dict[str, tuple[EvidenceFactCandidate, ...]] = {
    "message_01": (
        EvidenceFactCandidate(
            "message",
            "message_01",
            "user_02",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="42750000",
            currency="IDR",
            effective_date="2025-08-15",
            recurrence_duration_months=None,
            notes="salary increase recurring from the explicit date",
        ),
    ),
    "message_02": (
        EvidenceFactCandidate(
            "message",
            "message_02",
            "user_03",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_request_id="request_03",
            notes="next regular payroll confirmed; no amount supplied",
        ),
    ),
    "message_03": (
        EvidenceFactCandidate(
            "message",
            "message_03",
            "user_04",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            target_request_id="request_04",
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_04": (
        EvidenceFactCandidate(
            "message",
            "message_04",
            "user_06",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1037.52",
            currency="EUR",
            target_request_id="request_06",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_05": (
        EvidenceFactCandidate(
            "message",
            "message_05",
            "user_07",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2024-09-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_06": (
        EvidenceFactCandidate(
            "message",
            "message_06",
            "user_08",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1422.85",
            currency="EUR",
            target_request_id="request_08",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_07": (
        EvidenceFactCandidate(
            "message",
            "message_07",
            "user_10",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            target_request_id="request_10",
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_08": (
        EvidenceFactCandidate(
            "message",
            "message_08",
            "user_11",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="38760000",
            currency="IDR",
            target_request_id="request_11",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_09": (
        EvidenceFactCandidate(
            "message",
            "message_09",
            "user_12",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_10": (
        EvidenceFactCandidate(
            "message",
            "message_10",
            "user_14",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="2717",
            currency="EUR",
            effective_date="2025-08-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message",
            "message_10",
            "user_14",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_11": (
        EvidenceFactCandidate(
            "message",
            "message_11",
            "user_15",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1661",
            currency="EUR",
            settlement_date="2026-01-15",
            target_request_id="request_15",
            notes="first salary occurrence confirmed",
        ),
    ),
    "message_12": (
        EvidenceFactCandidate(
            "message",
            "message_12",
            "user_16",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            amount="63952",
            currency="INR",
            target_request_id="request_16",
            notes="rent increases 12 percent, recurring debit",
        ),
    ),
    "message_13": (
        EvidenceFactCandidate(
            "message",
            "message_13",
            "user_18",
            EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            target_request_id="request_18",
            notes="transfer pair classification; pair unresolved",
        ),
    ),
    "message_14": (
        EvidenceFactCandidate(
            "message",
            "message_14",
            "user_20",
            EvidenceFactType.PENDING_CREDIT,
            amount="8640",
            currency="INR",
            settlement_date="2026-02-14",
            target_event_id="event_1785",
            target_request_id="request_20",
            notes="refund pending until settlement",
        ),
    ),
    "message_15": (
        EvidenceFactCandidate(
            "message",
            "message_15",
            "user_22",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="369.6",
            currency="EUR",
            target_event_id="event_1960",
            target_request_id="request_22",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_16": (
        EvidenceFactCandidate(
            "message",
            "message_16",
            "user_23",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            target_request_id="request_23",
            notes="prize still processing; no supplied amount or date",
        ),
    ),
    "message_17": (
        EvidenceFactCandidate(
            "message",
            "message_17",
            "user_24",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="33550",
            currency="INR",
            settlement_date="2025-12-28",
            target_event_id="event_2165",
            notes="settled one-time prize already in cash state",
        ),
    ),
    # ------------------------------------------------------------------
    # Evaluation-message scenario families. Each row was classified from the
    # finite normalized template catalogue; only explicit grounded values are
    # carried and every row is re-validated against the case at resolve time.
    # ------------------------------------------------------------------
    "message_18": (
        EvidenceFactCandidate(
            "message", "message_18", "user_26",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="30780000", currency="IDR", settlement_date="2025-08-15",
            notes="approved invoice credit on settlement; other invoices excluded",
        ),
    ),
    "message_19": (
        EvidenceFactCandidate(
            "message", "message_19", "user_27",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_20": (
        EvidenceFactCandidate(
            "message", "message_20", "user_28",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1452", currency="EUR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_20", "user_28",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="653.40", currency="EUR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_21": (
        EvidenceFactCandidate(
            "message", "message_21", "user_29",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_22": (
        EvidenceFactCandidate(
            "message", "message_22", "user_32",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="54120", currency="ZAR", settlement_date="2025-02-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_23": (
        EvidenceFactCandidate(
            "message", "message_23", "user_33",
            EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            notes="transfer pair classification; pair unresolved",
        ),
    ),
    "message_24": (
        EvidenceFactCandidate(
            "message", "message_24", "user_34",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="196000", currency="INR", settlement_date="2024-12-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_25": (
        EvidenceFactCandidate(
            "message", "message_25", "user_35",
            EvidenceFactType.PENDING_CREDIT,
            amount="12960", currency="INR", settlement_date="2025-11-06",
            target_event_id="event_3230",
            notes="refund pending until settlement",
        ),
    ),
    "message_26": (
        EvidenceFactCandidate(
            "message", "message_26", "user_36",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="2988", currency="USD", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_27": (
        EvidenceFactCandidate(
            "message", "message_27", "user_37",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="21090000", currency="IDR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_27", "user_37",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="9490500", currency="IDR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_28": (
        EvidenceFactCandidate(
            "message", "message_28", "user_38",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="405.35", currency="EUR", settlement_date="2025-07-31",
            target_event_id="event_3491",
            notes="settled one-time prize already in cash state",
        ),
    ),
    "message_29": (
        EvidenceFactCandidate(
            "message", "message_29", "user_40",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1760", currency="EUR", settlement_date="2024-06-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_30": (
        EvidenceFactCandidate(
            "message", "message_30", "user_42",
            EvidenceFactType.RECURRENCE_STOP,
            amount="148000", currency="INR",
            notes="household employment ended; remaining salary continues",
        ),
    ),
    "message_31": (
        EvidenceFactCandidate(
            "message", "message_31", "user_43",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="32870000", currency="IDR", settlement_date="2024-09-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_32": (
        EvidenceFactCandidate(
            "message", "message_32", "user_44",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="115000", currency="INR", settlement_date="2025-02-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_33": (
        EvidenceFactCandidate(
            "message", "message_33", "user_45",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="17290000", currency="IDR", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_34": (
        EvidenceFactCandidate(
            "message", "message_34", "user_47",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_35": (
        EvidenceFactCandidate(
            "message", "message_35", "user_48",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_4535",
            notes="settled receipt confirmation; amount grounded by image_08",
        ),
    ),
    "message_36": (
        EvidenceFactCandidate(
            "message", "message_36", "user_49",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="31464000", currency="IDR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_37": (
        EvidenceFactCandidate(
            "message", "message_37", "user_50",
            EvidenceFactType.RECURRENCE_STOP,
            amount="126000", currency="INR",
            notes="household employment ended; remaining salary continues",
        ),
    ),
    "message_38": (
        EvidenceFactCandidate(
            "message", "message_38", "user_52",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="69000", currency="INR", settlement_date="2024-06-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_39": (
        EvidenceFactCandidate(
            "message", "message_39", "user_53",
            EvidenceFactType.PENDING_CREDIT,
            amount="230.4", currency="USD", settlement_date="2025-11-14",
            target_event_id="event_4994",
            notes="refund pending until settlement",
        ),
    ),
    "message_40": (
        EvidenceFactCandidate(
            "message", "message_40", "user_54",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="42460", currency="ZAR", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_41": (
        EvidenceFactCandidate(
            "message", "message_41", "user_57",
            EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            notes="transfer pair classification; pair unresolved",
        ),
    ),
    "message_42": (
        EvidenceFactCandidate(
            "message", "message_42", "user_58",
            EvidenceFactType.RECURRENCE_STOP,
            amount="25840000", currency="IDR",
            notes="household employment ended; remaining salary continues",
        ),
    ),
    "message_43": (
        EvidenceFactCandidate(
            "message", "message_43", "user_59",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_44": (
        EvidenceFactCandidate(
            "message", "message_44", "user_60",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="530.40", currency="USD",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_45": (
        EvidenceFactCandidate(
            "message", "message_45", "user_61",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_46": (
        EvidenceFactCandidate(
            "message", "message_46", "user_62",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2112", currency="USD", settlement_date="2025-08-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_47": (
        EvidenceFactCandidate(
            "message", "message_47", "user_64",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency refund processing; no home amount yet",
        ),
    ),
    "message_48": (
        EvidenceFactCandidate(
            "message", "message_48", "user_65",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_49": (
        EvidenceFactCandidate(
            "message", "message_49", "user_66",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="116000", currency="INR", settlement_date="2026-04-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_50": (
        EvidenceFactCandidate(
            "message", "message_50", "user_68",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2025-02-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_51": (
        EvidenceFactCandidate(
            "message", "message_51", "user_69",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            currency="EUR",
            notes="renewed lease raises rent 12 percent, recurring debit",
        ),
    ),
    "message_52": (
        EvidenceFactCandidate(
            "message", "message_52", "user_70",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="121800", currency="INR",
            target_event_id="event_6532",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_53": (
        EvidenceFactCandidate(
            "message", "message_53", "user_71",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="696", currency="USD", settlement_date="2025-05-15",
            notes="foreign-currency salary at settlement-date rate",
        ),
    ),
    "message_54": (
        EvidenceFactCandidate(
            "message", "message_54", "user_72",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="18700", currency="ZAR", settlement_date="2026-07-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_55": (
        EvidenceFactCandidate(
            "message", "message_55", "user_73",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            currency="INR",
            notes="renewed lease raises rent 12 percent, recurring debit",
        ),
    ),
    "message_56": (
        EvidenceFactCandidate(
            "message", "message_56", "user_74",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="26180", currency="ZAR", settlement_date="2025-08-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_57": (
        EvidenceFactCandidate(
            "message", "message_57", "user_75",
            EvidenceFactType.RECURRENCE_STOP,
            notes="employment ended; stop future salary recurrence",
        ),
    ),
    "message_58": (
        EvidenceFactCandidate(
            "message", "message_58", "user_76",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="3072", currency="USD",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_59": (
        EvidenceFactCandidate(
            "message", "message_59", "user_77",
            EvidenceFactType.PENDING_CREDIT,
            amount="8880", currency="INR", settlement_date="2025-11-12",
            target_event_id="event_7186",
            notes="refund pending until settlement",
        ),
    ),
    "message_60": (
        EvidenceFactCandidate(
            "message", "message_60", "user_80",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="158000", currency="INR",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_61": (
        EvidenceFactCandidate(
            "message", "message_61", "user_81",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            currency="USD",
            notes="renewed lease raises rent 12 percent, recurring debit",
        ),
    ),
    "message_62": (
        EvidenceFactCandidate(
            "message", "message_62", "user_82",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1752", currency="USD",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_62", "user_82",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="788.40", currency="USD",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_63": (
        EvidenceFactCandidate(
            "message", "message_63", "user_83",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="62000", currency="INR", effective_date="2025-05-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_63", "user_83",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_64": (
        EvidenceFactCandidate(
            "message", "message_64", "user_84",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_7941",
            notes="settled receipt confirmation; amount grounded by image_13",
        ),
    ),
    "message_65": (
        EvidenceFactCandidate(
            "message", "message_65", "user_85",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="8618400", currency="IDR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_66": (
        EvidenceFactCandidate(
            "message", "message_66", "user_87",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="251000", currency="INR", effective_date="2026-01-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_66", "user_87",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_67": (
        EvidenceFactCandidate(
            "message", "message_67", "user_88",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="prize requires release charge; unapproved and not cash",
        ),
    ),
    "message_68": (
        EvidenceFactCandidate(
            "message", "message_68", "user_90",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="13420", currency="ZAR", settlement_date="2026-07-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_69": (
        EvidenceFactCandidate(
            "message", "message_69", "user_91",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_8575",
            notes="failed debit attempt ignored; retry remains an obligation",
        ),
    ),
    "message_70": (
        EvidenceFactCandidate(
            "message", "message_70", "user_92",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="49280", currency="ZAR",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_71": (
        EvidenceFactCandidate(
            "message", "message_71", "user_93",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="prize still processing; no supplied amount or date",
        ),
    ),
    "message_72": (
        EvidenceFactCandidate(
            "message", "message_72", "user_94",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="924", currency="EUR", settlement_date="2024-12-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_73": (
        EvidenceFactCandidate(
            "message", "message_73", "user_95",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2025-05-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_74": (
        EvidenceFactCandidate(
            "message", "message_74", "user_98",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1804", currency="EUR", settlement_date="2025-08-15",
            notes="foreign-currency salary at settlement-date rate",
        ),
    ),
    "message_75": (
        EvidenceFactCandidate(
            "message", "message_75", "user_101",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="139700", currency="INR", settlement_date="2025-10-27",
            target_event_id="event_9420",
            notes="settled one-time prize already in cash state",
        ),
    ),
    "message_76": (
        EvidenceFactCandidate(
            "message", "message_76", "user_102",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1419", currency="EUR", settlement_date="2026-04-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_77": (
        EvidenceFactCandidate(
            "message", "message_77", "user_103",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="164880", currency="INR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_78": (
        EvidenceFactCandidate(
            "message", "message_78", "user_104",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="35860", currency="ZAR",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_79": (
        EvidenceFactCandidate(
            "message", "message_79", "user_105",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="70200", currency="INR",
            target_event_id="event_9805",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_80": (
        EvidenceFactCandidate(
            "message", "message_80", "user_106",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1815", currency="EUR", settlement_date="2024-12-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_81": (
        EvidenceFactCandidate(
            "message", "message_81", "user_107",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2123", currency="EUR", settlement_date="2025-05-15",
            notes="approved and processing first salary on scheduled date",
        ),
    ),
    "message_82": (
        EvidenceFactCandidate(
            "message", "message_82", "user_108",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="33440", currency="ZAR",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_83": (
        EvidenceFactCandidate(
            "message", "message_83", "user_110",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="16720", currency="ZAR", settlement_date="2025-08-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_84": (
        EvidenceFactCandidate(
            "message", "message_84", "user_111",
            EvidenceFactType.RECURRENCE_STOP,
            notes="employment ended; stop future salary recurrence",
        ),
    ),
    "message_85": (
        EvidenceFactCandidate(
            "message", "message_85", "user_112",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="627", currency="EUR", settlement_date="2024-06-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_86": (
        EvidenceFactCandidate(
            "message", "message_86", "user_113",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_10521",
            notes="settled receipt confirmation; amount grounded by image_16",
        ),
    ),
    "message_87": (
        EvidenceFactCandidate(
            "message", "message_87", "user_114",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="148200", currency="INR",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_88": (
        EvidenceFactCandidate(
            "message", "message_88", "user_115",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="32450", currency="INR", settlement_date="2024-08-30",
            target_event_id="event_10699",
            notes="settled one-time prize already in cash state",
        ),
    ),
    "message_89": (
        EvidenceFactCandidate(
            "message", "message_89", "user_117",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="1188", currency="EUR", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_90": (
        EvidenceFactCandidate(
            "message", "message_90", "user_118",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="759", currency="EUR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_90", "user_118",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="341.55", currency="EUR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_91": (
        EvidenceFactCandidate(
            "message", "message_91", "user_119",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="176000", currency="INR", effective_date="2025-05-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_91", "user_119",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_92": (
        EvidenceFactCandidate(
            "message", "message_92", "user_120",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="13062500", currency="IDR", settlement_date="2026-03-30",
            target_event_id="event_11129",
            notes="settled investment sale proceeds already in cash state",
        ),
    ),
    "message_93": (
        EvidenceFactCandidate(
            "message", "message_93", "user_122",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="15390000", currency="IDR", settlement_date="2025-08-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_94": (
        EvidenceFactCandidate(
            "message", "message_94", "user_123",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_95": (
        EvidenceFactCandidate(
            "message", "message_95", "user_125",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="748", currency="EUR", settlement_date="2025-11-15",
            notes="foreign-currency salary at settlement-date rate",
        ),
    ),
    "message_96": (
        EvidenceFactCandidate(
            "message", "message_96", "user_126",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="152000", currency="INR", settlement_date="2026-07-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_97": (
        EvidenceFactCandidate(
            "message", "message_97", "user_127",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="50160", currency="ZAR", effective_date="2024-09-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_97", "user_127",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_98": (
        EvidenceFactCandidate(
            "message", "message_98", "user_128",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_99": (
        EvidenceFactCandidate(
            "message", "message_99", "user_129",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="561", currency="USD", settlement_date="2026-03-28",
            target_event_id="event_11925",
            notes="settled one-time prize already in cash state",
        ),
    ),
    "message_100": (
        EvidenceFactCandidate(
            "message", "message_100", "user_130",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="2177.28", currency="USD",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_101": (
        EvidenceFactCandidate(
            "message", "message_101", "user_131",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2025-05-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_102": (
        EvidenceFactCandidate(
            "message", "message_102", "user_132",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1193.40", currency="USD",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_103": (
        EvidenceFactCandidate(
            "message", "message_103", "user_133",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_104": (
        EvidenceFactCandidate(
            "message", "message_104", "user_135",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="828", currency="USD", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_105": (
        EvidenceFactCandidate(
            "message", "message_105", "user_137",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            currency="INR",
            notes="renewed lease raises rent 12 percent, recurring debit",
        ),
    ),
    "message_106": (
        EvidenceFactCandidate(
            "message", "message_106", "user_138",
            EvidenceFactType.PENDING_CREDIT,
            target_event_id="event_12709",
            notes="foreign-currency purchase pending; reserve at settlement",
        ),
    ),
    "message_107": (
        EvidenceFactCandidate(
            "message", "message_107", "user_140",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="31900", currency="ZAR", settlement_date="2025-02-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_108": (
        EvidenceFactCandidate(
            "message", "message_108", "user_141",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="53350", currency="INR", settlement_date="2025-12-27",
            target_event_id="event_13032",
            notes="settled investment sale proceeds already in cash state",
        ),
    ),
    "message_109": (
        EvidenceFactCandidate(
            "message", "message_109", "user_142",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2040", currency="USD", settlement_date="2024-12-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_110": (
        EvidenceFactCandidate(
            "message", "message_110", "user_143",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="8228", currency="ZAR", settlement_date="2025-04-30",
            target_event_id="event_13207",
            notes="settled one-time prize already in cash state",
        ),
    ),
    "message_111": (
        EvidenceFactCandidate(
            "message", "message_111", "user_144",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="864", currency="USD", settlement_date="2026-07-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_112": (
        EvidenceFactCandidate(
            "message", "message_112", "user_145",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="258000", currency="INR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_112", "user_145",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="116100", currency="INR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_113": (
        EvidenceFactCandidate(
            "message", "message_113", "user_147",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="1529", currency="EUR", effective_date="2026-04-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_113", "user_147",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_114": (
        EvidenceFactCandidate(
            "message", "message_114", "user_148",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="19602", currency="ZAR", settlement_date="2024-05-31",
            target_event_id="event_13663",
            notes="settled investment sale proceeds already in cash state",
        ),
    ),
    "message_115": (
        EvidenceFactCandidate(
            "message", "message_115", "user_150",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="893.75", currency="EUR",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_116": (
        EvidenceFactCandidate(
            "message", "message_116", "user_151",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="46170000", currency="IDR", settlement_date="2024-09-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_117": (
        EvidenceFactCandidate(
            "message", "message_117", "user_152",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="818.4", currency="ZAR", settlement_date="2025-02-02",
            target_event_id="event_14026",
            notes="settled one-time employer reimbursement",
        ),
    ),
    "message_118": (
        EvidenceFactCandidate(
            "message", "message_118", "user_153",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency bill pending; no home amount yet",
        ),
    ),
    "message_119": (
        EvidenceFactCandidate(
            "message", "message_119", "user_154",
            EvidenceFactType.RECURRENCE_STOP,
            amount="1628", currency="EUR",
            notes="household employment ended; remaining salary continues",
        ),
    ),
    "message_120": (
        EvidenceFactCandidate(
            "message", "message_120", "user_155",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="84000", currency="INR", effective_date="2025-05-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_120", "user_155",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_121": (
        EvidenceFactCandidate(
            "message", "message_121", "user_156",
            EvidenceFactType.PENDING_CREDIT,
            target_event_id="event_14399",
            notes="disputed card charge; reversal not posted",
        ),
    ),
    "message_122": (
        EvidenceFactCandidate(
            "message", "message_122", "user_157",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="23940000", currency="IDR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_123": (
        EvidenceFactCandidate(
            "message", "message_123", "user_159",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_124": (
        EvidenceFactCandidate(
            "message", "message_124", "user_160",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1672", currency="EUR", settlement_date="2024-06-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_125": (
        EvidenceFactCandidate(
            "message", "message_125", "user_161",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="26790000", currency="IDR", settlement_date="2025-11-15",
            notes="approved and processing first salary on scheduled date",
        ),
    ),
    "message_126": (
        EvidenceFactCandidate(
            "message", "message_126", "user_162",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="29070000", currency="IDR", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_127": (
        EvidenceFactCandidate(
            "message", "message_127", "user_163",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="30400000", currency="IDR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_127", "user_163",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="13680000", currency="IDR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_128": (
        EvidenceFactCandidate(
            "message", "message_128", "user_164",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="44270000", currency="IDR",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_129": (
        EvidenceFactCandidate(
            "message", "message_129", "user_165",
            EvidenceFactType.RECURRENCE_STOP,
            notes="employment ended; stop future salary recurrence",
        ),
    ),
    "message_130": (
        EvidenceFactCandidate(
            "message", "message_130", "user_166",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2340", currency="USD", settlement_date="2024-12-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_131": (
        EvidenceFactCandidate(
            "message", "message_131", "user_167",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2025-05-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_132": (
        EvidenceFactCandidate(
            "message", "message_132", "user_168",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="137150", currency="INR",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_133": (
        EvidenceFactCandidate(
            "message", "message_133", "user_169",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency refund processing; no home amount yet",
        ),
    ),
    "message_134": (
        EvidenceFactCandidate(
            "message", "message_134", "user_170",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="prize still processing; no supplied amount or date",
        ),
    ),
    "message_135": (
        EvidenceFactCandidate(
            "message", "message_135", "user_171",
            EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            notes="transfer pair classification; pair unresolved",
        ),
    ),
    "message_136": (
        EvidenceFactCandidate(
            "message", "message_136", "user_172",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            notes="separate card-account minimums; both obligations kept",
        ),
    ),
    "message_137": (
        EvidenceFactCandidate(
            "message", "message_137", "user_173",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1284", currency="USD", settlement_date="2025-11-15",
            notes="foreign-currency salary at settlement-date rate",
        ),
    ),
    "message_138": (
        EvidenceFactCandidate(
            "message", "message_138", "user_175",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1924.56", currency="EUR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_139": (
        EvidenceFactCandidate(
            "message", "message_139", "user_176",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="847", currency="EUR",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_140": (
        EvidenceFactCandidate(
            "message", "message_140", "user_177",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1731.60", currency="USD",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_141": (
        EvidenceFactCandidate(
            "message", "message_141", "user_178",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2376", currency="EUR", settlement_date="2024-12-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_142": (
        EvidenceFactCandidate(
            "message", "message_142", "user_179",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="prize requires release charge; unapproved and not cash",
        ),
    ),
    "message_143": (
        EvidenceFactCandidate(
            "message", "message_143", "user_180",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="59000", currency="INR", settlement_date="2026-07-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_144": (
        EvidenceFactCandidate(
            "message", "message_144", "user_182",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_145": (
        EvidenceFactCandidate(
            "message", "message_145", "user_183",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency bill pending; no home amount yet",
        ),
    ),
    "message_146": (
        EvidenceFactCandidate(
            "message", "message_146", "user_184",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency refund processing; no home amount yet",
        ),
    ),
    "message_147": (
        EvidenceFactCandidate(
            "message", "message_147", "user_185",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            currency="EUR",
            notes="renewed lease raises rent 12 percent, recurring debit",
        ),
    ),
    "message_148": (
        EvidenceFactCandidate(
            "message", "message_148", "user_186",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="31889", currency="ZAR",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_149": (
        EvidenceFactCandidate(
            "message", "message_149", "user_187",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="145000", currency="INR", settlement_date="2024-09-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_150": (
        EvidenceFactCandidate(
            "message", "message_150", "user_188",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="83.16", currency="EUR", settlement_date="2025-02-02",
            target_event_id="event_17401",
            notes="settled one-time employer reimbursement",
        ),
    ),
    "message_151": (
        EvidenceFactCandidate(
            "message", "message_151", "user_189",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="627", currency="EUR", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_152": (
        EvidenceFactCandidate(
            "message", "message_152", "user_191",
            EvidenceFactType.PENDING_CREDIT,
            amount="65.12", currency="EUR", settlement_date="2025-05-10",
            target_event_id="event_17662",
            notes="refund pending until settlement",
        ),
    ),
    "message_153": (
        EvidenceFactCandidate(
            "message", "message_153", "user_193",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1750.32", currency="EUR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_154": (
        EvidenceFactCandidate(
            "message", "message_154", "user_194",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2025-08-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_155": (
        EvidenceFactCandidate(
            "message", "message_155", "user_195",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1222.65", currency="EUR",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_156": (
        EvidenceFactCandidate(
            "message", "message_156", "user_197",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="38190000", currency="IDR", settlement_date="2025-11-15",
            notes="approved and processing first salary on scheduled date",
        ),
    ),
    "message_157": (
        EvidenceFactCandidate(
            "message", "message_157", "user_198",
            EvidenceFactType.PENDING_CREDIT,
            target_event_id="event_18269",
            notes="disputed card charge; reversal not posted",
        ),
    ),
    "message_158": (
        EvidenceFactCandidate(
            "message", "message_158", "user_199",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_159": (
        EvidenceFactCandidate(
            "message", "message_159", "user_200",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_160": (
        EvidenceFactCandidate(
            "message", "message_160", "user_201",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_161": (
        EvidenceFactCandidate(
            "message", "message_161", "user_202",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            notes="separate card-account minimums; both obligations kept",
        ),
    ),
    "message_162": (
        EvidenceFactCandidate(
            "message", "message_162", "user_204",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2024", currency="EUR", settlement_date="2026-01-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_163": (
        EvidenceFactCandidate(
            "message", "message_163", "user_208",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="1664400", currency="IDR",
            target_event_id="event_19182",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_164": (
        EvidenceFactCandidate(
            "message", "message_164", "user_210",
            EvidenceFactType.PENDING_CREDIT,
            target_event_id="event_19334",
            notes="disputed card charge; reversal not posted",
        ),
    ),
    "message_165": (
        EvidenceFactCandidate(
            "message", "message_165", "user_212",
            EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
            effective_date="2025-02-23",
            notes="next salary date replaced; one occurrence",
        ),
    ),
    "message_166": (
        EvidenceFactCandidate(
            "message", "message_166", "user_213",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_167": (
        EvidenceFactCandidate(
            "message", "message_167", "user_214",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_168": (
        EvidenceFactCandidate(
            "message", "message_168", "user_215",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="gig payout pending and not withdrawable",
        ),
    ),
    "message_169": (
        EvidenceFactCandidate(
            "message", "message_169", "user_216",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="2424", currency="USD", effective_date="2026-07-15",
            notes="monthly salary increase recurring from the date",
        ),
    ),
    "message_170": (
        EvidenceFactCandidate(
            "message", "message_170", "user_219",
            EvidenceFactType.RECURRENCE_RESUME,
            amount="1914", currency="EUR", effective_date="2026-04-15",
            notes="salary resumes recurring",
        ),
        EvidenceFactCandidate(
            "message", "message_170", "user_219",
            EvidenceFactType.RECURRING_EXPENSE_NOTICE,
            notes="childcare debit begins; amount unbounded",
            secondary=True,
        ),
    ),
    "message_171": (
        EvidenceFactCandidate(
            "message", "message_171", "user_220",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1346.40", currency="EUR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_172": (
        EvidenceFactCandidate(
            "message", "message_172", "user_221",
            EvidenceFactType.PENDING_CREDIT,
            amount="9440", currency="INR", settlement_date="2025-11-10",
            target_event_id="event_20379",
            notes="refund pending until settlement",
        ),
    ),
    "message_173": (
        EvidenceFactCandidate(
            "message", "message_173", "user_222",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="35200", currency="ZAR", settlement_date="2026-01-15",
            notes="approved invoice credit on settlement",
        ),
    ),
    "message_174": (
        EvidenceFactCandidate(
            "message", "message_174", "user_224",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="2166000", currency="IDR", settlement_date="2025-02-01",
            target_event_id="event_20615",
            notes="settled one-time employer reimbursement",
        ),
    ),
    "message_175": (
        EvidenceFactCandidate(
            "message", "message_175", "user_225",
            EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
            currency="IDR",
            notes="renewed lease raises rent 12 percent, recurring debit",
        ),
    ),
    "message_176": (
        EvidenceFactCandidate(
            "message", "message_176", "user_226",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="260000", currency="INR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_176", "user_226",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="117000", currency="INR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_177": (
        EvidenceFactCandidate(
            "message", "message_177", "user_227",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_178": (
        EvidenceFactCandidate(
            "message", "message_178", "user_228",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="30400000", currency="IDR", settlement_date="2026-04-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_179": (
        EvidenceFactCandidate(
            "message", "message_179", "user_229",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_21101",
            notes="failed debit attempt ignored; retry remains an obligation",
        ),
    ),
    "message_180": (
        EvidenceFactCandidate(
            "message", "message_180", "user_230",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="2827", currency="EUR",
            notes="household source ended; remaining confirmed salary retained",
        ),
    ),
    "message_181": (
        EvidenceFactCandidate(
            "message", "message_181", "user_232",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="2772", currency="EUR", settlement_date="2024-06-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_182": (
        EvidenceFactCandidate(
            "message", "message_182", "user_233",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="16910000", currency="IDR", settlement_date="2025-11-15",
            notes="approved and processing first salary on scheduled date",
        ),
    ),
    "message_183": (
        EvidenceFactCandidate(
            "message", "message_183", "user_234",
            EvidenceFactType.PENDING_CREDIT,
            target_event_id="event_21582",
            notes="disputed card charge; reversal not posted",
        ),
    ),
    "message_184": (
        EvidenceFactCandidate(
            "message", "message_184", "user_235",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency refund processing; no home amount yet",
        ),
    ),
    "message_185": (
        EvidenceFactCandidate(
            "message", "message_185", "user_236",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="2690400", currency="IDR",
            target_event_id="event_21785",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_186": (
        EvidenceFactCandidate(
            "message", "message_186", "user_237",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_187": (
        EvidenceFactCandidate(
            "message", "message_187", "user_238",
            EvidenceFactType.RECURRENCE_STOP,
            amount="912", currency="USD",
            notes="household employment ended; remaining salary continues",
        ),
    ),
    "message_188": (
        EvidenceFactCandidate(
            "message", "message_188", "user_240",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="62000", currency="INR", settlement_date="2026-01-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_189": (
        EvidenceFactCandidate(
            "message", "message_189", "user_241",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_190": (
        EvidenceFactCandidate(
            "message", "message_190", "user_242",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="968", currency="EUR", settlement_date="2025-08-15",
            notes="approved and processing first salary on scheduled date",
        ),
    ),
    "message_191": (
        EvidenceFactCandidate(
            "message", "message_191", "user_245",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1680", currency="USD",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_192": (
        EvidenceFactCandidate(
            "message", "message_192", "user_246",
            EvidenceFactType.RECURRENCE_STOP,
            notes="employment ended; stop future salary recurrence",
        ),
    ),
    "message_193": (
        EvidenceFactCandidate(
            "message", "message_193", "user_247",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="1528.56", currency="EUR",
            notes="temporary reduced pay, next cycle only",
        ),
    ),
    "message_194": (
        EvidenceFactCandidate(
            "message", "message_194", "user_248",
            EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
            amount="1548", currency="USD",
            notes="confirmed base salary; open-deal commission ignored",
        ),
    ),
    "message_195": (
        EvidenceFactCandidate(
            "message", "message_195", "user_249",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="702", currency="USD",
            notes="next-cycle reduction from approved unpaid leave",
        ),
    ),
    "message_196": (
        EvidenceFactCandidate(
            "message", "message_196", "user_250",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="53680", currency="ZAR", settlement_date="2024-12-15",
            notes="first salary from new employer on confirmed date",
        ),
    ),
    "message_197": (
        EvidenceFactCandidate(
            "message", "message_197", "user_252",
            EvidenceFactType.PENDING_CREDIT,
            target_event_id="event_23203",
            notes="disputed card charge; reversal not posted",
        ),
    ),
    "message_198": (
        EvidenceFactCandidate(
            "message", "message_198", "user_253",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_23306",
            notes="failed debit attempt ignored; retry remains an obligation",
        ),
    ),
    "message_199": (
        EvidenceFactCandidate(
            "message", "message_199", "user_254",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_200": (
        EvidenceFactCandidate(
            "message", "message_200", "user_256",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="214000", currency="INR", settlement_date="2024-06-15",
            notes="first salary credit on confirmed date",
        ),
    ),
    "message_201": (
        EvidenceFactCandidate(
            "message", "message_201", "user_259",
            EvidenceFactType.RECURRENCE_CONFIRMATION,
            target_event_id="event_23855",
            notes="failed debit attempt ignored; retry remains an obligation",
        ),
    ),
    "message_202": (
        EvidenceFactCandidate(
            "message", "message_202", "user_261",
            EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            notes="transfer pair classification; pair unresolved",
        ),
    ),
    "message_203": (
        EvidenceFactCandidate(
            "message", "message_203", "user_262",
            EvidenceFactType.RECURRENCE_STOP,
            amount="48260000", currency="IDR",
            notes="household employment ended; remaining salary continues",
        ),
    ),
    "message_204": (
        EvidenceFactCandidate(
            "message", "message_204", "user_263",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="1485", currency="EUR", settlement_date="2025-05-15",
            notes="foreign-currency salary at settlement-date rate",
        ),
    ),
    "message_205": (
        EvidenceFactCandidate(
            "message", "message_205", "user_264",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="10560", currency="INR",
            target_event_id="event_24352",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_206": (
        EvidenceFactCandidate(
            "message", "message_206", "user_265",
            EvidenceFactType.RECURRENCE_STOP,
            notes="seasonal contract ended; stop from message boundary",
        ),
    ),
    "message_207": (
        EvidenceFactCandidate(
            "message", "message_207", "user_266",
            EvidenceFactType.UNREALIZED_VALUE,
            amount="580.8", currency="EUR",
            target_event_id="event_24534",
            notes="non-cash portfolio valuation",
        ),
    ),
    "message_208": (
        EvidenceFactCandidate(
            "message", "message_208", "user_267",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency bill pending; no home amount yet",
        ),
    ),
    "message_209": (
        EvidenceFactCandidate(
            "message", "message_209", "user_268",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="prize still processing; no supplied amount or date",
        ),
    ),
    "message_210": (
        EvidenceFactCandidate(
            "message", "message_210", "user_269",
            EvidenceFactType.CONFIRMED_FUTURE_CREDIT,
            amount="38280", currency="ZAR", settlement_date="2025-11-15",
            notes="approved and processing first salary on scheduled date",
        ),
    ),
    "message_211": (
        EvidenceFactCandidate(
            "message", "message_211", "user_271",
            EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
            amount="103000", currency="INR",
            notes="next regular salary; one-time arrears separated",
        ),
        EvidenceFactCandidate(
            "message", "message_211", "user_271",
            EvidenceFactType.SETTLED_ONE_TIME_CREDIT,
            amount="46350", currency="INR",
            notes="one-time arrears adjustment does not recur",
            secondary=True,
        ),
    ),
    "message_212": (
        EvidenceFactCandidate(
            "message", "message_212", "user_272",
            EvidenceFactType.UNAVAILABLE_CREDIT,
            notes="quarterly bonus unapproved; amount and date unknown",
        ),
    ),
    "message_213": (
        EvidenceFactCandidate(
            "message", "message_213", "user_273",
            EvidenceFactType.INTERNAL_TRANSFER_PAIR,
            notes="transfer pair classification; pair unresolved",
        ),
    ),
    "message_214": (
        EvidenceFactCandidate(
            "message", "message_214", "user_274",
            EvidenceFactType.PENDING_CREDIT,
            notes="foreign-currency refund processing; no home amount yet",
        ),
    ),
    "message_215": (
        EvidenceFactCandidate(
            "message", "message_215", "user_275",
            EvidenceFactType.PENDING_CREDIT,
            amount="1444000", currency="IDR", settlement_date="2025-05-13",
            target_event_id="event_25342",
            notes="refund pending until settlement",
        ),
    ),
}

_IMAGE_FACTS: dict[str, tuple[EvidenceFactCandidate, ...]] = {
    "image_01": (
        EvidenceFactCandidate(
            "image", "image_01", "user_03",
            EvidenceFactType.EVENT_AMOUNT,
            amount="4365000", currency="IDR",
            target_event_id="event_253", target_request_id="request_03",
            notes="Net Pay",
        ),
    ),
    "image_02": (
        EvidenceFactCandidate(
            "image", "image_02", "user_16",
            EvidenceFactType.EVENT_AMOUNT,
            amount="100000", currency="INR",
            target_event_id="event_1442", target_request_id="request_16",
            notes="Balance Due",
        ),
    ),
    "image_03": (
        EvidenceFactCandidate(
            "image", "image_03", "user_17",
            EvidenceFactType.EVENT_AMOUNT,
            amount="41272", currency="INR",
            target_event_id="event_1545", target_request_id="request_17",
            notes="Cash Paid",
        ),
    ),
    "image_05": (
        EvidenceFactCandidate(
            "image", "image_05", "user_20",
            EvidenceFactType.EVENT_AMOUNT,
            amount="822.05", currency="INR",
            target_event_id="event_1786", target_request_id="request_20",
            notes="Amount due after 06-Feb-2026",
        ),
    ),
    "image_06": (
        EvidenceFactCandidate(
            "image", "image_06", "user_33",
            EvidenceFactType.EVENT_AMOUNT,
            amount="1995", currency="INR",
            target_event_id="event_3051", target_request_id="request_33",
            notes="Total",
        ),
    ),
    "image_07": (
        EvidenceFactCandidate(
            "image", "image_07", "user_35",
            EvidenceFactType.EVENT_AMOUNT,
            amount="8528.10", currency="INR",
            target_event_id="event_3231", target_request_id="request_35",
            notes="Total",
        ),
    ),
    "image_08": (
        EvidenceFactCandidate(
            "image", "image_08", "user_48",
            EvidenceFactType.EVENT_AMOUNT,
            amount="15339", currency="INR",
            target_event_id="event_4535", target_request_id="request_48",
            notes="Total Amount Received",
        ),
    ),
    "image_09": (
        EvidenceFactCandidate(
            "image", "image_09", "user_55",
            EvidenceFactType.EVENT_AMOUNT,
            amount="723", currency="INR",
            target_event_id="event_5170", target_request_id="request_55",
            notes="Total Amount Received",
        ),
    ),
    "image_10": (
        EvidenceFactCandidate(
            "image", "image_10", "user_64",
            EvidenceFactType.EVENT_AMOUNT,
            amount="79679.26", currency="INR",
            target_event_id="event_6033", target_request_id="request_64",
            notes="Balance Due",
        ),
    ),
    "image_11": (
        EvidenceFactCandidate(
            "image", "image_11", "user_73",
            EvidenceFactType.EVENT_AMOUNT,
            amount="3650", currency="INR",
            target_event_id="event_6859", target_request_id="request_73",
            notes="Amount Payable",
        ),
    ),
    "image_12": (
        EvidenceFactCandidate(
            "image", "image_12", "user_78",
            EvidenceFactType.EVENT_AMOUNT,
            amount="33.50", currency="USD",
            target_event_id="event_7307", target_request_id="request_78",
            notes="Total",
        ),
    ),
    "image_13": (
        EvidenceFactCandidate(
            "image", "image_13", "user_84",
            EvidenceFactType.EVENT_AMOUNT,
            amount="2298", currency="INR",
            target_event_id="event_7941", target_request_id="request_84",
            notes="Total paid",
        ),
    ),
    "image_14": (
        EvidenceFactCandidate(
            "image", "image_14", "user_101",
            EvidenceFactType.EVENT_AMOUNT,
            amount="4543", currency="INR",
            target_event_id="event_9421", target_request_id="request_101",
            notes="TOTAL",
        ),
    ),
    "image_15": (
        EvidenceFactCandidate(
            "image", "image_15", "user_105",
            EvidenceFactType.EVENT_AMOUNT,
            amount="9968", currency="INR",
            target_event_id="event_9806", target_request_id="request_105",
            notes="Grand Total",
        ),
    ),
    "image_16": (
        EvidenceFactCandidate(
            "image", "image_16", "user_113",
            EvidenceFactType.EVENT_AMOUNT,
            amount="393.22", currency="INR",
            target_event_id="event_10521", target_request_id="request_113",
            notes="Total",
        ),
    ),
}

# --------------------------------------------------------------------------
# Fact-type field-combination contracts (fail-closed validation)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _FieldContract:
    required: frozenset[str]
    forbidden: frozenset[str]

_AMOUNT = frozenset({"amount", "currency"})
_DATE_EFFECTIVE = frozenset({"effective_date"})
_DATE_SETTLEMENT = frozenset({"settlement_date"})

_FIELD_CONTRACTS: dict[EvidenceFactType, _FieldContract] = {
    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT: _FieldContract(
        frozenset(), _DATE_SETTLEMENT
    ),
    EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT: _FieldContract(
        frozenset(), _DATE_EFFECTIVE | _DATE_SETTLEMENT
    ),
    EvidenceFactType.RECURRENCE_CONFIRMATION: _FieldContract(
        frozenset(), frozenset({"amount", "currency", "effective_date", "settlement_date"})
    ),
    EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT: _FieldContract(
        _DATE_EFFECTIVE, frozenset({"amount", "currency", "settlement_date"})
    ),
    EvidenceFactType.RECURRENCE_STOP: _FieldContract(
        frozenset(), frozenset({"effective_date", "settlement_date"})
    ),
    EvidenceFactType.RECURRENCE_RESUME: _FieldContract(
        _AMOUNT | _DATE_EFFECTIVE, frozenset({"settlement_date"})
    ),
    EvidenceFactType.RECURRING_EXPENSE_AMENDMENT: _FieldContract(
        frozenset(), _DATE_SETTLEMENT
    ),
    EvidenceFactType.CONFIRMED_FUTURE_CREDIT: _FieldContract(
        _AMOUNT | _DATE_SETTLEMENT, frozenset({"effective_date"})
    ),
    EvidenceFactType.UNAVAILABLE_CREDIT: _FieldContract(
        frozenset(), frozenset({"amount", "currency", "effective_date", "settlement_date"})
    ),
    EvidenceFactType.PENDING_CREDIT: _FieldContract(
        frozenset(), frozenset({"effective_date"})
    ),
    EvidenceFactType.UNREALIZED_VALUE: _FieldContract(
        _AMOUNT, frozenset({"effective_date", "settlement_date"})
    ),
    EvidenceFactType.SETTLED_ONE_TIME_CREDIT: _FieldContract(
        _AMOUNT, _DATE_EFFECTIVE
    ),
    EvidenceFactType.INTERNAL_TRANSFER_PAIR: _FieldContract(
        frozenset(), frozenset({"amount", "currency", "effective_date", "settlement_date"})
    ),
    EvidenceFactType.RECURRING_EXPENSE_NOTICE: _FieldContract(
        frozenset(), frozenset({"amount", "currency", "effective_date", "settlement_date"})
    ),
    EvidenceFactType.EVENT_AMOUNT: _FieldContract(
        _AMOUNT, frozenset({"effective_date", "settlement_date"})
    ),
}

# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

def _parse_amount(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        parsed = Decimal(raw)
    except InvalidOperation:
        raise ValueError("invalid_decimal") from None
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("invalid_amount")
    return parsed

def _parse_date(raw: str | None) -> date | None:
    if raw is None:
        return None
    if len(raw) != 10 or raw[4] != "-" or raw[7] != "-":
        raise ValueError("invalid_date")
    return date.fromisoformat(raw)

def _parse_currency(raw: str | None) -> CurrencyCode | None:
    if raw is None:
        return None
    try:
        return CurrencyCode(raw)
    except ValueError:
        raise ValueError("unsupported_currency") from None

def _validate_candidate_shape(candidate: EvidenceFactCandidate) -> None:
    if candidate.carrier_type not in ("message", "image"):
        raise ValueError("unknown_carrier_type")
    if not candidate.carrier_id or not candidate.user_id:
        raise ValueError("missing_carrier_identity")
    contract = _FIELD_CONTRACTS[candidate.fact_type]
    present = {
        "amount": candidate.amount is not None,
        "currency": candidate.currency is not None,
        "effective_date": candidate.effective_date is not None,
        "settlement_date": candidate.settlement_date is not None,
    }
    missing = {name for name in contract.required if not present[name]}
    if missing:
        raise ValueError("missing_required_field")
    extra = {name for name in contract.forbidden if present[name]}
    if extra:
        raise ValueError("unsupported_extra_field")
    if (candidate.amount is None) != (candidate.currency is None) and candidate.amount is not None:
        raise ValueError("amount_currency_mismatch")
    if candidate.recurrence_duration_months is not None:
        if candidate.recurrence_duration_months <= 0:
            raise ValueError("invalid_duration")
    if candidate.amount is not None and candidate.currency is not None:
        _parse_amount(candidate.amount)
        _parse_currency(candidate.currency)
    elif candidate.currency is not None:
        _parse_currency(candidate.currency)
    _parse_date(candidate.effective_date)
    _parse_date(candidate.settlement_date)

def _validate_target(
    candidate: EvidenceFactCandidate,
    case: RequestCase,
    events_by_id: dict[str, EventRecord],
) -> str | None:
    """Validate and return the resolved target event id, or None."""
    if candidate.target_event_id is not None:
        event = events_by_id.get(candidate.target_event_id)
        if event is None or event.user_id != candidate.user_id:
            raise ValueError("unknown_or_foreign_target")
        return event.event_id
    # Series targeting: find the unique compatible same-user series for this
    # fact type. When the carrier names no event and no compatible series
    # exists, the target stays unresolved and the conservative outcome applies.
    return _resolve_series_target(candidate, case)

_SERIES_PROFILES: dict[EvidenceFactType, tuple[EventType, ...]] = {
    EvidenceFactType.RECURRING_AMOUNT_AMENDMENT: (EventType.INCOME,),
    EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT: (EventType.INCOME,),
    EvidenceFactType.RECURRENCE_STOP: (EventType.INCOME,),
    EvidenceFactType.RECURRENCE_RESUME: (EventType.INCOME,),
    EvidenceFactType.RECURRING_EXPENSE_AMENDMENT: (EventType.EXPENSE, EventType.SUBSCRIPTION),
    EvidenceFactType.RECURRING_EXPENSE_NOTICE: (EventType.EXPENSE, EventType.SUBSCRIPTION),
    EvidenceFactType.RECURRENCE_CONFIRMATION: (EventType.INCOME,),
    EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT: (EventType.INCOME,),
}

_SALARY_FACT_TYPES = frozenset(
    {
        EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
        EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
        EvidenceFactType.RECURRENCE_STOP,
        EvidenceFactType.RECURRENCE_RESUME,
        EvidenceFactType.RECURRENCE_CONFIRMATION,
    }
)

_RENT_FACT_TYPES = frozenset({EvidenceFactType.RECURRING_EXPENSE_AMENDMENT})

def _resolve_series_target(
    candidate: EvidenceFactCandidate, case: RequestCase
) -> str | None:
    if candidate.fact_type not in _SERIES_PROFILES:
        return None
    wanted_types = _SERIES_PROFILES[candidate.fact_type]
    candidates = [
        event
        for event in case.events
        if event.user_id == candidate.user_id
        and event.event_type in wanted_types
        and (
            candidate.currency is None
            or event.currency == _parse_currency(candidate.currency)
        )
    ]
    if candidate.fact_type in _SALARY_FACT_TYPES:
        # Salary series: income/salary category rows only. Non-salary income
        # (windfalls, refunds, sales) never inherits a salary amendment.
        salary_rows = [event for event in candidates if event.category == "salary"]
        if not salary_rows:
            return None
        # When a recurring amount repeats across rows, only rows sharing that
        # amount, blank image-pending amounts, or the recurring series'
        # description stay cadence members; variable one-off rows such as
        # open-deal commissions form separate series and never absorb a
        # regular-pay amendment. The anchor is the latest compatible row.
        counts: dict[Decimal, int] = {}
        for event in salary_rows:
            if event.amount is not None:
                counts[event.amount] = counts.get(event.amount, 0) + 1
        recurring_groups = [
            (amount, [e for e in salary_rows if e.amount == amount])
            for amount, count in counts.items()
            if count >= 2
        ]
        selected_group: list[EventRecord] | None = None
        if len(recurring_groups) > 1:
            if candidate.amount is not None:
                parsed_amount = _parse_amount(candidate.amount)
                matching = [
                    rows for amount, rows in recurring_groups
                    if amount == parsed_amount
                ]
                if len(matching) == 1:
                    selected_group = matching[0]
                else:
                    return None
            else:
                return None
        elif recurring_groups:
            selected_group = recurring_groups[0][1]
        if selected_group is not None:
            recurring_amount, _ = recurring_groups[0] if len(recurring_groups) == 1 else (None, None)
            group_rows = selected_group
            descriptions = {event.description for event in group_rows}
            candidates = [
                event
                for event in salary_rows
                if event.amount is None
                or (recurring_amount is not None and event.amount == recurring_amount)
                or event.description in descriptions
            ]
        else:
            candidates = salary_rows
    if candidate.fact_type in _RENT_FACT_TYPES:
        # Rent series: expense/rent rows only; other recurring expenses,
        # including the separate scheduled event named in the pack, never
        # inherit a lease amendment. A separate scheduled/pending obligation
        # is not the recurring cadence anchor.
        candidates = [
            event
            for event in candidates
            if event.category == "rent"
            and event.status is EventStatus.SETTLED
        ]
    if candidate.fact_type is EvidenceFactType.RECURRING_EXPENSE_NOTICE:
        # Childcare notice: no supplied childcare series exists, so no target
        # can be grounded. The unresolved conservative outcome applies.
        return None
    if not candidates:
        return None
    series: dict[tuple[str, str, str], list[EventRecord]] = {}
    for event in candidates:
        key = (event.event_type.value, event.category, event.currency.value)
        series.setdefault(key, []).append(event)
    if len(series) != 1 or len(next(iter(series.values()))) < 1:
        return None
    rows = next(iter(series.values()))
    if len(rows) < 2:
        return None
    return rows[-1].event_id

def _resolve_message_facts(
    case: RequestCase, events_by_id: dict[str, EventRecord]
) -> tuple[tuple[EvidenceFact, ...], tuple[EvidenceDiagnostic, ...]]:
    facts: list[EvidenceFact] = []
    diagnostics: list[EvidenceDiagnostic] = []
    accepted: set[tuple[str, str, str, str]] = set()
    for record in case.messages:
        cached = _MESSAGE_FACTS.get(record.message_id)
        if cached is None:
            diagnostics.append(
                EvidenceDiagnostic(
                    "message", record.message_id, "unclassified_carrier",
                    (record.message_id,),
                )
            )
            continue
        try:
            _resolve_cached_candidates(
                cached, record, case, events_by_id, facts, diagnostics, accepted
            )
        except ValueError as error:
            diagnostics.append(
                EvidenceDiagnostic(
                    "message",
                    record.message_id,
                    _reason_for(error),
                    (record.message_id,),
                )
            )
    return tuple(facts), tuple(diagnostics)

def _resolve_image_facts(
    case: RequestCase, events_by_id: dict[str, EventRecord]
) -> tuple[tuple[EvidenceFact, ...], tuple[EvidenceDiagnostic, ...]]:
    facts: list[EvidenceFact] = []
    diagnostics: list[EvidenceDiagnostic] = []
    accepted: set[tuple[str, str, str, str]] = set()
    for record in case.images:
        cached = _IMAGE_FACTS.get(record.image_id)
        if cached is None:
            # An unknown or changed image never inherits a cached amount.
            diagnostics.append(
                EvidenceDiagnostic(
                    "image", record.image_id, "unavailable_image_review",
                    (record.image_id,),
                )
            )
            continue
        try:
            _resolve_cached_candidates(
                cached, record, case, events_by_id, facts, diagnostics, accepted
            )
        except ValueError as error:
            diagnostics.append(
                EvidenceDiagnostic(
                    "image",
                    record.image_id,
                    _reason_for(error),
                    (record.image_id,),
                )
            )
    return tuple(facts), tuple(diagnostics)

def _resolve_cached_candidates(
    cached: tuple[EvidenceFactCandidate, ...],
    record: MessageRecord | ImageRecord,
    case: RequestCase,
    events_by_id: dict[str, EventRecord],
    facts: list[EvidenceFact],
    diagnostics: list[EvidenceDiagnostic],
    accepted: set[tuple[str, str, str, str]],
) -> None:
    if record.user_id != cached[0].user_id:
        raise ValueError("carrier_user_mismatch")
    for candidate in cached:
        _validate_candidate_shape(candidate)
        if candidate.user_id != record.user_id:
            raise ValueError("carrier_user_mismatch")
        if candidate.secondary:
            _resolve_secondary_candidate(
                candidate, record, case, events_by_id, facts, diagnostics, accepted
            )
            continue
        _resolve_primary_candidate(
            candidate, record, case, events_by_id, facts, diagnostics, accepted
        )

def _resolve_primary_candidate(
    candidate: EvidenceFactCandidate,
    record: MessageRecord | ImageRecord,
    case: RequestCase,
    events_by_id: dict[str, EventRecord],
    facts: list[EvidenceFact],
    diagnostics: list[EvidenceDiagnostic],
    accepted: set[tuple[str, str, str, str]],
) -> None:
    target_event_id = _validate_target(candidate, case, events_by_id)
    _validate_request_target(candidate, case)
    sources = (SourceReference(candidate.carrier_type, record.message_id if isinstance(record, MessageRecord) else record.image_id),)
    fact_type = candidate.fact_type

    # Conservative outcome classes ------------------------------------------------
    if fact_type is EvidenceFactType.UNAVAILABLE_CREDIT:
        diagnostics.append(
            EvidenceDiagnostic(
                candidate.carrier_type, record.message_id if isinstance(record, MessageRecord) else record.image_id,
                "unavailable_credit_no_cash", (record.message_id if isinstance(record, MessageRecord) else record.image_id,),
            )
        )
        return
    if fact_type is EvidenceFactType.RECURRING_EXPENSE_NOTICE:
        # Unbounded required debit: invents no amount and blocks downstream
        # certification until an amount is grounded.
        diagnostics.append(
            EvidenceDiagnostic(
                candidate.carrier_type,
                record.message_id if isinstance(record, MessageRecord) else record.image_id,
                "unresolved_required_debit_blocks",
                (record.message_id if isinstance(record, MessageRecord) else record.image_id,),
                blocks_downstream=True,
            )
        )
        return
    if fact_type is EvidenceFactType.INTERNAL_TRANSFER_PAIR and target_event_id is None:
        diagnostics.append(
            EvidenceDiagnostic(
                candidate.carrier_type,
                record.message_id if isinstance(record, MessageRecord) else record.image_id,
                "unresolved_transfer_pair",
                (record.message_id if isinstance(record, MessageRecord) else record.image_id,),
            )
        )
        return
    if fact_type is EvidenceFactType.RECURRENCE_CONFIRMATION and target_event_id is None:
        diagnostics.append(
            EvidenceDiagnostic(
                candidate.carrier_type,
                record.message_id if isinstance(record, MessageRecord) else record.image_id,
                "unresolved_recurrence_target",
                (record.message_id if isinstance(record, MessageRecord) else record.image_id,),
            )
        )
        return
    if fact_type in (
        EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
        EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
    ) and candidate.amount is None:
        # An amendment without a grounded amount invents no value.
        diagnostics.append(
            EvidenceDiagnostic(
                candidate.carrier_type,
                _carrier_id(record),
                "unresolved_series_target",
                (_carrier_id(record),),
            )
        )
        return
    if fact_type in (
        EvidenceFactType.RECURRING_AMOUNT_AMENDMENT,
        EvidenceFactType.NEXT_CYCLE_AMOUNT_AMENDMENT,
        EvidenceFactType.SETTLEMENT_DATE_REPLACEMENT,
        EvidenceFactType.RECURRENCE_STOP,
        EvidenceFactType.RECURRENCE_RESUME,
        EvidenceFactType.RECURRING_EXPENSE_AMENDMENT,
    ) and target_event_id is None:
        # Unresolved target: amends no event or series.
        diagnostics.append(
            EvidenceDiagnostic(
                candidate.carrier_type,
                record.message_id if isinstance(record, MessageRecord) else record.image_id,
                "unresolved_series_target",
                (record.message_id if isinstance(record, MessageRecord) else record.image_id,),
            )
        )
        return

    amount = _parse_amount(candidate.amount)
    currency = _parse_currency(candidate.currency)
    effective_date = _parse_date(candidate.effective_date)
    settlement_date = _parse_date(candidate.settlement_date)

    if fact_type is EvidenceFactType.EVENT_AMOUNT:
        event = events_by_id[target_event_id]
        if currency != event.currency:
            raise ValueError("event_currency_mismatch")
        if event.amount is not None:
            raise ValueError("event_amount_not_blank")
        # A settled historical debit already reflected in the available
        # balance is history, not a new current debit; a pending/scheduled
        # debit stays a real obligation at its supplied settlement date.
        if event.status is EventStatus.PENDING or event.status is EventStatus.SCHEDULED:
            pass
        elif event.status is not EventStatus.SETTLED:
            raise ValueError("event_status_not_groundable")

    if fact_type is EvidenceFactType.PENDING_CREDIT:
        if target_event_id is not None:
            event = events_by_id[target_event_id]
            if event.status is not EventStatus.PENDING:
                raise ValueError("pending_credit_direction_status")
            if event.direction is Direction.DEBIT:
                # A pending required debit (foreign purchase, disputed
                # charge) stays a reserved obligation on the linked event.
                # Evidence records no cash fact and invents no amount; the
                # conservative diagnostic keeps the carrier first-class.
                diagnostics.append(
                    EvidenceDiagnostic(
                        candidate.carrier_type,
                        _carrier_id(record),
                        "pending_debit_reserved_no_cash",
                        (_carrier_id(record), target_event_id),
                    )
                )
                return
            if event.direction is not Direction.CREDIT:
                raise ValueError("pending_credit_direction_status")
        # Amounts stay reserved but unavailable until settlement; the fact
        # records the stated amount without making it available cash.

    if fact_type is EvidenceFactType.SETTLED_ONE_TIME_CREDIT and target_event_id is not None:
        event = events_by_id[target_event_id]
        if event.direction is not Direction.CREDIT or event.status is not EventStatus.SETTLED:
            raise ValueError("settled_credit_direction_status")

    if fact_type is EvidenceFactType.UNREALIZED_VALUE and target_event_id is not None:
        event = events_by_id[target_event_id]
        if event.direction is not Direction.NON_CASH or event.status is not EventStatus.UNREALIZED:
            raise ValueError("unrealized_value_direction_status")

    key = (
        candidate.carrier_type,
        record.message_id if isinstance(record, MessageRecord) else record.image_id,
        fact_type.value,
        target_event_id or "",
    )
    if key in accepted:
        raise ValueError("duplicate_fact")
    accepted.add(key)

    facts.append(
        EvidenceFact(
            fact_id=f"{record.message_id if isinstance(record, MessageRecord) else record.image_id}::{fact_type.value}",
            fact_type=fact_type,
            sources=sources,
            target_event_id=target_event_id,
            amount=amount,
            currency=currency,
            effective_date=effective_date,
            settlement_date=settlement_date,
            recurrence_duration_months=candidate.recurrence_duration_months,
            notes=candidate.notes,
        )
    )

def _resolve_secondary_candidate(
    candidate: EvidenceFactCandidate,
    record: MessageRecord | ImageRecord,
    case: RequestCase,
    events_by_id: dict[str, EventRecord],
    facts: list[EvidenceFact],
    diagnostics: list[EvidenceDiagnostic],
    accepted: set[tuple[str, str, str, str]],
) -> None:
    if candidate.fact_type is EvidenceFactType.RECURRING_EXPENSE_NOTICE:
        diagnostics.append(
            EvidenceDiagnostic(
                "message",
                record.message_id,
                "unresolved_required_debit_blocks",
                (record.message_id,),
                blocks_downstream=True,
            )
        )
        return
    if candidate.fact_type is EvidenceFactType.SETTLED_ONE_TIME_CREDIT:
        amount = _parse_amount(candidate.amount)
        currency = _parse_currency(candidate.currency)
        settlement_date = _parse_date(candidate.settlement_date)
        key = ("message", record.message_id, candidate.fact_type.value, "")
        if key in accepted:
            raise ValueError("duplicate_fact")
        accepted.add(key)
        facts.append(
            EvidenceFact(
                fact_id=f"{record.message_id}::{candidate.fact_type.value}",
                fact_type=candidate.fact_type,
                sources=(SourceReference("message", record.message_id),),
                target_event_id=None,
                amount=amount,
                currency=currency,
                effective_date=None,
                settlement_date=settlement_date,
                recurrence_duration_months=None,
                notes=candidate.notes,
            )
        )
        return
    raise ValueError("unsupported_secondary_fact")

def _validate_request_target(
    candidate: EvidenceFactCandidate, case: RequestCase
) -> None:
    if candidate.target_request_id is None:
        return
    if candidate.target_request_id != case.request.request_id:
        raise ValueError("request_target_mismatch")

def _carrier_id(record: MessageRecord | ImageRecord) -> str:
    return record.message_id if isinstance(record, MessageRecord) else record.image_id


def _reason_for(error: ValueError) -> str:
    return str(error)

def resolve_case_evidence(case: RequestCase) -> EvidenceResolution:
    """Resolve every supplied carrier on ``case`` into validated facts.

    Messages resolve first in supplied order, then images. Carriers that are
    unknown, unclassified, or fail validation produce explicit conservative
    diagnostics and never become zero-valued or partially trusted facts.
    """
    if not isinstance(case, RequestCase):
        raise ValueError("invalid_case")
    events_by_id = {event.event_id: event for event in case.events}
    if len(events_by_id) != len(case.events):
        raise ValueError("duplicate_event_id")

    message_facts, message_diagnostics = _resolve_message_facts(case, events_by_id)
    image_facts, image_diagnostics = _resolve_image_facts(case, events_by_id)
    facts = message_facts + image_facts
    diagnostics = message_diagnostics + image_diagnostics
    blocks = any(diagnostic.blocks_downstream for diagnostic in diagnostics)
    return EvidenceResolution(
        facts=facts, diagnostics=diagnostics, blocks_downstream=blocks
    )
# app/email_ingestion/filters/rules.py
"""
MVP email filtering rules for Casefile.

Goal (v1):
- Keep it deterministic, cheap, and metadata-based.
- Drop obvious noise (noreply, bulk, lists, receipts/OTPs, system notifications).
- Return a decision + reason you can log and iterate on.

Input expectation:
- Gmail "metadata" message JSON (users.messages.get format=metadata)
  including:
    - id, threadId, internalDate, sizeEstimate
    - payload.headers: [{name, value}, ...]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple


# -----------------------------
# Public API
# -----------------------------


@dataclass(frozen=True)
class RuleDecision:
    keep: bool
    reason: str


def should_keep_email_metadata(
    msg: Dict[str, Any],
    *,
    provider: str = "gmail",
) -> RuleDecision:
    """
    Main predicate. Use this in your celery ingestion loop.

    Returns:
      RuleDecision(keep=True/False, reason="...")
    """

    headers = _headers_map(msg)
    frm_raw = headers.get("from", "")
    subj = headers.get("subject", "")
    to_raw = headers.get("to", "")
    cc_raw = headers.get("cc", "")
    snippet = msg.get("snippet") or ""

    frm = frm_raw.lower()
    subj_l = subj.lower()
    snippet_l = snippet.lower()

    # 1) Hard sender blocks
    if _matches_any(frm, SENDER_CONTAINS_BLOCKLIST):
        return RuleDecision(False, "drop:sender_blocklist")

    # 2) Bulk/list mail headers (best signal)
    # These headers often exist even in "primary" mails for services.
    if _has_any_header(headers, BULK_HEADERS):
        return RuleDecision(False, "drop:bulk_header")

    # 3) Subject keyword blocks (high precision)
    if _matches_any(subj_l, SUBJECT_CONTAINS_BLOCKLIST):
        return RuleDecision(False, "drop:subject_blocklist")

    # 4) Snippet blocks (OTP / login codes often only show here)
    if _matches_any(snippet_l, SNIPPET_CONTAINS_BLOCKLIST):
        return RuleDecision(False, "drop:snippet_blocklist")

    # 5) Recipient count heuristic (mailing lists / announcements)
    # Use raw parsing (cheap). Tune threshold later.
    recipient_count = _count_recipients(to_raw) + _count_recipients(cc_raw)
    if recipient_count >= MAX_RECIPIENTS_TO_KEEP:
        return RuleDecision(False, f"drop:too_many_recipients:{recipient_count}")

    # 6) If you want to keep "real threads", boost keep for reply chains
    # (Don't drop without it though; recruiters may be 1st-touch.)
    # You can use this later for scoring.
    # has_reply_headers = ("in-reply-to" in headers) or ("references" in headers)

    # Default keep
    return RuleDecision(True, "keep")


# -----------------------------
# Config / Rule Tables
# -----------------------------

# Keep this list SHORT for v1. Add as you discover noise.
SENDER_CONTAINS_BLOCKLIST: Tuple[str, ...] = (
    "notifications@github.com",
    "noreply@",
    "no-reply@",
    "do-not-reply@",
    "mailer-daemon",
    "postmaster@",
    # common “systemy” senders (tune later)
    "support@",
    "billing@",
    "receipt@",
    "receipts@",
    "alerts@",
    "updates@",
)

# Headers that strongly imply automated bulk/list mail
BULK_HEADERS: Tuple[str, ...] = (
    "list-unsubscribe",
    "list-id",
    "precedence",  # often "bulk" or "list"
    "auto-submitted",  # auto-generated
    "x-autoresponse",  # various
    "x-auto-response-suppress",
)

# Subject patterns that are usually non-conversational noise
SUBJECT_CONTAINS_BLOCKLIST: Tuple[str, ...] = (
    "verification code",
    "otp",
    "one-time",
    "password reset",
    "reset your password",
    "security alert",
    "new sign-in",
    "login alert",
    "invoice",
    "receipt",
    "statement available",
    "your statement",
    "payment received",
    "payment confirmation",
    "order confirmation",
    "dispatch",
    "delivered",
    "your trip with uber",  # you mentioned Uber volume
    "uber trip",
    "your uber receipt",
    "unsubscribe",
    "digest",
    "newsletter",
)

# Snippet patterns (often contains OTP even when subject is vague)
SNIPPET_CONTAINS_BLOCKLIST: Tuple[str, ...] = (
    "your verification code",
    "use this code",
    "one-time passcode",
    "otp is",
)

# Tune: 5 is a good default for conversation-ish emails.
MAX_RECIPIENTS_TO_KEEP = 6  # drop if >= 6 total To+Cc


# -----------------------------
# Helpers
# -----------------------------


def _headers_map(msg: Dict[str, Any]) -> Dict[str, str]:
    """
    Gmail payload.headers -> lowercase dict.
    If multiple headers with same name exist, last one wins (fine for v1).
    """
    out: Dict[str, str] = {}
    payload = msg.get("payload") or {}
    for h in payload.get("headers", []) or []:
        name = (h.get("name") or "").strip().lower()
        value = (h.get("value") or "").strip()
        if name:
            out[name] = value
    return out


def _has_any_header(headers: Dict[str, str], names: Iterable[str]) -> bool:
    for n in names:
        n_l = n.lower()
        if n_l in headers:
            # special case: precedence exists but isn't bulk/list (still often noisy)
            if n_l == "precedence":
                v = headers.get("precedence", "").lower()
                if "bulk" in v or "list" in v or "junk" in v:
                    return True
                # if precedence exists with something else, don't auto-drop
                continue
            return True
    return False


def _matches_any(text: str, needles: Iterable[str]) -> bool:
    # simple contains, fast and good enough for MVP
    for s in needles:
        if s and s in text:
            return True
    return False


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


def _count_recipients(raw: str) -> int:
    """
    Counts email-like tokens in a To/Cc header.
    It's heuristic (good enough for filtering lists/announcements).
    """
    if not raw:
        return 0
    return len(_EMAIL_RE.findall(raw))

#!/usr/bin/env python3
"""
IRS Transcript Parser
=====================
Library-first: ``from transcript_parser import parse_transcript``

Parses the four IRS transcript types delivered via the IRS Online Account portal:
  - Account Transcript
  - Tax Return Transcript
  - Wage and Income Transcript
  - Record of Account Transcript

Returns a JSON-serialisable dict matching the schema defined in README.md.

CLI usage:
    python3 transcript_parser.py "path/to/transcript.pdf"
    python3 transcript_parser.py "path/to/transcript.pdf" --json
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Import pdf_extract from sibling directory (lazy — only needed for PDF input)
# ---------------------------------------------------------------------------
_PDF_EXTRACTOR_DIR = str(Path(__file__).parent.parent / "pdf-extractor")


def _import_pdf_extract():
    """Lazy import of pdf_extract so text-only usage doesn't require poppler."""
    if _PDF_EXTRACTOR_DIR not in sys.path:
        sys.path.insert(0, _PDF_EXTRACTOR_DIR)
    try:
        from pdf_extract import extract  # noqa: E402
        return extract
    except ImportError as e:
        raise ImportError(
            f"pdf_extract not found at {_PDF_EXTRACTOR_DIR}. "
            "Ensure ../pdf-extractor/pdf_extract.py exists, or pass a .txt file."
        ) from e


# ---------------------------------------------------------------------------
# Load TC code descriptions
# ---------------------------------------------------------------------------
_TC_CODES_PATH = Path(__file__).parent / "tc_codes.json"
try:
    with open(_TC_CODES_PATH) as _f:
        _raw = json.load(_f)
    # Support both flat {"150": {...}} and nested {"codes": {"150": {...}}} schemas.
    TC_CODES: dict[str, dict] = _raw.get("codes", _raw) if isinstance(_raw, dict) else {}
except FileNotFoundError:
    TC_CODES = {}
except json.JSONDecodeError as e:
    print(f"Warning: {_TC_CODES_PATH} is malformed JSON ({e}); TC descriptions unavailable.", file=sys.stderr)
    TC_CODES = {}


# Signed IRS amount as it appears after a label: "$1,234.56", "-$20,000.00", "$-85.00",
# "($8,211.00)", "1,637.54". The sign may precede or follow the "$"; capturing it is what
# keeps a credit balance from parsing as 0.
_AMT = r"(\(?-?\$?-?[\d,]+(?:\.\d+)?\)?)"


def _tc_label(tc: str) -> str:
    """Return a short human label for a TC code, used in anomaly messages."""
    entry = TC_CODES.get(tc, {})
    return entry.get("short") or entry.get("description") or tc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_transcript(pdf_path: str | Path) -> dict:
    """
    Parse an IRS transcript PDF and return a structured dict.

    Parameters
    ----------
    pdf_path : str or Path

    Returns
    -------
    dict — see module docstring / README for full schema.
    """
    pdf_path = Path(pdf_path).resolve()
    extract = _import_pdf_extract()
    result = extract(pdf_path)

    if result.mode == "failed":
        raise ValueError(f"Could not extract text from {pdf_path}: {result.diagnostics}")
    if result.mode == "image":
        raise ValueError(
            f"Transcript appears to be image-based (scanned). "
            f"PNGs at: {result.pngs}. OCR first then pass text to _parse_text()."
        )

    return _parse_text(result.text or "", str(pdf_path))


def _parse_text(text: str, source_path: str = "") -> dict:
    """Parse raw pdftotext output into the schema dict."""
    lines = text.splitlines()

    doc_type          = _detect_doc_type(lines)
    tax_period        = _extract_tax_period(lines)
    form_number       = _extract_form_number(lines)
    taxpayer_name     = _extract_taxpayer_name(lines)
    taxpayer_tin      = _extract_tin(lines)
    filing_status     = _extract_filing_status(lines)
    return_section    = _extract_return_section(lines)
    account_summary   = _extract_account_summary(lines)
    tc_transactions   = _extract_transactions(lines)
    tc_summary        = _build_tc_summary(tc_transactions)
    wage_income_items = _extract_wage_income(lines, doc_type)
    anomalies         = _find_anomalies(tc_transactions, account_summary)

    return {
        "doc_type":           doc_type,
        "tax_period":         tax_period,
        "form_number":        form_number,
        "taxpayer_name":      taxpayer_name,
        "taxpayer_tin":       taxpayer_tin,
        "filing_status":      filing_status,
        "return_section":     return_section,
        "account_summary":    account_summary,
        "tc_transactions":    tc_transactions,
        "tc_summary":         tc_summary,
        "wage_income_items":  wage_income_items,
        "anomalies":          anomalies,
        "_source":            source_path,
    }


# ---------------------------------------------------------------------------
# Transcript type detection
# ---------------------------------------------------------------------------

def _detect_doc_type(lines: list[str]) -> str:
    joined = " ".join(lines[:30]).lower()
    if "record of account" in joined:
        return "IRS-RecordOfAccount-Transcript"
    if "account transcript" in joined:
        return "IRS-Account-Transcript"
    if "wage and income" in joined:
        return "IRS-WageIncome-Transcript"
    if "tax return transcript" in joined:
        return "IRS-Return-Transcript"
    return "IRS-Unknown-Transcript"


# ---------------------------------------------------------------------------
# Header-field extractors
# ---------------------------------------------------------------------------

def _extract_tax_period(lines: list[str]) -> str:
    """Return YYYYMM, e.g. '202012'."""
    mon_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    for line in lines:
        m = re.search(
            r"(?:TAX PERIOD|Tax Period Ending)\s*:\s*(\w+)\.?\s+\d+,?\s+(\d{4})",
            line, re.IGNORECASE
        )
        if m:
            return f"{m.group(2)}{mon_map.get(m.group(1)[:3].lower(), '00')}"
        m2 = re.search(r"Tax Period Requested\s*:\s*([A-Za-z]+),?\s+(\d{4})", line, re.IGNORECASE)
        if m2:
            return f"{m2.group(2)}{mon_map.get(m2.group(1)[:3].lower(), '00')}"
        # 2026+ layouts: "Report for Tax Period Ending: 12-31-2024", "Tax Period Requested: 12-31-2025"
        m3 = re.search(r"(?:TAX PERIOD|Tax Period Ending|Tax Period Requested)\s*:\s*(\d{2})-\d{2}-(\d{4})",
                       line, re.IGNORECASE)
        if m3:
            return f"{m3.group(2)}{m3.group(1)}"
    return ""


def _extract_form_number(lines: list[str]) -> str:
    """Return just the form token, e.g. '1040'."""
    for line in lines:
        m = re.search(r"FORM NUMBER\s*:\s*(\S+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_taxpayer_name(lines: list[str]) -> str:
    for line in lines:
        m = re.search(r"NAME\(S\)\s+SHOWN\s+ON\s+RETURN\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    # Account/RoA: name line follows the SPOUSE TIN line
    for i, line in enumerate(lines):
        if "SPOUSE TAXPAYER IDENTIFICATION" in line.upper():
            for j in range(i + 1, min(i + 5, len(lines))):
                cand = lines[j].strip()
                if cand and not cand.upper().startswith("TAXPAYER") and not re.match(r"^\d", cand):
                    return cand
    return ""


def _extract_tin(lines: list[str]) -> str:
    for line in lines:
        m = re.search(r"TAXPAYER IDENTIFICATION NUMBER\s*:\s*(\S+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"SSN\s+Provided\s*:\s*(\S+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        m = re.search(r"^\s*SSN\s*:\s*(\S+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_filing_status(lines: list[str]) -> str:
    for line in lines:
        m = re.search(r"FILING STATUS\s*:\s*(.+)", line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Return section (AGI, taxable income, tax per return, SE tax)
# ---------------------------------------------------------------------------

def _extract_return_section(lines: list[str]) -> dict:
    sec = {"agi": 0.0, "taxable_income": 0.0, "tax_per_return": 0.0, "se_tax": 0.0}
    block = "\n".join(lines)

    # Flags: MULTILINE so ^ matches line-start; IGNORECASE throughout
    FLAGS_ML = re.IGNORECASE | re.MULTILINE

    def g(pat: str, flags: int = re.IGNORECASE | re.DOTALL) -> float:
        m = re.search(pat, block, flags)
        return _parse_amount(m.group(1)) if m else 0.0

    # AGI — handle UPPERCASE (older e-services) and Mixed Case (2026+) layouts,
    # with optional "$" prefix on the amount.
    sec["agi"] = (
        g(r"ADJUSTED GROSS\s+INCOME\s*:\s*" + _AMT, re.IGNORECASE | re.DOTALL)
        or g(r"ADJUSTED GROSS INCOME\s*:\.+\s*" + _AMT, re.IGNORECASE)
    )

    # TAXABLE INCOME — must not match "SE TAXABLE INCOME"
    sec["taxable_income"] = (
        g(r"(?<!\w)TAXABLE INCOME\s*:\s*" + _AMT, FLAGS_ML)
        or g(r"(?<!\w)TAXABLE INCOME\s*:\.+\s*" + _AMT, FLAGS_ML)
    )

    # TAX PER RETURN (Account/RoA) or TOTAL TAX LIABILITY TP FIGURES (Return Transcript)
    sec["tax_per_return"] = (
        g(r"TAX PER RETURN\s*:\s*" + _AMT, re.IGNORECASE)
        or g(r"TOTAL TAX LIABILITY TP FIGURES\s*:\.+\s*" + _AMT, re.IGNORECASE)
    )

    # SE TAX
    sec["se_tax"] = (
        g(r"TOTAL SELF\s+EMPLOYMENT TAX\s*:\s*" + _AMT, re.IGNORECASE | re.DOTALL)
        or g(r"TOTAL SELF EMPLOYMENT TAX\s*:\s*" + _AMT, re.IGNORECASE)
        or g(r"SE TAX PER COMPUTER\s*:\.+\s*" + _AMT, re.IGNORECASE)
    )

    return sec


# ---------------------------------------------------------------------------
# Account summary
# ---------------------------------------------------------------------------

def _extract_account_summary(lines: list[str]) -> dict:
    summary = {"account_balance": 0.0, "accrued_interest": 0.0, "accrued_penalty": 0.0}
    # Anchor the amount capture to the FIRST colon after the specific label, so we
    # never pick up "As of: 05-11-2026" which appears after the amount on the same line.
    for line in lines:
        s = line.strip()
        if re.match(r"ACCOUNT BALANCE\s*:", s, re.IGNORECASE) and "PLUS" not in s.upper():
            m = re.search(r"^ACCOUNT BALANCE\s*:\s*" + _AMT, s, re.IGNORECASE)
            if m:
                summary["account_balance"] = _parse_amount(m.group(1))
        elif re.match(r"ACCRUED INTEREST\s*:", s, re.IGNORECASE):
            m = re.search(r"^ACCRUED INTEREST\s*:\s*" + _AMT, s, re.IGNORECASE)
            if m:
                summary["accrued_interest"] = _parse_amount(m.group(1))
        elif re.match(r"ACCRUED PENALTY\s*:", s, re.IGNORECASE):
            m = re.search(r"^ACCRUED PENALTY\s*:\s*" + _AMT, s, re.IGNORECASE)
            if m:
                summary["accrued_penalty"] = _parse_amount(m.group(1))
    return summary


# ---------------------------------------------------------------------------
# Transaction table parser
# ---------------------------------------------------------------------------
#
# Layout (pdftotext -layout, confirmed by character-position inspection):
#
#   Header: "CODE EXPLANATION OF TRANSACTION              CYCLE    DATE          AMOUNT"
#            0    5                                       45       54            ~73+
#
# Strategy: use a single regex per data line to capture all 5 fields atomically.
# This avoids any fragile column-slicing and correctly handles absent CYCLE columns.
#
#   TC line format:
#     <3-digit code>  <explanation text (2+ spaces gap)>  [CYCLE]  MM-DD-YYYY  [-]$N.NN
#
#   CYCLE is optional (8 consecutive digits, must be followed by space + date)

_TC_MAIN_RE = re.compile(
    r"^(\d{3})"                       # group 1: TC code
    r"\s{1,4}"                        # 1-4 spaces after code
    r"(.+?)"                          # group 2: explanation (non-greedy)
    r"\s{2,}"                         # 2+ space gap
    r"(?:(\d{8})\s+)?"                # group 3: CYCLE (8 digits, optional)
    r"(\d{2}-\d{2}-\d{4})"            # group 4: DATE mm-dd-yyyy
    r"\s+"
    r"(-?\$[\d,]+\.\d{2})\s*$"        # group 5: AMOUNT with dollar sign
)

# Zero-amount variant (the regex above requires an explicit $ amount but $0.00 may vary)
_TC_ZERO_RE = re.compile(
    r"^(\d{3})"
    r"\s{1,4}"
    r"(.+?)"
    r"\s{2,}"
    r"(?:(\d{8})\s+)?"
    r"(\d{2}-\d{2}-\d{4})"
    r"\s+"
    r"(\$0\.00)\s*$"
)


def _extract_transactions(lines: list[str]) -> list[dict]:
    """Parse the TRANSACTIONS table. Returns list of tc_transaction dicts."""

    # Locate the header line
    header_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if re.match(r"\s*CODE\s+EXPLANATION OF TRANSACTION", line, re.IGNORECASE):
            header_idx = i
            break
    if header_idx is None:
        return []

    transactions: list[dict] = []
    current: Optional[dict] = None

    for raw_line in lines[header_idx + 1:]:
        line = raw_line.rstrip()

        if "Sensitive Taxpayer Data" in line or "This Product Contains" in line:
            break

        if not line.strip():
            continue

        m = _TC_MAIN_RE.match(line) or _TC_ZERO_RE.match(line)

        if m:
            tc          = m.group(1)
            explanation = m.group(2).strip()
            cycle       = m.group(3) or ""
            iso_date    = _parse_date(m.group(4))
            amount      = _parse_amount(m.group(5))
            entry   = TC_CODES.get(tc, {})
            tc_desc = entry.get("short") or entry.get("description") or explanation

            current = {
                "tc":             tc,
                "explanation":    explanation,
                "cycle":          cycle,
                "date":           iso_date,
                "amount":         amount,
                "tc_description": tc_desc,
            }
            transactions.append(current)

        elif current is not None:
            continuation = line.strip()
            if not continuation:
                continue
            # Skip DLN reference lines (e.g., "80221-689-21191-1")
            if re.match(r"^\d{5}-\d{3}-\d{5}-\d", continuation):
                continue
            # Stop if we hit a new section header (e.g. RoA wage section start)
            if re.match(r"SSN Provided\s*:", continuation, re.IGNORECASE):
                break
            if re.match(r"Tax Period Ending\s*:", continuation, re.IGNORECASE):
                break
            if re.match(r"The following items reflect", continuation, re.IGNORECASE):
                break
            current["explanation"] += " " + continuation

    return transactions


def _build_tc_summary(transactions: list[dict]) -> dict:
    summary: dict[str, list] = defaultdict(list)
    for tx in transactions:
        summary[tx["tc"]].append({
            "date":   tx["date"],
            "amount": tx["amount"],
            "cycle":  tx["cycle"],
        })
    return dict(summary)


# ---------------------------------------------------------------------------
# Wage & Income items
# ---------------------------------------------------------------------------

# Information-return headings, in every layout the IRS Online Account has served:
#   legacy / Sept-2026:  "Form W-2 Wage and Tax Statement"      "Schedule K-1 1065"
#   Oct-2026 onward:     "Form W-2: Wage and Tax Statement"     "Schedule K-1 1065: Partner's Share of ..."
# The form token is matched explicitly so field lines such as "Form Number: 1040" or
# "Schedule K-3: Box checked" are never mistaken for a heading.
_WI_HEADING_RE = re.compile(
    r"^\s*(?P<code>Form\s+(?:W-?\d+[A-Z]?|\d{3,4}[A-Z]?(?:-[A-Z]{1,4})?)"
    r"|Schedule\s+K-1(?:\s+\(?\d{4}(?:-[A-Z]+)?\)?)?)"
    r"(?:\s*:\s*|\s+-\s+|\s+)?(?P<title>[A-Za-z][^:]*)?\s*$"
)
# "Label: value" with either dot leaders (legacy) or a run of spaces (2026 layouts).
_WI_FIELD_RE = re.compile(r"^\s*(?P<label>[^:]{2,90}?)\s*:(?:\.+|\s+)\s*(?P<value>\S.*?)\s*$")
_WI_ID_RE = re.compile(r"Identification Number(?:\s*\([^)]*\))?\s*$", re.IGNORECASE)
_WI_SKIP_LABELS = ("name", "name (cont.)", "street address", "street address (cont.)", "city, state and zip code")
_WI_NARRATIVE = ("reflect the amount", "adjusted", "following items", "do not show")


def _wi_form_code(code: str) -> str:
    """'Form W-2' -> 'W-2'; 'Form 1099-B' -> '1099-B'; 'Schedule K-1 1065' -> 'K-1 (1065)'."""
    code = re.sub(r"\s+", " ", code.strip())
    m = re.match(r"Schedule K-1(?: \(?(\d{4}(?:-[A-Z]+)?)\)?)?$", code)
    if m:
        return f"K-1 ({m.group(1)})" if m.group(1) else "K-1"
    return re.sub(r"^Form ", "", code)


def _extract_wage_income(lines: list[str], doc_type: str) -> list[dict]:
    """Extract W-2, 1099, 1098, 5498, Schedule K-1 and similar blocks from Wage & Income
    (and Record of Account) transcripts.

    Each item: form (normalised heading), form_code, ein (payer/filer/partnership id as
    shown — the IRS masks it), name (payer), recipient_name, recipient_tin,
    submission_type, and fields {label: value}. Dollar values are signed floats;
    indicator values ("Box checked", "Original") stay strings.
    """
    items: list[dict] = []
    if doc_type not in ("IRS-WageIncome-Transcript", "IRS-RecordOfAccount-Transcript"):
        return items

    in_wage_section = (doc_type == "IRS-WageIncome-Transcript")
    current: Optional[dict] = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # RoA: wage/return-section marker
        if re.match(r"SSN Provided\s*:", stripped, re.IGNORECASE):
            in_wage_section = True
        if not in_wage_section:
            continue
        if "Sensitive Taxpayer Data" in stripped or re.match(r"Page \d+/\d+$", stripped):
            continue

        m_head = _WI_HEADING_RE.match(line)
        if m_head:
            title = (m_head.group("title") or "").strip()
            if not any(n in title.lower() for n in _WI_NARRATIVE):
                if current:
                    items.append(current)
                code = re.sub(r"\s+", " ", m_head.group("code").strip())
                current = {
                    "form": f"{code} {title}".strip(),
                    "form_code": _wi_form_code(code),
                    "ein": "", "name": "", "recipient_name": "", "recipient_tin": "",
                    "submission_type": "", "fields": {},
                }
                continue

        if current is None:
            continue

        m_f = _WI_FIELD_RE.match(line)
        if not m_f:
            continue
        label, value = m_f.group("label").strip(), m_f.group("value").strip()
        low = label.lower()

        if _WI_ID_RE.search(label):
            if not current["ein"]:
                current["ein"] = value
            elif not current["recipient_tin"]:
                current["recipient_tin"] = value
            continue
        if low == "name":
            if not current["name"]:
                current["name"] = value
            elif not current["recipient_name"]:
                current["recipient_name"] = value
            continue
        if low in _WI_SKIP_LABELS:
            continue
        if low == "submission type":
            current["submission_type"] = value
            continue

        current["fields"][label] = (
            _parse_amount(value) if re.fullmatch(r"\(?-?\$?-?[\d,]+(?:\.\d+)?\)?", value) else value
        )

    if current:
        items.append(current)

    return items


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

EXAM_CODES   = {"420", "424"}
EXAM_ASSESS  = {"300"}
FREEZE_CODES = {"570", "520", "582"}


def _find_anomalies(transactions: list[dict], account_summary: dict) -> list[str]:
    anomalies: list[str] = []
    seen = {tx["tc"] for tx in transactions}

    for tc in EXAM_CODES:
        if tc in seen:
            anomalies.append(f"EXAM_INDICATOR: TC {tc} — {_tc_label(tc)}")
    for tc in EXAM_ASSESS:
        if tc in seen:
            anomalies.append(f"EXAM_ASSESSMENT: TC {tc} — {_tc_label(tc)}")
    for tc in FREEZE_CODES:
        if tc in seen:
            anomalies.append(f"FREEZE_INDICATOR: TC {tc} — {_tc_label(tc)}")
    if "977" in seen:
        anomalies.append("AMENDED_RETURN: TC 977 — Form 1040-X was filed")
    if "976" in seen:
        anomalies.append("DUPLICATE_RETURN: TC 976 — Duplicate return posted")
    if "846" in seen and account_summary.get("account_balance", 0) > 0:
        anomalies.append("BALANCE_AFTER_REFUND: Positive balance remains despite TC 846 refund issued")

    return anomalies


# ---------------------------------------------------------------------------
# Parsing utilities
# ---------------------------------------------------------------------------

def _parse_amount(s: str) -> float:
    """
    Convert IRS amount string to float.
    -$500.00  ($8,211.00)  $106,625.00  $0.00  $-85.00
    Parentheses or leading minus → negative (IRS credit convention).
    """
    if not s:
        return 0.0
    s = s.strip()
    negative = s.startswith("(") or s.startswith("-") or bool(re.match(r"^\$-", s))
    cleaned  = re.sub(r"[^\d.]", "", s)
    if not cleaned:
        return 0.0
    try:
        val = float(cleaned)
    except ValueError:
        return 0.0
    return -val if negative else val


_MON_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _parse_date(s: str) -> str:
    """Parse IRS date to ISO 8601 YYYY-MM-DD. Handles MM-DD-YYYY and Mon. DD, YYYY."""
    if not s:
        return ""
    s = s.strip()
    m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(1)}-{m.group(2)}"
    m2 = re.match(r"^(\w{3,})\.?\s*(\d{1,2}),?\s*(\d{4})$", s)
    if m2:
        return (
            f"{m2.group(3)}-"
            f"{_MON_MAP.get(m2.group(1)[:3].lower(), '00')}-"
            f"{m2.group(2).zfill(2)}"
        )
    return s


# ---------------------------------------------------------------------------
# CLI with confirmation flow
# ---------------------------------------------------------------------------

def _print_table(data: dict, out=sys.stdout) -> None:
    print("\n" + "=" * 72, file=out)
    print("  IRS Transcript Parser — Parsed Result", file=out)
    print("=" * 72, file=out)

    for label, key in [
        ("Document Type",  "doc_type"),
        ("Tax Period",     "tax_period"),
        ("Form Number",    "form_number"),
        ("Taxpayer Name",  "taxpayer_name"),
        ("Taxpayer TIN",   "taxpayer_tin"),
        ("Filing Status",  "filing_status"),
    ]:
        print(f"  {label:<22} {data.get(key, '')}", file=out)

    rs = data.get("return_section", {})
    print("\n  Return Section:", file=out)
    for label, key in [("AGI", "agi"), ("Taxable Income", "taxable_income"),
                       ("Tax per Return", "tax_per_return"), ("SE Tax", "se_tax")]:
        print(f"    {label:<32} ${rs.get(key, 0):>15,.2f}", file=out)

    acct = data.get("account_summary", {})
    print("\n  Account Summary:", file=out)
    for label, key in [("Balance", "account_balance"), ("Accrued Interest", "accrued_interest"),
                       ("Accrued Penalty", "accrued_penalty")]:
        print(f"    {label:<32} ${acct.get(key, 0):>15,.2f}", file=out)

    tcs = data.get("tc_transactions", [])
    print(f"\n  Transactions ({len(tcs)} records):", file=out)
    for tx in tcs:
        amt  = tx.get("amount", 0.0)
        sign = "-" if amt < 0 else " "
        print(f"    TC {tx['tc']:3s}  {tx['date']:<12}  {sign}${abs(amt):>12,.2f}  {tx['explanation'][:46]}", file=out)

    anomalies = data.get("anomalies", [])
    if anomalies:
        print(f"\n  *** ANOMALIES / FLAGS ({len(anomalies)}) ***", file=out)
        for a in anomalies:
            print(f"    ! {a}", file=out)

    wi = data.get("wage_income_items", [])
    if wi:
        print(f"\n  Wage/Income Items ({len(wi)} information returns):", file=out)
        for item in wi:
            print(f"    {item.get('form_code') or item.get('form', ''):<12} {item.get('name', '')[:28]:<28}  ID: {item.get('ein', '')}", file=out)

    print("=" * 72 + "\n", file=out)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 transcript_parser.py <path/to/transcript.pdf>", file=sys.stderr)
        print("       python3 transcript_parser.py <path/to/transcript.pdf> --json", file=sys.stderr)
        print("       python3 transcript_parser.py <path/to/transcript.txt>  --json  (pre-extracted text)", file=sys.stderr)
        return 1

    input_path       = sys.argv[1]
    output_json_flag = "--json" in sys.argv

    try:
        # Auto-detect: .txt/.text files are already pdftotext output — parse directly
        # without calling pdftotext again.
        if Path(input_path).suffix.lower() in (".txt", ".text"):
            raw_text = Path(input_path).read_text(encoding="utf-8", errors="replace")
            data = _parse_text(raw_text, input_path)
        else:
            data = parse_transcript(input_path)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if output_json_flag:
        # Keep stdout pure JSON when --json is set; human table goes to stderr.
        _print_table(data, out=sys.stderr)
        print(json.dumps(data, indent=2))
        return 0

    _print_table(data)

    # Interactive confirmation flow
    while True:
        try:
            choice = input("  Action — [y] write JSON  [s] skip  [p] print JSON : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  Skipped.")
            return 0

        if choice in ("y", "yes"):
            out_path = Path(input_path).with_suffix(".parsed.json")
            out_path.write_text(json.dumps(data, indent=2))
            print(f"  Written: {out_path}")
            break
        elif choice in ("s", "skip", ""):
            print("  Skipped — no file written.")
            break
        elif choice in ("p", "print"):
            print(json.dumps(data, indent=2))
        else:
            print("  Enter y / s / p")

    return 0


if __name__ == "__main__":
    sys.exit(main())

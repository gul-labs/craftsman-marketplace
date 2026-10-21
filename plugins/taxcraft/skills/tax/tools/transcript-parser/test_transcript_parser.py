#!/usr/bin/env python3
"""
Self-test for transcript_parser.

Runs on the synthetic text fixtures in samples/ (no PDF, no poppler needed) and
proves two things for every transcript layout the IRS Online Account has served:

  1. Information returns are found — W-2, 1099-B, 1099-INT and Schedule K-1 blocks
     in the legacy dot-leader layout, the plain-heading 2026 layout, and the
     colon-heading layout introduced in October 2026.
  2. Signs survive — a credit balance ("-$12,000.00") and K-1 losses ("-$997.00")
     parse negative, not as 0 or positive.

    python3 test_transcript_parser.py        # exit 0 = all pass
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from transcript_parser import _parse_amount, _parse_text  # noqa: E402

FAILURES: list[str] = []


def expect(cond: bool, label: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILURES.append(label)


def parse(name: str) -> dict:
    return _parse_text((HERE / "samples" / name).read_text(), name)


def by_code(items: list[dict], code: str) -> list[dict]:
    return [i for i in items if i["form_code"] == code]


print("amount parsing")
for raw, want in [("-$20,000.00", -20000.0), ("$-85.00", -85.0), ("($8,211.00)", -8211.0),
                  ("$1,234.56", 1234.56), ("1,637.54", 1637.54), ("$0.00", 0.0)]:
    expect(_parse_amount(raw) == want, f"_parse_amount({raw!r}) == {want}")

print("account transcript with a credit balance (2026 mixed-case layout)")
d = parse("sample-account-credit-balance.txt")
expect(d["doc_type"] == "IRS-Account-Transcript", "doc_type")
expect(d["tax_period"] == "202412", "tax_period from 'Report for Tax Period Ending: 12-31-2024'")
expect(d["account_summary"]["account_balance"] == -12000.0, "credit balance stays negative (-12,000)")
expect(d["account_summary"]["accrued_interest"] == 0.0, "accrued interest ignores the 'As of' date")
expect(d["return_section"]["agi"] == 210000.0, "AGI")
expect(d["return_section"]["tax_per_return"] == 31500.0, "tax per return")
expect([t["tc"] for t in d["tc_transactions"]] == ["150", "806", "846", "670", "570"], "five TC lines in order")
expect(any(a.startswith("FREEZE_INDICATOR: TC 570") for a in d["anomalies"]), "TC 570 freeze flagged")
expect(not any(a.startswith("BALANCE_AFTER_REFUND") for a in d["anomalies"]), "credit balance is not a balance due")

print("wage & income — October 2026 colon-heading layout")
d = parse("sample-wage-income-2026-colon-layout.txt")
wi = d["wage_income_items"]
expect(d["doc_type"] == "IRS-WageIncome-Transcript", "doc_type")
expect(d["tax_period"] == "202512", "tax_period from 'Tax Period Requested: 12-31-2025'")
expect([i["form_code"] for i in wi] == ["W-2", "1099-B", "K-1 (1065)"], "three blocks: W-2, 1099-B, K-1 (1065)")
w2 = by_code(wi, "W-2")[0]
expect(w2["fields"].get("Wages, Tips and Other Compensation") == 12500.0, "W-2 wages")
expect(w2["fields"].get("Federal Income Tax Withheld") == 1100.0, "W-2 withholding")
expect(w2["name"] == "SAMP EMPL" and w2["recipient_name"] == "SAMP TA", "payer and recipient names separated")
expect(w2["ein"] == "XXXXX0001" and w2["recipient_tin"] == "XXX-XX-1234", "payer id and recipient TIN separated")
expect(w2["submission_type"] == "Original document", "submission type")
expect(w2["fields"].get("Retirement Plan Indicator") == "Yes - retirement plan", "indicator kept as text")
expect("Street Address" not in w2["fields"] and "Name" not in w2["fields"], "address lines not copied into fields")
b = by_code(wi, "1099-B")[0]
expect(b["fields"].get("Proceeds") == 10000.0 and b["fields"].get("Cost or Basis") == 8000.0, "1099-B proceeds and basis")
expect(b["ein"] == "XXXXX0002", "1099-B payer FIN")
k1 = by_code(wi, "K-1 (1065)")[0]
expect(k1["name"] == "SAMP FUN LP", "K-1 partnership name")
expect(k1["fields"].get("Ordinary Business Income (loss)") == -997.0, "K-1 ordinary loss negative")
expect(k1["fields"].get("Real Estate") == -3250.0, "K-1 rental loss negative")
expect(k1["fields"].get("Interest") == 64.0, "K-1 interest")
expect(k1["fields"].get("Schedule K-3") == "Box checked", "'Schedule K-3: Box checked' is a field, not a heading")

print("wage & income — September 2026 plain-heading layout")
d = parse("sample-wage-income-2026-plain-layout.txt")
wi = d["wage_income_items"]
expect(d["tax_period"] == "202512", "tax_period from 'December, 2025'")
expect([i["form_code"] for i in wi] == ["W-2", "K-1 (1065)"], "two blocks: W-2, K-1 (1065)")
expect(by_code(wi, "W-2")[0]["fields"].get("Wages, Tips and Other Compensation") == 12500.0, "values without dot leaders")
k1 = by_code(wi, "K-1 (1065)")[0]
expect(k1["ein"] == "XXXXX0003", "EIN label without '(EIN)'")
expect(k1["submission_type"] == "Amended document", "amended K-1 recognised")
expect(k1["fields"].get("Ordinary Income K-1") == -997.0, "legacy K-1 label, negative")

print("wage & income — legacy dot-leader layout")
d = parse("sample-wage-income-legacy-dotleader.txt")
wi = d["wage_income_items"]
expect([i["form_code"] for i in wi] == ["W-2", "1099-INT"], "two blocks: W-2, 1099-INT")
expect(by_code(wi, "W-2")[0]["fields"].get("Wages, Tips and Other Compensation") == 95000.0, "dot-leader wages")
expect(by_code(wi, "1099-INT")[0]["fields"].get("Interest") == 412.0, "dot-leader interest")

print("existing samples unchanged")
d = parse("sample-account-transcript.txt")
expect(d["account_summary"]["account_balance"] == 1637.54, "positive balance without '$'")
expect(d["return_section"]["agi"] == 225000.0, "uppercase AGI")
expect(d["tax_period"] == "202212", "'Dec. 31, 2022' tax period")
expect(len(d["tc_transactions"]) == 7, "seven TC lines")
d = parse("sample-with-exam-flags.txt")
expect(any(a.startswith("EXAM_") for a in d["anomalies"]), "exam flags still raised")

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED")
    sys.exit(1)
print("all passed")

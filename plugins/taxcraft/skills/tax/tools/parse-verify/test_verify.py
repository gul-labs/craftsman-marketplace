#!/usr/bin/env python3
"""
Self-test for parse-verify.

Two things are being proven here, and the second matters more than the first:

  1. Each invariant FIRES on a document that violates it.
  2. Each invariant STAYS SILENT on a document that satisfies it — including
     the cases that superficially resemble a violation.

A validator that flags everything is as useless as one that flags nothing.
The discriminating cases below (both sign conventions; a legitimately huge
basis worksheet explained by debt share) are the ones worth guarding.

    python3 test_verify.py        # exit 0 = all pass
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pdf-extractor"))

import envelope  # noqa: E402
from verify import check_1065, check_cross, check_k1, verify_docs  # noqa: E402

FAILURES: list[str] = []


def expect(cond: bool, label: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILURES.append(label)


def ids(findings) -> set[str]:
    return {f.check for f in findings}


# --------------------------------------------------------------------------
print("Item L rollforward — both sign conventions must reconcile")

# Withdrawals stored as a signed negative (Harris Villas shape).
signed_convention = {
    "doc_type": "K-1-1065", "box_2_rental_re": -4168,
    "part_ii_item_l": {"beginning": 58192, "contributions": 0,
                       "current_year_net_income": -4168, "withdrawals": -8022,
                       "other_increases": 0, "other_decreases": -2015, "ending": 43987},
    "part_ii_item_k": {"nonrecourse_beginning": 981, "qnr_beginning": 111073,
                       "recourse_beginning": 651},
}
expect("K1.item_l.rollforward" not in ids(check_k1(signed_convention, "signed")),
       "signed-negative withdrawals reconcile")

# Withdrawals stored as a positive magnitude (CAPE shape). A validator that
# only understands the convention above reports a false break here.
magnitude_convention = {
    "doc_type": "K-1-1065", "box_2_rental_re": -24168,
    "part_ii_item_l": {"beginning": 50000, "contributions": 0,
                       "current_year_net_income": -24168, "withdrawals": 500,
                       "other_increases": 0, "other_decreases": 0, "ending": 25332},
    "part_ii_item_k": {"nonrecourse": 66189},
}
expect("K1.item_l.rollforward" not in ids(check_k1(magnitude_convention, "magnitude")),
       "positive-magnitude withdrawals reconcile")

broken = {
    "doc_type": "K-1-1065", "box_2_rental_re": -4168,
    "part_ii_item_l": {"beginning": 58192, "contributions": 0,
                       "current_year_net_income": -4168, "withdrawals": -8022,
                       "other_increases": 0, "other_decreases": -2015, "ending": 99999},
    "part_ii_item_k": {"nonrecourse": 500000},
}
expect("K1.item_l.rollforward" in ids(check_k1(broken, "broken")),
       "a genuine rollforward break is caught")

# --------------------------------------------------------------------------
print("\nItem L blank while the K-1 allocates activity")

blank = {
    "doc_type": "K-1-1065", "box_2_rental_re": -7540, "box_5_interest": 281,
    "part_ii_item_l": {"beginning": 0, "contributions": 0, "current_year_net_income": 0,
                       "withdrawals": 0, "other_increases": 0, "other_decreases": 0, "ending": 0},
    "part_ii_item_k": {"nonrecourse": 0, "qnr": 0, "recourse": 0},
}
expect("K1.item_l.blank" in ids(check_k1(blank, "blank")), "blank Item L with activity is flagged")

# A K-1 with no activity and no capital is empty, not defective.
quiet = {"doc_type": "K-1-1065",
         "part_ii_item_l": {"beginning": 0, "contributions": 0, "current_year_net_income": 0,
                            "withdrawals": 0, "other_increases": 0, "other_decreases": 0, "ending": 0}}
expect("K1.item_l.blank" not in ids(check_k1(quiet, "quiet")),
       "blank Item L with no activity is not flagged")

# --------------------------------------------------------------------------
print("\n§704(d) — loss allowed only to the extent of outside basis")

# Item L reports real zeros, so basis genuinely IS zero — assert the violation.
zero_basis = {
    "doc_type": "K-1-1065", "box_2_rental_re": -7540,
    "part_ii_item_l": {"beginning": 0, "contributions": 0, "current_year_net_income": -7540,
                       "withdrawals": 0, "other_increases": 0, "other_decreases": 0,
                       "ending": -7540},
    "part_ii_item_k": {"nonrecourse": 0, "qnr": 0, "recourse": 0},
}
expect("K1.704d.loss_exceeds_basis" in ids(check_k1(zero_basis, "zero")),
       "loss exceeding a KNOWN zero basis is flagged as a violation")

# Item L is blank, so basis is unknown. Claiming a §704(d) violation here
# would assert something the document cannot support.
expect("K1.704d.basis_undeterminable" in ids(check_k1(blank, "blank")),
       "loss with an unpopulated Item L is flagged as undeterminable, not as a violation")
expect("K1.704d.loss_exceeds_basis" not in ids(check_k1(blank, "blank")),
       "an unpopulated Item L does not assert a §704(d) violation")

expect("K1.704d.loss_exceeds_basis" not in ids(check_k1(magnitude_convention, "cape")),
       "loss covered by capital + debt share is not flagged")

# Item K nested as {"beginning": {...}, "ending": {...}} must still be read.
nested_k = {
    "doc_type": "K-1-1065", "box_2_rental_re": -5000,
    "part_ii_item_l": {"beginning": 1000, "contributions": 0, "current_year_net_income": -5000,
                       "withdrawals": 0, "other_increases": 0, "other_decreases": 0,
                       "ending": -4000},
    "part_ii_item_k": {"beginning": {"nonrecourse": 40000, "qnr": 0, "recourse": 0},
                       "ending": {"nonrecourse": 40000, "qnr": 0, "recourse": 0}},
}
expect("K1.704d.loss_exceeds_basis" not in ids(check_k1(nested_k, "nested")),
       "nested Item K liability shape is read, not silently treated as zero")

# --------------------------------------------------------------------------
print("\nBasis worksheet vs capital + liability share")

# Legitimately large: the gap IS the debt share, and it ties (a leveraged real-estate position).
explained = {
    "doc_type": "K-1-1065", "box_1_ordinary": -700,
    "part_ii_item_l": {"beginning": 50000, "contributions": 0,
                       "current_year_net_income": -24290, "withdrawals": 0,
                       "other_increases": 0, "other_decreases": 0, "ending": 25710},
    "part_ii_item_k": {"nonrecourse": 2884, "qnr": 105422, "recourse": 273},
    "basis_worksheet": {"end_of_year": 134289},
}
expect("K1.basis_worksheet.unexplained" not in ids(check_k1(explained, "explained")),
       "large basis explained by debt share is not flagged")

unexplained = dict(magnitude_convention, basis_worksheet_end_of_year=19876049)
expect("K1.basis_worksheet.unexplained" in ids(check_k1(unexplained, "unexplained")),
       "basis that capital + debt cannot explain is flagged")

# --------------------------------------------------------------------------
print("\nGuaranteed payments vs distributions")

swapped = {"doc_type": "K-1-1065", "box_4c_gp_total": 12000, "box_19_distributions": 12000}
expect("K1.gp_equals_distribution" in ids(check_k1(swapped, "swapped")),
       "identical GP and distributions are flagged")
distinct = {"doc_type": "K-1-1065", "box_4c_gp_total": 12000, "box_19_distributions": 8000}
expect("K1.gp_equals_distribution" not in ids(check_k1(distinct, "distinct")),
       "distinct GP and distributions are not flagged")

# --------------------------------------------------------------------------
print("\n§199A statement")

# Regression: FY2023 files spell these `qbi_ordinary_income_loss` /
# `qbi_rental_income_loss`, and the two are COMPONENTS to be summed. An
# alias list that misses them reads zero and flags a healthy K-1.
verbose_spelling = {
    "doc_type": "K-1-1065", "box_1_ordinary": -37960, "box_2_rental_re": 0,
    "statement_a_199a": [{"trade_or_business": "X", "qbi_ordinary_income_loss": -37960,
                          "qbi_rental_income_loss": 0, "w2_wages": 18795,
                          "ubia_qualified_property": 118078}],
}
expect("K1.199a.zeroed" not in ids(check_k1(verbose_spelling, "verbose")),
       "long-form qbi_*_income_loss spelling is read, not treated as zero")

split_components = {
    "doc_type": "K-1-1065", "box_1_ordinary": -700, "box_2_rental_re": -23562,
    "statement_a_199a": [{"qbi_ordinary": -700, "qbi_rental": -23562}],
}
expect("K1.199a.zeroed" not in ids(check_k1(split_components, "split")),
       "ordinary and rental QBI are summed, not chosen between")

genuinely_zeroed = {
    "doc_type": "K-1-1065", "box_2_rental_re": -235903,
    "statement_a_199a": [{"qbi_ordinary_income_loss": 0, "qbi_rental_income_loss": 0,
                          "w2_wages": 0, "ubia_qualified_property": 0}],
}
expect("K1.199a.zeroed" in ids(check_k1(genuinely_zeroed, "zeroed")),
       "a genuinely zeroed §199A pass-through is still flagged")

# --------------------------------------------------------------------------
print("\nSchedule L / M-2")

imbalanced = {"doc_type": "1065-Return",
              "schedule_l": {"ending": {"total_assets": 100, "total_liab": 10,
                                        "partners_capital": 50}}}
expect("1065.schedule_l.imbalance" in ids(check_1065(imbalanced, "sl")),
       "an unbalanced Schedule L is flagged")

balanced = {"doc_type": "1065-Return",
            "schedule_l": {"ending": {"total_assets": 263342, "total_liab": 0,
                                      "partners_capital": 263342}},
            "schedule_m2": {"beginning": 61752, "contributions": 330000, "net_income": -128410,
                            "other_increases": 0, "distributions_cash": 0,
                            "distributions_property": 0, "other_decreases": 0,
                            "ending": 263342}}
expect(not ({"1065.schedule_l.imbalance", "1065.m2.rollforward", "1065.m2_vs_schedule_l"}
            & ids(check_1065(balanced, "ok"))),
       "a balanced return with a tying M-2 is silent")

drifted = dict(balanced, schedule_m2=dict(balanced["schedule_m2"], ending=999999))
expect("1065.m2.rollforward" in ids(check_1065(drifted, "drift")),
       "an M-2 that does not roll forward is flagged")

# --------------------------------------------------------------------------
print("\nCross-document — Schedule K must equal the sum of issued K-1s")

ret = {"doc_type": "1065-Return", "tax_year": 2024,
       "schedule_k": {"line_1_ordinary": -700, "line_2_rental_re": -128907,
                      "line_18c_nondeductible_expenses": 0}}
p1 = {"doc_type": "K-1-1065", "direction": "issued", "tax_year": 2024,
      "box_1_ordinary": -350, "box_2_rental_re": -64453, "pct_capital_end": 50.0}
p2 = {"doc_type": "K-1-1065", "direction": "issued", "tax_year": 2024,
      "box_1_ordinary": -350, "box_2_rental_re": -64454, "pct_capital_end": 50.0}
expect("cross.k_vs_k1_sum" not in ids(check_cross({"r": ret, "a": p1, "b": p2})),
       "K-1s that foot to Schedule K are not flagged")

p2_bad = dict(p2, box_1_ordinary=-1000)
expect("cross.k_vs_k1_sum" in ids(check_cross({"r": ret, "a": p1, "b": p2_bad})),
       "K-1s that do not foot to Schedule K are flagged")

expect("cross.ownership_sum" in ids(check_cross({"r": ret, "a": p1,
                                                 "b": dict(p2, pct_capital_end=30.0)})),
       "ownership percentages not totalling 100% are flagged")

# Received nondeductible expenses that never reach Schedule K line 18c.
r1 = {"doc_type": "K-1-1065", "direction": "received", "tax_year": 2024,
      "box_18_nondeductible_c": 215}
r2 = {"doc_type": "K-1-1065", "direction": "received", "tax_year": 2024,
      "box_18_nondeductible_c": 1}
expect("cross.nondeductible_passthrough" in ids(
           check_cross({"r": ret, "a": p1, "b": p2, "x": r1, "y": r2})),
       "nondeductible expenses lost in a tier are flagged")

ret_ok = {**ret, "schedule_k": dict(ret["schedule_k"], line_18c_nondeductible_expenses=216)}
expect("cross.nondeductible_passthrough" not in ids(
           check_cross({"r": ret_ok, "a": p1, "b": p2, "x": r1, "y": r2})),
       "nondeductible expenses correctly passed through are not flagged")

# --------------------------------------------------------------------------
print("\nSchema-2 envelopes verify identically to legacy flat documents")


def envelope_ize(doc):
    """Wrap every scalar (nested dicts included) in an OBSERVED envelope.

    This is the shape `k1_parser.py --merge` and `form_parser.py` emit. A
    verifier that reads `.value` only on the paths it happens to remember
    passes the flat corpus and silently reports nothing on the new one.
    """
    if isinstance(doc, dict):
        return {k: envelope_ize(v) for k, v in doc.items()}
    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        return envelope.make(float(doc))
    if isinstance(doc, str):
        return envelope.make(doc)
    return doc


for label, flat in (("signed", signed_convention), ("broken", broken),
                    ("zero basis", zero_basis), ("swapped GP", swapped),
                    ("blank Item L", blank)):
    wrapped = dict(envelope_ize(flat), doc_type=flat["doc_type"], schema_version=2)
    expect(ids(check_k1(wrapped, "env")) == ids(check_k1(flat, "flat")),
           f"envelope K-1 ({label}) yields exactly the flat K-1's findings")

# --------------------------------------------------------------------------
print("\nMissing is not zero — an unobserved input skips its check")

not_present_capital = dict(envelope_ize(signed_convention), doc_type="K-1-1065", schema_version=2)
not_present_capital["part_ii_item_l"] = dict(not_present_capital["part_ii_item_l"],
                                             ending=envelope.make(None))
np_ids = ids(check_k1(not_present_capital, "np"))
expect("K1.item_l.rollforward.not_evaluable" in np_ids,
       "a NOT_PRESENT capital-account field skips the rollforward with an INFO finding")
expect("K1.item_l.rollforward" not in np_ids,
       "the skipped rollforward is not reported as a break against a substituted zero")
expect(all(f.severity == "INFO" for f in check_k1(not_present_capital, "np")
           if f.check.endswith(".not_evaluable")),
       "not_evaluable findings are INFO, never a failure")

# An UNREADABLE liability share must not be read as a zero basis either.
unreadable_debt = dict(envelope_ize(zero_basis), doc_type="K-1-1065", schema_version=2)
unreadable_debt["part_ii_item_k"] = {"nonrecourse": envelope.make(None, "UNREADABLE"),
                                     "qnr": envelope.make(0.0), "recourse": envelope.make(0.0)}
ud_ids = ids(check_k1(unreadable_debt, "unreadable"))
expect("K1.704d.loss_exceeds_basis" not in ud_ids,
       "an unreadable liability share does not assert a §704(d) violation")
expect("K1.704d.loss_exceeds_basis.not_evaluable" in ud_ids,
       "an unreadable liability share is reported as not evaluable")

# --------------------------------------------------------------------------
print("\nRegistry doc types are routed to the declarative invariants")


def w2_doc(box_4: float) -> dict:
    """A schema-2 W-2. tax_year 2025 so `rules/federal-2025.json` loads and the
    rate invariants can evaluate at all."""
    env = envelope.make
    return {
        "doc_type": "W-2", "schema_version": 2, "tax_year": 2025,
        "identity": {"employee_ssn": env("123-45-6789"), "employer_ein": env("91-1234567"),
                     "employer_name": env("ACME HOLDINGS LLC"), "employee_name": env("PAT DOE")},
        "boxes": {"box_1": env(100000.0), "box_2": env(14000.0), "box_3": env(100000.0),
                  "box_4": env(box_4), "box_5": env(100000.0), "box_6": env(1450.0),
                  "box_12": env([]), "box_16": env(100000.0), "box_17": env(5000.0),
                  "box_18": env(100000.0), "box_19": env(1500.0)},
    }


consistent = verify_docs({"w2.json": w2_doc(6200.0)})
expect(not [f for f in consistent if f.severity != "INFO"],
       "a consistent W-2 produces nothing at or above MEDIUM")

ten_x = verify_docs({"w2.json": w2_doc(62000.0)})
expect("W2.box4_ss_rate" in ids(ten_x),
       "a W-2 whose box 4 is 10x the 6.2% rate is flagged through the registry invariants")
expect(all(f.severity == "HIGH" for f in ten_x if f.check == "W2.box4_ss_rate"),
       "the registry severity (HIGH) survives the conversion to a Finding")

# --------------------------------------------------------------------------
print("\nDuplicate W-2s across two files")

dup = verify_docs({"w2-copy-b.json": w2_doc(6200.0), "w2-copy-2.json": w2_doc(6200.0)})
expect("W2.duplicate" in ids(dup), "the same W-2 saved twice is flagged")

other_employer = w2_doc(6200.0)
other_employer["identity"] = dict(other_employer["identity"],
                                  employer_ein=envelope.make("91-7654321"))
expect("W2.duplicate" not in ids(verify_docs({"a.json": w2_doc(6200.0), "b.json": other_employer})),
       "two W-2s from different employers are not flagged as duplicates")

# --------------------------------------------------------------------------
print("\nWhat the extractor said about its own read")

disputed = w2_doc(6200.0)
disputed["_extraction"] = {"engines": ["text", "vision"], "merged": True,
                           "review_required": ["boxes.box_2"],
                           "quality": {"verdict": "suspect", "reasons": ["dictionary hit ratio 0.07 is low"]}}
ext = verify_docs({"w2.json": disputed})
review = [f for f in ext if f.check == "EXTRACTION.review_required"]
expect(len(review) == 1 and review[0].severity == "MEDIUM",
       "a field the engines disagreed on is a MEDIUM finding")
suspect = [f for f in ext if f.check == "EXTRACTION.text_suspect"]
expect(len(suspect) == 1 and suspect[0].severity == "INFO",
       "suspect text quality is surfaced at INFO")
expect(not [f for f in verify_docs({"w2.json": w2_doc(6200.0)})
            if f.check.startswith("EXTRACTION.")],
       "a document with no _extraction block produces no extraction findings")

# --------------------------------------------------------------------------
print()
if FAILURES:
    print(f"{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("All checks pass.")

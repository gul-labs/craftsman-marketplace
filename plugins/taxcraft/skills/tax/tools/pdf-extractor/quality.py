#!/usr/bin/env python3
"""
quality — is this extracted text real, and which form is it?

The old gate ("more than 50 characters, more than 5 characters per KB") passed
gibberish: a PDF whose fonts carry no ToUnicode map makes `pdftotext` emit
`(cid:37)(cid:12)` tokens or symbol soup, which is long, dense, and worthless.
The downstream regexes then found nothing and returned zeros, silently.

This module scores extracted text on signals that gibberish cannot fake:
printable ratio, share of `(cid:N)` tokens, share of alphabetic tokens that are
ordinary English or tax-form vocabulary, and (when the PDF is at hand) whether
`pdffonts` reports fonts without a ToUnicode map. It also detects the document
type from anchor phrases so the caller can pick a parser and a vision skeleton.

Verdicts:
    ok       — parse it
    suspect  — parse it, but a vision pass is mandatory as the cross-check
    garbage  — do not parse; go straight to the vision rung

Pure stdlib. Never raises on odd input. Never modifies anything.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "form-parser"))
try:
    from doc_types import REGISTRY  # type: ignore
except Exception:  # pragma: no cover - registry missing only in a broken install
    REGISTRY = {}

# Words that appear on nearly every US tax form or in ordinary English prose.
# The list is deliberately small: it only needs to separate real text (hit
# ratio well above 0.1) from symbol soup (hit ratio near 0).
_VOCAB = set("""
the and for from with this that you your are was were not any all per each
total amount income tax taxes federal state local city name address employer
employee payer recipient wages tips other compensation withheld withholding
social security medicare box copy form schedule year statement information
interest dividends distributions proceeds basis cost gain loss capital
ordinary qualified rental royalties partner partnership shareholder beneficiary
share deductions credits contributions rollover mortgage principal points
insurance premiums tuition scholarships student loan benefits paid repaid
gross net taxable nontaxable exempt code codes number account identification
control department treasury internal revenue service instructions attach
return page part line item beginning ending during current prior final
amended corrected void date issued printed report reported reportable
description quantity shares sold acquired covered noncovered wash sale
disallowed market discount premium bond treasury foreign country
allocated dependent care nonqualified plans statutory retirement plan third
party sick pay locality wages guaranteed payments liabilities recourse
nonrecourse capital contributed withdrawals distributions self employment
earnings section deductible portion unemployment refund grants agriculture
card third network transactions monthly advance credit enrollment premium
coverage marketplace policy annual totals january february march april may
june july august september october november december
""".split())

_CID_RE = re.compile(r"\(cid:\d+\)")
_WORD_RE = re.compile(r"[A-Za-z]{3,}")
_MONEY_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+\.\d{2}")


@dataclass
class QualityReport:
    verdict: str = "ok"                     # ok | suspect | garbage
    reasons: list[str] = field(default_factory=list)
    chars: int = 0
    printable_ratio: float = 1.0
    cid_token_ratio: float = 0.0
    alpha_tokens: int = 0
    dictionary_hit_ratio: float = 0.0
    replacement_chars: int = 0
    money_tokens: int = 0
    fonts_total: Optional[int] = None
    fonts_without_tounicode: Optional[int] = None
    detected_doc_type: Optional[str] = None
    anchor_hits: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Font inspection
# --------------------------------------------------------------------------

def font_report(pdf_path: Path) -> tuple[Optional[int], Optional[int]]:
    """(total fonts, fonts without a ToUnicode map) via `pdffonts`, or (None, None)."""
    if not shutil.which("pdffonts"):
        return None, None
    try:
        proc = subprocess.run(["pdffonts", str(pdf_path)], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if proc.returncode != 0:
        return None, None
    lines = proc.stdout.splitlines()
    # header, dashes, then one row per font; the `uni` column is the 5th from
    # the right in poppler's layout, but column positions shift with long names,
    # so locate it from the header instead.
    if len(lines) < 2:
        return 0, 0
    header = lines[0]
    uni_col = header.find("uni")
    if uni_col < 0:
        return None, None
    total = 0
    missing = 0
    for row in lines[2:]:
        if not row.strip():
            continue
        total += 1
        cell = row[uni_col:uni_col + 3].strip().lower()
        if cell == "no":
            missing += 1
    return total, missing


# --------------------------------------------------------------------------
# Doc-type detection by anchors
# --------------------------------------------------------------------------

def detect_doc_type(text: str) -> tuple[Optional[str], dict[str, int]]:
    """Score every registry doc type by anchor hits; return (best, all_hits).

    Anchors are regexes; a hit counts once per anchor. Ties are broken toward
    the type with more *specific* anchors (a longer anchor list), then by
    registry order. Returns (None, hits) when nothing matched.
    """
    hits: dict[str, int] = {}
    flat = " ".join(text.split())
    for name, spec in REGISTRY.items():
        n = 0
        for pat in spec.anchors:
            if re.search(pat, flat, re.IGNORECASE):
                n += 1
        if n:
            hits[name] = n
    if not hits:
        return None, hits
    # Prefer types whose anchors are *all* present; among those, the most anchors.
    def key(item):
        name, n = item
        total = len(REGISTRY[name].anchors)
        return (n == total, n / total, n)
    best = max(hits.items(), key=key)[0]
    # A composite brokerage statement matches INT, DIV and B at once.
    if {"1099-INT", "1099-DIV", "1099-B"} <= set(hits) and "1099-Composite" in REGISTRY:
        best = "1099-Composite"
    return best, hits


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def assess(text: str, *, doc_hint: Optional[str] = None, pdf_path: Optional[Path] = None) -> QualityReport:
    r = QualityReport()
    text = text or ""
    r.chars = len(text)
    if r.chars == 0:
        r.verdict = "garbage"
        r.reasons.append("no text extracted")
        return r

    printable = sum(1 for c in text if c.isprintable() or c in "\n\t\r")
    r.printable_ratio = printable / r.chars
    r.replacement_chars = text.count("�")

    cid_tokens = len(_CID_RE.findall(text))
    words = _WORD_RE.findall(text)
    r.alpha_tokens = len(words)
    denom = max(1, len(words) + cid_tokens)
    r.cid_token_ratio = cid_tokens / denom
    if words:
        hits = sum(1 for w in words if w.lower() in _VOCAB)
        r.dictionary_hit_ratio = hits / len(words)
    r.money_tokens = len(_MONEY_RE.findall(text))

    if pdf_path is not None:
        r.fonts_total, r.fonts_without_tounicode = font_report(Path(pdf_path))

    r.detected_doc_type, r.anchor_hits = detect_doc_type(text)

    # ---- verdict --------------------------------------------------------
    garbage = []
    suspect = []

    if r.printable_ratio < 0.90:
        garbage.append(f"printable ratio {r.printable_ratio:.2f} < 0.90")
    if r.cid_token_ratio > 0.10:
        garbage.append(f"{r.cid_token_ratio:.0%} of tokens are (cid:N) — fonts have no ToUnicode map")
    if r.alpha_tokens >= 20 and r.dictionary_hit_ratio < 0.04:
        garbage.append(f"dictionary hit ratio {r.dictionary_hit_ratio:.2f} — text is not language")
    if r.alpha_tokens < 5:
        garbage.append(f"only {r.alpha_tokens} alphabetic tokens — image-only or empty page")

    if r.replacement_chars and r.replacement_chars / r.chars > 0.02:
        suspect.append(f"{r.replacement_chars} replacement characters")
    if 0.04 <= r.dictionary_hit_ratio < 0.10 and r.alpha_tokens >= 20:
        suspect.append(f"dictionary hit ratio {r.dictionary_hit_ratio:.2f} is low")
    # A missing ToUnicode map is a *risk factor*, not a defect. The standard
    # base-14 fonts (Helvetica, Times) carry standard encodings and extract
    # perfectly without one, and plenty of legitimate payroll and broker PDFs
    # use them. What the map's absence predicts is symbol soup — and the text
    # statistics above measure that outcome directly. So font metadata only
    # counts against a document whose text is ALSO weak; otherwise flagging it
    # forces a vision pass on documents that read fine, and a gate that cries
    # wolf on readable text gets ignored on the text that matters.
    if r.fonts_total and r.fonts_without_tounicode:
        if r.fonts_without_tounicode == r.fonts_total and r.dictionary_hit_ratio < 0.15:
            garbage.append("every font lacks a ToUnicode map and the text is not language")
        elif r.dictionary_hit_ratio < 0.25:
            suspect.append(f"{r.fonts_without_tounicode}/{r.fonts_total} fonts lack a ToUnicode map "
                           f"and the dictionary hit ratio is only {r.dictionary_hit_ratio:.2f}")
    if doc_hint and r.detected_doc_type and doc_hint != r.detected_doc_type:
        suspect.append(f"expected {doc_hint}, anchors say {r.detected_doc_type}")
    if doc_hint and not r.anchor_hits.get(doc_hint):
        suspect.append(f"no {doc_hint} anchor phrase found in text")

    if garbage:
        r.verdict, r.reasons = "garbage", garbage + suspect
    elif suspect:
        r.verdict, r.reasons = "suspect", suspect
    else:
        r.verdict, r.reasons = "ok", []
    return r


def main() -> int:  # pragma: no cover - thin CLI for manual checks
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Score extracted PDF text for trustworthiness.")
    ap.add_argument("pdf", help="PDF path (text is extracted with pdftotext -layout)")
    ap.add_argument("--hint", help="expected doc type, e.g. W-2")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not shutil.which("pdftotext"):
        print("pdftotext not on PATH — install poppler", file=sys.stderr)
        return 2
    proc = subprocess.run(["pdftotext", "-layout", args.pdf, "-"], capture_output=True, text=True)
    rep = assess(proc.stdout, doc_hint=args.hint, pdf_path=Path(args.pdf))
    if args.json:
        print(json.dumps(rep.as_dict(), indent=2))
    else:
        print(f"verdict: {rep.verdict}  doc_type: {rep.detected_doc_type}")
        for reason in rep.reasons:
            print(f"  - {reason}")
    return 0 if rep.verdict == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())

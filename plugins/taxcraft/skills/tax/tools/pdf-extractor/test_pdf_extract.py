#!/usr/bin/env python3
"""
Self-test for the pdf-extractor rungs: the quality gate, the field envelope and
its merge, the AcroForm rung, and `compare.py --fields`.

What this proves is narrow and deliberate. It cannot prove that a real W-2 parses
correctly — that needs the fixture corpus in `tools/form-parser/fixtures/`, and
vision cannot run headless at all. What it proves is that the *gates* behave:
that `(cid:N)` soup is called garbage rather than parsed into silent zeros, that
two reads which disagree are reported rather than averaged, that a missing
AcroForm engine returns "unknown" rather than "no fields", and that a field
disagreement makes `compare.py --fields` exit non-zero so CI can see it.

Poppler is optional here: the cases that need `pdftotext` / `pdftoppm` print
`SKIP ...` and pass. The pure-Python cases always run.

Runs with no arguments, exits 0 on pass, and writes only into a temp directory.

    python3 -B test_pdf_extract.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import acroform  # noqa: E402
import envelope  # noqa: E402
import pdf_extract  # noqa: E402
import quality  # noqa: E402

FAILURES: list[str] = []
SKIPS: list[str] = []
CHECKS = 0


def check(cond: bool, label: str) -> bool:
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILURES.append(label)
        print(f"FAIL {label}")
        return False
    return True


def skip(label: str, why: str) -> None:
    SKIPS.append(label)
    print(f"SKIP {label} — {why}")


# --------------------------------------------------------------------------
# Sample text
# --------------------------------------------------------------------------

W2_TEXT = """
                              2025 W-2 Wage and Tax Statement
Employer identification number (EIN)        91-1234567
Employer's name, address, and ZIP code
    ACME MANUFACTURING LLC
    1200 PIKE STREET, SEATTLE WA 98101
Employee's social security number           XXX-XX-4321
Employee's first name and initial           JANE Q PUBLIC
 1 Wages, tips, other compensation              145,000.00
 2 Federal income tax withheld                   28,400.00
 3 Social security wages                        168,600.00
 4 Social security tax withheld                  10,453.20
 5 Medicare wages and tips                      145,000.00
 6 Medicare tax withheld                          2,102.50
12a Code D                                       23,000.00
15 State  WA    Employer's state ID number
16 State wages, tips, etc.                      145,000.00
17 State income tax withheld                          0.00
Copy B — To Be Filed With Employee's FEDERAL Tax Return
Form W-2   Department of the Treasury — Internal Revenue Service
"""

INT_TEXT = """
PAYER'S name, street address, city                Form 1099-INT
FIRST TECH FEDERAL CREDIT UNION                   Interest Income
RECIPIENT'S name  JANE Q PUBLIC                   2025
 1 Interest income                                  1,284.00
 2 Early withdrawal penalty                             0.00
 3 Interest on U.S. Savings Bonds and Treasury obligations
 4 Federal income tax withheld                          0.00
 8 Tax-exempt interest                                  0.00
Department of the Treasury — Internal Revenue Service
"""

MORTGAGE_TEXT = """
RECIPIENT'S/LENDER'S name                         Form 1098
BIG NATIONAL BANK N.A.                            Mortgage Interest Statement
PAYER'S/BORROWER'S name  JANE Q PUBLIC            2025
 1 Mortgage interest received from payer(s)/borrower(s)   18,402.55
 2 Outstanding mortgage principal                        612,000.00
 3 Mortgage origination date                             2021-06-14
 5 Mortgage insurance premiums                                 0.00
 6 Points paid on purchase of principal residence              0.00
10 Other  Real property taxes paid                         7,412.00
Department of the Treasury — Internal Revenue Service
"""

# What a PDF whose fonts carry no ToUnicode map yields: long, dense, worthless.
CID_SOUP = ("(cid:37)(cid:12)(cid:88)(cid:3)(cid:49)(cid:82)(cid:3)(cid:20)\n"
            "(cid:9)(cid:71)(cid:15)(cid:3)(cid:44)(cid:81)(cid:3)(cid:23)(cid:3)\n") * 12

SYMBOL_SOUP = "§¶þÿ ¤¤¤ ‡‡ ~~~ ¬¬¬ ×÷ ±±± ¶¶ §§ ‰‰ „„ ‹‹ ›› ¡¡ ¿¿ ØØ\n" * 20


# --------------------------------------------------------------------------
# 1. quality.assess
# --------------------------------------------------------------------------

def test_quality() -> None:
    ok = quality.assess(W2_TEXT)
    check(ok.verdict == "ok", f"W-2 layout text scores ok (got {ok.verdict}: {ok.reasons})")
    check(ok.dictionary_hit_ratio >= 0.10,
          f"W-2 text reads as language (hit ratio {ok.dictionary_hit_ratio:.2f})")

    soup = quality.assess(CID_SOUP)
    check(soup.verdict == "garbage", f"(cid:N) soup is garbage (got {soup.verdict})")
    check(soup.cid_token_ratio > 0.10, "cid token ratio is measured, not guessed")
    check(any("cid" in r for r in soup.reasons), "the reason names the ToUnicode problem")

    sym = quality.assess(SYMBOL_SOUP)
    check(sym.verdict == "garbage", f"symbol soup is garbage (got {sym.verdict})")

    empty = quality.assess("")
    check(empty.verdict == "garbage", "empty text is garbage, not ok")

    # Never raises on odd input.
    for odd in (None, "\x00\x01\x02", "€" * 5, "1 2 3"):
        try:
            quality.assess(odd)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - the point of the check
            check(False, f"assess({odd!r}) raised {type(exc).__name__}: {exc}")
            continue
        check(True, f"assess({str(odd)[:8]!r}) returned a report instead of raising")

    # A hint that contradicts the anchors is a suspect, not a silent pass.
    mismatch = quality.assess(W2_TEXT, doc_hint="1099-INT")
    check(mismatch.verdict == "suspect",
          f"hint/anchor mismatch is suspect (got {mismatch.verdict})")


def test_doc_type_detection() -> None:
    for text, want in ((W2_TEXT, "W-2"), (INT_TEXT, "1099-INT"), (MORTGAGE_TEXT, "1098")):
        got, hits = quality.detect_doc_type(text)
        check(got == want, f"detect_doc_type → {want} (got {got}; hits {hits})")
    got, _ = quality.detect_doc_type("a grocery receipt for two avocados and milk")
    check(got is None, f"unrelated prose detects no doc type (got {got})")


# --------------------------------------------------------------------------
# 2. envelope.values_agree
# --------------------------------------------------------------------------

def test_values_agree() -> None:
    va = envelope.values_agree
    check(va(1000.0, 1000.40), "money agrees within the whole-dollar tolerance")
    check(va(145000.0, 145600.0), "money agrees within 0.5% on large amounts")
    check(not va(1000.0, 1010.0), "a $10 difference on $1,000 is a disagreement")
    check(not va(145000.0, 152000.0), "a 4.8% difference is a disagreement")
    check(va(0, 0.0), "zero agrees with zero")
    check(not va(None, 0.0), "NOT_PRESENT never agrees with an observed zero")
    check(va(None, None), "two absences agree")

    check(va("ACME  Manufacturing LLC", "acme manufacturing llc"),
          "strings compare case- and space-insensitively")
    check(va("1,284.00", 1284.0), "a numeric string compares as a number")
    check(not va("ACME LLC", "APEX LLC"), "different names disagree")

    d = [{"code": "D", "amount": 23000.0}, {"code": "DD", "amount": 14200.0}]
    check(va(d, [{"code": "dd", "amount": 14200.4}, {"code": "d", "amount": 23000.0}]),
          "code lists compare as multisets, order- and case-insensitively")
    check(not va(d, [{"code": "D", "amount": 23000.0}]),
          "a code list missing an entry disagrees")
    check(not va(d, [{"code": "D", "amount": 23000.0}, {"code": "DD", "amount": 1420.0}]),
          "a code list with a wrong amount disagrees")


# --------------------------------------------------------------------------
# 3. envelope.merge
# --------------------------------------------------------------------------

def _doc(**boxes) -> dict:
    return {
        "doc_type": "W-2",
        "schema_version": 2,
        "tax_year": 2025,
        "identity": {"employee_name": envelope.make("JANE Q PUBLIC", page=1, box="e")},
        "boxes": {k: v for k, v in boxes.items()},
    }


def test_merge() -> None:
    text_doc = _doc(
        box_1=envelope.make(145000.0, page=1, box="1"),
        box_2=envelope.make(28400.0, page=1, box="2"),
        box_3=envelope.make(None, "NOT_PRESENT"),
        box_4=envelope.make(10453.20, page=1, box="4"),
    )
    vision_doc = _doc(
        box_1=envelope.make(145000.0, page=1, box="1"),   # agree
        box_2=envelope.make(24800.0, page=1, box="2"),    # disagree (digit swap)
        box_3=envelope.make(168600.0, page=1, box="3"),   # one-sided (vision only)
        box_4=envelope.make(None, "UNREADABLE"),          # text only, vision blind
    )
    merged = envelope.merge(text_doc, vision_doc)
    boxes = merged["boxes"]
    ext = merged["_extraction"]

    check(boxes["box_1"]["value"] == 145000.0, "agreed field keeps its value")
    check(boxes["box_1"]["confidence"] == envelope.CONF_AGREE,
          f"agreement is high confidence (got {boxes['box_1']['confidence']})")
    check(boxes["box_1"].get("engines") == ["text", "vision"], "agreement records both engines")

    check(boxes["box_2"]["value"] == 24800.0, "disagreement keeps the vision value")
    check(boxes["box_2"]["confidence"] == envelope.CONF_DISAGREE, "disagreement is low confidence")
    alts = boxes["box_2"].get("alternates") or []
    check(any(a["value"] == 28400.0 for a in alts), "the text value survives as an alternate")
    check("boxes.box_2" in ext["review_required"], "a disagreement is listed for review")

    check(boxes["box_3"]["value"] == 168600.0, "a one-sided read keeps that value")
    check(boxes["box_3"]["confidence"] == envelope.CONF_SINGLE, "one-sided is medium confidence")
    check(boxes["box_3"]["state"] == "OBSERVED_VALUE", "a one-sided read is still observed")

    check(boxes["box_4"]["value"] == 10453.20, "text wins where vision was UNREADABLE")
    check("boxes.box_4" in ext["review_required"],
          "a box one engine could not read is flagged for review")

    check(ext["merged"] is True and ext["engines"] == ["text", "vision"],
          "the merge records which engines ran")
    check(merged["schema_version"] == envelope.SCHEMA_VERSION, "merge stamps schema_version 2")
    check(len(envelope.review_summary(merged)) == len(ext["review_required"]),
          "review_summary covers every flagged field")

    # Single-engine merge: nothing is invented, nothing is zeroed.
    solo = envelope.merge(text_doc, None)
    check(solo["_extraction"]["merged"] is False, "a single-engine merge is not marked merged")
    check(solo["boxes"]["box_3"]["state"] == "NOT_PRESENT",
          "a box nobody saw stays NOT_PRESENT, never 0")
    check(envelope.unwrap(solo["boxes"]["box_3"]) is None, "NOT_PRESENT unwraps to None, not 0")

    # A doc_type mismatch is an error, not a silent merge of two different forms.
    other = _doc(box_1=envelope.make(1.0))
    other["doc_type"] = "1099-INT"
    try:
        envelope.merge(text_doc, other)
        check(False, "merging two different doc types raises")
    except ValueError:
        check(True, "merging two different doc types raises")


# --------------------------------------------------------------------------
# 4. acroform
# --------------------------------------------------------------------------

def test_acroform(tmp: Path) -> None:
    engine = acroform.has_engine()

    missing = acroform.read_fields(tmp / "does-not-exist.pdf")
    check(missing is None, "a missing file returns None, not {}")
    check(bool(acroform.last_error), "the reason for a None lands in last_error")

    broken = tmp / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4\nthis is not a PDF body\n%%EOF\n")
    try:
        got = acroform.read_fields(broken)
    except Exception as exc:  # pragma: no cover - the point of the check
        check(False, f"a broken PDF must not raise (raised {type(exc).__name__}: {exc})")
        got = None
    check(got is None or isinstance(got, dict), "a broken PDF returns None or a dict, never raises")

    if engine is None:
        check(acroform.read_fields(_plain_pdf(tmp)) is None,
              "with no engine, read_fields returns None (unknown), not {} (no fields)")
        check("engine" in (acroform.last_error or ""),
              "last_error explains that no engine is installed")
        skip("acroform on a fieldless PDF", "neither pypdf nor pdftk is installed")
    else:
        fields = acroform.read_fields(_plain_pdf(tmp))
        check(fields is None or fields == {},
              f"a PDF with no widgets yields {{}} (or None), got {fields!r}")

    # The pdftk block parser is pure text handling — testable without pdftk.
    dump = (
        "---\nFieldType: Text\nFieldName: topmostSubform[0].Box1[0]\nFieldValue: 145000.00\n"
        "---\nFieldType: Text\nFieldName: topmostSubform[0].Box2[0]\nFieldValue: \n"
        "---\nFieldType: Choice\nFieldName: Codes\nFieldValue: D\nFieldValue: DD\n"
    )
    parsed = acroform._parse_pdftk_dump(dump)
    check(parsed.get("topmostSubform[0].Box1[0]") == "145000.00", "pdftk dump: value parsed")
    check("topmostSubform[0].Box2[0]" not in parsed,
          "pdftk dump: an unfilled widget is dropped, not read as an empty string")
    check(parsed.get("Codes") == "D, DD", "pdftk dump: a multi-value field is joined")


# --------------------------------------------------------------------------
# 5. compare.py --fields
# --------------------------------------------------------------------------

def test_compare_fields(tmp: Path) -> None:
    a = _doc(
        box_1=envelope.make(145000.0, page=1, box="1"),
        box_2=envelope.make(28400.0, page=1, box="2"),
    )
    a["state_local"] = [{"state": envelope.make("WA", page=1, box="15"),
                         "state_wages": envelope.make(145000.0, page=1, box="16")}]
    b = json.loads(json.dumps(a))
    b["boxes"]["box_2"] = envelope.make(24800.0, page=1, box="2")     # conflict
    b["boxes"]["box_3"] = envelope.make(168600.0, page=1, box="3")    # one-sided

    a_path, b_path = tmp / "text.json", tmp / "vision.json"
    a_path.write_text(json.dumps(a), encoding="utf-8")
    b_path.write_text(json.dumps(b), encoding="utf-8")

    script = str(HERE / "compare.py")
    proc = subprocess.run([sys.executable, "-B", script, "--fields", str(a_path), str(b_path)],
                          capture_output=True, text=True)
    check(proc.returncode == 1,
          f"a field disagreement exits 1 (got {proc.returncode}; stderr={proc.stderr.strip()[:200]})")
    check("boxes.box_2" in proc.stdout, "the conflicting field is named in the table")
    check("boxes.box_3" in proc.stdout, "the one-sided field is named in the table")

    proc = subprocess.run([sys.executable, "-B", script, "--fields", str(a_path), str(b_path), "--json"],
                          capture_output=True, text=True)
    check(proc.returncode == 1, "--json keeps the non-zero exit on disagreement")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        check(False, f"--fields --json emits valid JSON (got {proc.stdout[:200]!r})")
        payload = {"disagreements": []}
    paths = {d["path"] for d in payload.get("disagreements", [])}
    check(paths == {"boxes.box_2", "boxes.box_3"},
          f"exactly the two disagreeing paths are reported (got {sorted(paths)})")
    kinds = {d["path"]: d["kind"] for d in payload.get("disagreements", [])}
    check(kinds.get("boxes.box_3") == "one-sided", "a field only one read saw is marked one-sided")
    check(payload.get("agree") is False, "agree=false when anything disagrees")

    # Identical documents agree and exit 0.
    same = tmp / "same.json"
    same.write_text(json.dumps(a), encoding="utf-8")
    proc = subprocess.run([sys.executable, "-B", script, "--fields", str(a_path), str(same)],
                          capture_output=True, text=True)
    check(proc.returncode == 0,
          f"two identical documents exit 0 (got {proc.returncode}; {proc.stderr.strip()[:200]})")

    # Tolerance is real: cents drift is not a disagreement.
    close = json.loads(json.dumps(a))
    close["boxes"]["box_2"] = envelope.make(28400.40, page=1, box="2")
    close_path = tmp / "close.json"
    close_path.write_text(json.dumps(close), encoding="utf-8")
    proc = subprocess.run([sys.executable, "-B", script, "--fields", str(a_path), str(close_path)],
                          capture_output=True, text=True)
    check(proc.returncode == 0, "cents-level drift is not reported as a disagreement")


# --------------------------------------------------------------------------
# 6. pdf_extract end to end (poppler only)
# --------------------------------------------------------------------------

def _pdf_bytes(lines: list[str]) -> bytes:
    """A minimal one-page PDF with Helvetica text. Enough for poppler to read
    back; deliberately hand-built so the test needs no fixture and no writer."""
    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content = "BT /F1 9 Tf 1 0 0 1 36 750 Tm 11 TL\n"
    for line in lines:
        content += f"({esc(line)}) Tj T*\n"
    content += "ET\n"
    stream = content.encode("latin-1", "replace")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n"
            "%%EOF\n").encode()
    return bytes(out)


def _plain_pdf(tmp: Path) -> Path:
    path = tmp / "plain.pdf"
    if not path.exists():
        path.write_bytes(_pdf_bytes(["A plain page with no form fields."]))
    return path


def test_extract(tmp: Path) -> None:
    if not shutil.which("pdftotext"):
        skip("pdf_extract end-to-end", "pdftotext (poppler) is not installed")
        return

    w2 = tmp / "w2.pdf"
    w2.write_bytes(_pdf_bytes([ln for ln in W2_TEXT.splitlines() if ln.strip()]))

    r = pdf_extract.extract(w2, doc_hint="W-2", out_dir=tmp / "auto")
    check(r.mode == "text", f"a text W-2 comes back as text (got {r.mode})")
    check(bool(r.text) and "145,000.00" in (r.text or ""), "box 1 survives the text rung")
    check(r.doc_type == "W-2", f"doc type detected from the text (got {r.doc_type})")
    check(r.quality is not None, "the quality report rides along on the result")
    verdict = (r.quality or {}).get("verdict")
    # This PDF draws with base-14 Helvetica, which carries no ToUnicode map, so
    # the gate calls it suspect on a machine with pdffonts. Either verdict is a
    # pass; what must hold is that text_ok mirrors it exactly.
    check(verdict in ("ok", "suspect"), f"clean text is not called garbage (got {verdict})")
    check(r.text_ok == (verdict == "ok"),
          f"text_ok mirrors the gate verdict (text_ok={r.text_ok}, verdict={verdict})")
    if verdict == "suspect" and shutil.which("pdftoppm"):
        check(bool(r.pngs) and bool(r.text),
              "a suspect read hands back BOTH the text and page images to cross-check")
        check(r.mode == "text", "a suspect read keeps mode='text' for existing callers")
    check(r.pages == 1, f"page count comes from pdfinfo (got {r.pages})")
    check(r.acroform is None or r.acroform == {}, "a non-fillable PDF reports no fields")
    check(isinstance(r.as_dict(), dict) and json.dumps(r.as_dict(), default=str),
          "the result serializes to JSON for --json")

    # mode="text" never rasterizes, whatever else it finds.
    t = pdf_extract.extract(w2, mode="text")
    check(t.mode == "text" and not t.pngs, "mode=text returns text and no images")

    if not shutil.which("pdftoppm"):
        skip("pdf_extract form mode", "pdftoppm (poppler) is not installed")
        return

    f = pdf_extract.extract(w2, mode="form", doc_hint="W-2", out_dir=tmp / "form")
    check(f.mode == "form", f"mode=form reports mode 'form' (got {f.mode})")
    check(len(f.pngs) == 1, f"form mode always rasterizes (got {len(f.pngs)} images)")
    check(bool(f.text), "form mode still runs text as the cross-check")
    check(f.diagnostics.get("dpi") == pdf_extract.FORM_DPI,
          f"form mode rasterizes at {pdf_extract.FORM_DPI} dpi (got {f.diagnostics.get('dpi')})")
    check(all(Path(p).is_file() for p in f.pngs), "the PNG paths exist")
    check(all(str(HERE) not in p for p in f.pngs), "no PNG is written inside the skill tree")

    d = pdf_extract.extract(w2, mode="form", dpi=150, out_dir=tmp / "form150")
    check(d.diagnostics.get("dpi") == 150, "an explicit --dpi overrides the form default")

    # Garbage text must not be handed back as if it were readable.
    junk = tmp / "junk.pdf"
    junk.write_bytes(_pdf_bytes(CID_SOUP.splitlines()))
    g = pdf_extract.extract(junk, out_dir=tmp / "junk_out")
    check(g.text is None, f"garbage text is withheld, not returned (got {(g.text or '')[:40]!r})")
    check(g.text_ok is False, "text_ok is False for garbage")
    check(g.mode == "image", f"garbage text falls through to the image rung (got {g.mode})")
    check(bool(g.pngs), "the caller gets page images to read instead")

    # force_image still skips text entirely, as it always did.
    fi = pdf_extract.extract(w2, force_image=True, out_dir=tmp / "forced")
    check(fi.mode == "image" and fi.text is None and bool(fi.pngs),
          "force_image keeps its old behaviour")
    check(fi.diagnostics.get("dpi") == pdf_extract.DEFAULT_DPI,
          "auto mode still rasterizes at 200 dpi by default")

    missing = pdf_extract.extract(tmp / "nope.pdf")
    check(missing.mode == "failed", "a missing file fails cleanly instead of raising")


# --------------------------------------------------------------------------

def main() -> int:
    with tempfile.TemporaryDirectory(prefix="pdfextract_test_") as td:
        tmp = Path(td)
        test_quality()
        test_doc_type_detection()
        test_values_agree()
        test_merge()
        test_acroform(tmp)
        test_compare_fields(tmp)
        test_extract(tmp)

    print()
    if FAILURES:
        print(f"FAILED — {len(FAILURES)} of {CHECKS} checks failed"
              + (f", {len(SKIPS)} group(s) skipped" if SKIPS else ""))
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"PASS — {CHECKS} checks"
          + (f", {len(SKIPS)} group(s) skipped: {', '.join(SKIPS)}" if SKIPS else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

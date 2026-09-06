#!/usr/bin/env python3
"""
Self-test for the form parser. No arguments, exit 0 on pass.

    python3 -B tools/form-parser/test_form_parser.py

What it proves, in the order it matters:

  1. Every fixture in `fixtures/<slug>/text.pdf` parses to its `golden.json` —
     with `--type` AND with auto-detection. That is the regression net: the
     registry's label patterns keep reading the values they used to read.
  2. A good fixture raises no HIGH/CRITICAL invariant, and `w-2-broken`
     (box 4 inflated tenfold) raises exactly `W2.box4_ss_rate`. An invariant
     suite that never fires proves nothing.
  3. Garbage text is refused rather than parsed: no text engine, verdict garbage.
  4. A scanned page yields PNGs and a vision prompt carrying the skeleton.
  5. An AcroForm PDF is read through rung 0.
  6. A vision read that disagrees lands the field in `review_required` and
     exits 1 instead of silently picking a side.

Everything temporary goes to `tempfile`; nothing is written inside the skill.
Without poppler the PDF cases print SKIP and the pure-python cases still run.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent / "pdf-extractor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import envelope  # noqa: E402
import form_parser  # noqa: E402
import invariants as invariants_mod  # noqa: E402
import doc_types  # noqa: E402
from doc_types import REGISTRY, FORM_PARSER_TYPES  # noqa: E402

FIXTURES = _HERE / "fixtures"
HAVE_PDFTOTEXT = shutil.which("pdftotext") is not None
failures: list[str] = []
checks = 0
skips = 0


def _have_pypdf() -> bool:
    try:
        import pypdf  # noqa: F401
        return True
    except Exception:
        return False


def check(cond: bool, label: str, detail: str = "") -> None:
    global checks
    checks += 1
    if not cond:
        failures.append(f"{label}" + (f" — {detail}" if detail else ""))


def skip(label: str) -> None:
    global skips
    skips += 1
    print(f"SKIP: {label}")


# --------------------------------------------------------------------------
# Pure-python cases (no poppler needed)
# --------------------------------------------------------------------------

def test_number_parsing() -> None:
    cases = {
        "1,234.56": 1234.56, "$1,234.56": 1234.56, "(1,234.56)": -1234.56,
        "-500.00": -500.0, "0.00": 0.0, "42": 42.0,
        "": None, "abc": None, "1.2.3": None,
    }
    for raw, want in cases.items():
        check(form_parser.to_number(raw) == want, "to_number", f"{raw!r} → {form_parser.to_number(raw)!r} want {want!r}")


def test_money_tokens() -> None:
    # A bare integer inside the label never beats the formatted amount.
    check(form_parser._money_tokens("Unrecap. Sec. 1250 gain     300.00") == [300.0],
          "money tokens prefer formatted", str(form_parser._money_tokens("Unrecap. Sec. 1250 gain     300.00")))
    check(form_parser._money_tokens("  1,050.00   1,120.00   840.00") == [1050.0, 1120.0, 840.0],
          "money tokens keep column order")
    check(form_parser._money_tokens("no amounts here") == [], "money tokens on prose")


def test_column_value() -> None:
    check(form_parser._column_value(", address, and ZIP code    Northwater Logistics LLC")
          == "Northwater Logistics LLC", "column value skips label continuation")
    check(form_parser._column_value("   123-45-6789") == "123-45-6789", "column value plain")
    check(form_parser._column_value("     ") == "", "column value empty")


def test_never_zero_for_missing() -> None:
    """The contract that matters: absent is not zero."""
    box = REGISTRY["W-2"].box("box_1")
    env = form_parser._envelope_for(box, None, page=1)
    check(env["state"] == "NOT_PRESENT" and envelope.unwrap(env) is None,
          "missing money box is NOT_PRESENT, unwraps to None", json.dumps(env))
    env = form_parser._envelope_for(box, "not a number", page=1)
    check(env["state"] == "UNREADABLE" and envelope.unwrap(env) is None,
          "unparsable money box is UNREADABLE, unwraps to None", json.dumps(env))
    env = form_parser._envelope_for(box, "0.00", page=1)
    check(env["state"] == "OBSERVED_ZERO" and envelope.unwrap(env) == 0.0,
          "a printed zero is OBSERVED_ZERO")


def test_registry_invariants_compile() -> None:
    errs = invariants_mod.self_check()
    check(not errs, "every registry invariant compiles", "; ".join(errs))


def test_vision_skeleton_roundtrip() -> None:
    for name in FORM_PARSER_TYPES:
        dt = REGISTRY[name]
        sk = dt.vision_skeleton()
        doc = form_parser.build_vision_doc(sk, dt)
        check(set(doc["boxes"]) == {b.id for b in dt.boxes},
              f"{name}: vision skeleton covers every box")
        check(all(envelope.state_of(e) == "NOT_PRESENT" for e in doc["boxes"].values()),
              f"{name}: an unfilled skeleton is NOT_PRESENT throughout, never zero")


def test_generic_template_is_inert() -> None:
    tpls = form_parser.load_templates()
    check(any(t.get("_name") == "generic.json" for t in tpls), "generic.json loads")
    check(form_parser.pick_template({"producer": "Anything At All", "creator": "x"}, "W-2") is None,
          "generic.json matches nothing")


def test_unknown_and_foreign_types() -> None:
    try:
        form_parser.resolve_doc_type("K-1-1065", None, None)
        check(False, "K-1 is routed away from form-parser")
    except form_parser.UsageError as e:
        check("k1-parser" in str(e), "K-1 error names the right tool", str(e))
    try:
        form_parser.resolve_doc_type("Form-9999", None, None)
        check(False, "an unknown type is a usage error")
    except form_parser.UsageError:
        check(True, "unknown type raises UsageError")


# --------------------------------------------------------------------------
# Fixture cases
# --------------------------------------------------------------------------

def fixture_dirs() -> list[Path]:
    if not FIXTURES.is_dir():
        return []
    return [d for d in sorted(FIXTURES.iterdir()) if (d / "golden.json").is_file()]


def same(got, want) -> bool:
    if isinstance(want, bool) or isinstance(got, bool):
        return got is not None and bool(got) == bool(want)
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return abs(float(got) - float(want)) <= 0.01
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return False
        return all(a.get("code") == b.get("code")
                   and abs(float(a.get("amount") or 0) - float(b.get("amount") or 0)) <= 0.01
                   for a, b in zip(got, want))
    if want is None or got is None:
        return want is got
    return " ".join(str(got).split()).casefold() == " ".join(str(want).split()).casefold()


def compare(doc: dict, gold: dict, label: str) -> None:
    """Every golden value is read back from the text pass — except the boxes the
    registry marks `text_unreliable`, which the text pass must REFUSE to read.

    Those are boxes whose caption appears twice on the form (a consolidated
    1099 prints "Federal income tax withheld" in both its interest and dividend
    sections). A line-local regex cannot tell which one it matched, so the
    correct text-pass answer is UNREADABLE, and vision supplies the figure. The
    golden file still records the true value for the vision and merge paths.
    """
    check(doc.get("tax_year") == gold["tax_year"], f"{label}: tax_year",
          f"got {doc.get('tax_year')!r}")
    dt = doc_types.get(gold["doc_type"])
    for section in ("identity", "boxes"):
        for k, want in gold[section].items():
            env = (doc.get(section) or {}).get(k)
            got = envelope.unwrap(env)
            box = dt.box(k)
            if box is not None and getattr(box, "text_unreliable", False):
                check(envelope.state_of(env) == "UNREADABLE",
                      f"{label}: {section}.{k} is UNREADABLE from text (ambiguous caption)",
                      f"got state {envelope.state_of(env)!r} value {got!r}")
                continue
            check(same(got, want), f"{label}: {section}.{k}", f"got {got!r} want {want!r}")


def test_fixtures() -> None:
    dirs = fixture_dirs()
    check(bool(dirs), "fixtures are present")
    covered = {json.loads((d / "golden.json").read_text())["doc_type"] for d in dirs}
    missing = sorted(set(FORM_PARSER_TYPES) - covered)
    check(not missing, "every form-parser doc type has a fixture", ", ".join(missing))
    if not HAVE_PDFTOTEXT:
        skip(f"{len(dirs)} PDF fixtures (pdftotext not on PATH — install poppler)")
        return
    for d in dirs:
        gold = json.loads((d / "golden.json").read_text())
        name = gold["doc_type"]
        compare(form_parser.parse(d / "text.pdf", name), gold, f"{d.name} --type")
        compare(form_parser.parse(d / "text.pdf"), gold, f"{d.name} auto")


def test_invariants_fire_only_when_they_should() -> None:
    if not HAVE_PDFTOTEXT:
        skip("invariant firing (needs poppler)")
        return
    for d in fixture_dirs():
        gold = json.loads((d / "golden.json").read_text())
        doc = form_parser.parse(d / "text.pdf", gold["doc_type"])
        hits = [f["check"] for f in doc["_extraction"]["findings"]
                if f["severity"] in ("HIGH", "CRITICAL")]
        if d.name == "w-2-broken":
            check("W2.box4_ss_rate" in hits,
                  "w-2-broken raises W2.box4_ss_rate (box 4 is 10x the 6.2% rate)", str(hits))
        else:
            check(not hits, f"{d.name}: a consistent form raises no HIGH/CRITICAL", str(hits))


def test_garbage_is_refused() -> None:
    pdf = FIXTURES / "w-2" / "garbage.pdf"
    if not HAVE_PDFTOTEXT or not pdf.is_file():
        skip("garbage.pdf quality gate (needs poppler + fixture)")
        return
    doc = form_parser.parse(pdf, "W-2")
    ext = doc["_extraction"]
    check(ext["quality"]["verdict"] == "garbage", "garbage.pdf verdict is garbage",
          str(ext["quality"]["verdict"]))
    check("text" not in ext["engines"], "garbage.pdf produced no text engine", str(ext["engines"]))
    check(all(not envelope.is_present(e) for _, e in envelope.walk(doc)),
          "garbage.pdf produced no observed values at all")


def test_scan_yields_vision_prompt() -> None:
    pdf = FIXTURES / "w-2" / "scan.pdf"
    if not pdf.is_file():
        skip("scan.pdf (not generated — pdftoppm was unavailable at fixture time)")
        return
    if not shutil.which("pdftoppm"):
        skip("scan.pdf vision prompt (pdftoppm not on PATH)")
        return
    out = run_cli([str(pdf), "--type", "W-2", "--vision-prompt"])
    check(out.returncode == 0, "--vision-prompt exits 0", out.stderr[-300:])
    check(".png" in out.stdout, "--vision-prompt lists page images")
    check('"box_1": null' in out.stdout, "--vision-prompt carries the skeleton")
    check("never guess" in out.stdout.lower(), "--vision-prompt carries the rules")


def test_acroform() -> None:
    pdf = FIXTURES / "w-2" / "acroform.pdf"
    if not pdf.is_file():
        skip("acroform.pdf (fixture absent)")
        return
    if not (shutil.which("pdftk") or _have_pypdf()):
        skip("acroform.pdf (neither pypdf nor pdftk available)")
        return
    doc = form_parser.parse(pdf, "W-2")
    check("acroform" in doc["_extraction"]["engines"], "acroform.pdf is read through rung 0",
          str(doc["_extraction"]["engines"]))
    gold = json.loads((FIXTURES / "w-2" / "golden.json").read_text())
    compare(doc, gold, "acroform")


def test_merge_disagreement() -> None:
    if not HAVE_PDFTOTEXT:
        skip("--merge disagreement (needs poppler)")
        return
    gold = json.loads((FIXTURES / "w-2" / "golden.json").read_text())
    vision = REGISTRY["W-2"].vision_skeleton()
    vision["tax_year"] = gold["tax_year"]
    for k, v in gold["boxes"].items():
        if k in vision["boxes"]:
            vision["boxes"][k] = v
    vision["boxes"]["box_2"] = 18600.00      # the model read a different box 2
    with tempfile.TemporaryDirectory(prefix="form-parser-test-") as tmp:
        vp = Path(tmp) / "vision.json"
        vp.write_text(json.dumps(vision))
        doc = form_parser.parse(FIXTURES / "w-2" / "text.pdf", "W-2",
                                vision_json=json.loads(vp.read_text()))
        review = doc["_extraction"]["review_required"]
        check("boxes.box_2" in review, "a disagreement lands in review_required", str(review))
        env = doc["boxes"]["box_2"]
        check(env.get("alternates"), "the losing read is kept as an alternate", json.dumps(env))
        check("boxes.box_1" not in review, "agreeing boxes stay out of review_required")

        out = run_cli([str(FIXTURES / "w-2" / "text.pdf"), "--type", "W-2",
                       "--merge", str(vp), "--quiet"])
        check(out.returncode == 1, "a document needing review exits 1", str(out.returncode))


def test_write_and_exit_codes() -> None:
    if not HAVE_PDFTOTEXT:
        skip("--write and exit codes (needs poppler)")
        return
    with tempfile.TemporaryDirectory(prefix="form-parser-write-") as tmp:
        pdf = Path(tmp) / "w2.pdf"
        shutil.copyfile(FIXTURES / "w-2" / "text.pdf", pdf)
        out = run_cli([str(pdf), "--type", "W-2", "--write", "--quiet"])
        # A text-only parse of a boxed form exits 1 on purpose: it is provisional
        # until a second engine confirms it, because a wrong font encoding yields
        # confident wrong numbers that no text statistic can see. It still writes,
        # carrying the flag that says so.
        check(out.returncode == 1, "a text-only form parse exits 1 (provisional)",
              out.stdout + out.stderr)
        written = Path(tmp) / ".parsed" / "w2.json"
        check(written.is_file(), "--write lands in <pdf dir>/.parsed/<stem>.json")
        if written.is_file():
            doc = json.loads(written.read_text())
            check(doc["schema_version"] == 2, "the written document is schema_version 2")
            check(doc["_extraction"]["sha256"], "the written document records the source hash")
            check(doc["_extraction"].get("vision_required") is True,
                  "a text-only form parse is marked vision_required")
            check(any("provisional" in w for w in doc.get("warnings", [])),
                  "the provisional warning reaches the written document")

        out = run_cli([str(pdf), "--type", "K-1-1065"])
        check(out.returncode == 2, "a foreign doc type is exit 2", str(out.returncode))
        check("k1-parser" in out.stderr, "the exit-2 message names the right tool", out.stderr)

        out = run_cli([str(Path(tmp) / "nope.pdf"), "--type", "W-2"])
        check(out.returncode == 2, "a missing file is exit 2", str(out.returncode))

        out = run_cli([str(FIXTURES / "w-2-broken" / "text.pdf"), "--type", "W-2", "--quiet"])
        check(out.returncode == 1, "a HIGH finding exits 1", str(out.returncode))


def run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(_HERE / "form_parser.py"), *args],
                          capture_output=True, text=True, timeout=180)


# --------------------------------------------------------------------------

def test_w2_fica_rate_bounds() -> None:
    """Boxes 4 and 6 are bounded on BOTH sides, with a documented escape.

    These are the checks most likely to be loosened by accident. Box 4 is the
    social security tax actually collected, so it may fall below 6.2% of boxes
    3 + 7 — but only by the uncollected tax the employer reports in box 12
    (code A for tips, code M for former-employee group-term life). An upper
    bound alone would let a box 4 misread as $2,000 where $3,100 was printed
    pass in silence, which is the exact transposition the check exists for.
    """
    def w2(**over):
        boxes = {"box_1": envelope.make(50000), "box_2": envelope.make(5000),
                 "box_3": envelope.make(50000), "box_5": envelope.make(50000),
                 "box_12": envelope.make([])}
        boxes.update(over)
        return {"doc_type": "W-2", "tax_year": 2025, "boxes": boxes}

    def fired(doc):
        # Only the rate checks are under test here; these skeleton documents
        # carry no identity block, whose absence is its own (correct) finding.
        return {f["check"] for f in invariants_mod.evaluate(doc, doc_name="w2")
                if f["severity"] in ("HIGH", "CRITICAL")
                and not f["check"].endswith("required_missing")}

    correct = w2(box_4=envelope.make(3100), box_6=envelope.make(725))
    check(not fired(correct), "a consistent W-2 raises no rate finding", str(fired(correct)))

    low = w2(box_4=envelope.make(2000), box_6=envelope.make(500))
    check("W2.box4_ss_rate" in fired(low), "box 4 read too LOW is caught")
    check("W2.box6_medicare_rate" in fired(low), "box 6 read too LOW is caught")

    high = w2(box_4=envelope.make(4000), box_6=envelope.make(725))
    check("W2.box4_ss_rate" in fired(high), "box 4 read too HIGH is caught")

    uncollected = w2(box_4=envelope.make(1900), box_6=envelope.make(445),
                     box_12=envelope.make([{"code": "A", "amount": 1200},
                                           {"code": "B", "amount": 280}]))
    check(not fired(uncollected),
          "a shortfall explained by uncollected tax in box 12 is not a finding",
          str(fired(uncollected)))

    # Wages at the wage base with the 0.9% additional Medicare tax above $200k.
    earner = w2(box_3=envelope.make(176100), box_4=envelope.make(10918),
                box_5=envelope.make(250000), box_6=envelope.make(4075))
    check(not fired(earner), "a high earner at the wage base is not a finding", str(fired(earner)))

    # The additional Medicare tax is part of the amount box 6 must report. A
    # $250,000 W-2 owes $3,625 + $450; a box 6 of $3,650 is $425 short and must
    # be caught, even though it clears 1.45% of box 5 on its own.
    big = {"box_1": envelope.make(250000), "box_2": envelope.make(50000),
           "box_3": envelope.make(176100), "box_4": envelope.make(10918),
           "box_5": envelope.make(250000), "box_12": envelope.make([])}
    short6 = {"doc_type": "W-2", "tax_year": 2025,
              "boxes": {**big, "box_6": envelope.make(3650)}}
    check("W2.box6_medicare_rate" in fired(short6),
          "a box 6 short by the additional Medicare tax is caught", str(fired(short6)))
    ok6 = {"doc_type": "W-2", "tax_year": 2025, "boxes": {**big, "box_6": envelope.make(4075)}}
    check(not fired(ok6), "the same W-2 with the full $4,075 is silent", str(fired(ok6)))
    exp6 = {"doc_type": "W-2", "tax_year": 2025,
            "boxes": {**big, "box_6": envelope.make(3650),
                      "box_12": envelope.make([{"code": "N", "amount": 425}])}}
    check(not fired(exp6), "the shortfall explained by box 12 code N is silent", str(fired(exp6)))

    unread12 = w2(box_4=envelope.make(2000), box_6=envelope.make(725),
                  box_12=envelope.make(None, "UNREADABLE"))
    checks_run = {f["check"] for f in invariants_mod.evaluate(unread12, doc_name="w2")}
    check("W2.box4_ss_rate.not_evaluable" in checks_run,
          "a shortfall with box 12 unread is reported as unproven, not passed")


TESTS = [
    test_number_parsing,
    test_money_tokens,
    test_column_value,
    test_never_zero_for_missing,
    test_registry_invariants_compile,
    test_vision_skeleton_roundtrip,
    test_generic_template_is_inert,
    test_unknown_and_foreign_types,
    test_fixtures,
    test_invariants_fire_only_when_they_should,
    test_w2_fica_rate_bounds,
    test_garbage_is_refused,
    test_scan_yields_vision_prompt,
    test_acroform,
    test_merge_disagreement,
    test_write_and_exit_codes,
]


def main() -> int:
    for fn in TESTS:
        try:
            fn()
        except Exception as e:  # a crash is a failure, with the test named
            failures.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    if failures:
        print(f"FAIL: {len(failures)} of {checks} checks failed")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"PASS: {checks} checks over {len(fixture_dirs())} PDF fixtures"
          + (f" ({skips} skipped)" if skips else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

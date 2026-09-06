#!/usr/bin/env python3
"""
compare — differential extraction (Layer A of the confidence system).

Runs the same PDF through several INDEPENDENT text extractors and reports
where they disagree about the dollar figures on the page. Agreement is weak
evidence of correctness; disagreement is strong evidence that a human (or a
vision pass) needs to look.

This deliberately does not decide who is right. It narrows a whole document
down to the handful of figures worth checking by hand.

Engines (each skipped silently if unavailable):
  - pdftotext -layout   preserves column geometry
  - pdftotext -raw      different reading order, no layout reconstruction
  - pdfplumber          separate library, separate PDF parser

A fourth opinion — vision on the rasterized page — cannot run headless.
Use `--pngs` to get page images to read back through the model, then pass
the figures you read via `--expect`.

A second mode compares two already-parsed documents instead of two text
extractions: `--fields text.json vision.json` walks the schema_version 2 shape
(`identity`, `boxes`, `state_local[]`) through `envelope.py` and prints the
fields where the two reads disagree. That is the same comparison `envelope.merge`
makes, reported instead of applied — useful before you commit to a merge.

Usage:
    python3 compare.py <file.pdf>
    python3 compare.py <file.pdf> --json
    python3 compare.py <file.pdf> --expect 58192 --expect -4168
    python3 compare.py <file.pdf> --pngs        # also rasterize for a vision pass
    python3 compare.py --fields text.json vision.json
    python3 compare.py --fields text.json vision.json --json

Exit codes:
    0 = all available engines agree (and any --expect values were found);
        or, in --fields mode, no field disagrees
    1 = disagreement, or an --expect value is missing
    2 = usage/IO error, or fewer than two engines available

Pure stdlib except the optional pdfplumber probe. Never modifies the PDF.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from envelope import flatten, get_path, is_envelope, values_agree, walk  # local module
except Exception:  # pragma: no cover - only in a broken install
    flatten = get_path = is_envelope = values_agree = walk = None  # type: ignore

# A "money-like" token: requires a currency marker, comma grouping, or two
# decimal places. Bare integers are excluded on purpose — page numbers, box
# numbers, and years would otherwise swamp the signal.
MONEY = re.compile(r"""
    (?P<paren>\()?
    \$?\s*
    (?P<body>
        \d{1,3}(?:,\d{3})+(?:\.\d{1,2})?     # comma-grouped: 58,192 / 1,234.56
      | \d+\.\d{2}                            # explicit cents: 1234.56
      | \$\s*\d+                              # dollar-marked integer: $500
    )
    (?P<close>\))?
""", re.VERBOSE)


def to_amount(m: re.Match) -> float | None:
    body = m.group("body").replace(",", "").replace("$", "").strip()
    try:
        v = float(body)
    except ValueError:
        return None
    # Accounting negatives: (1,234) means -1234
    if m.group("paren") and m.group("close"):
        v = -v
    return v


def amounts(text: str) -> Counter:
    out: Counter = Counter()
    for m in MONEY.finditer(text):
        v = to_amount(m)
        if v is not None:
            out[round(v, 2)] += 1
    return out


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def engine_pdftotext(pdf: Path, mode: str) -> str | None:
    if not _have("pdftotext"):
        return None
    cmd = ["pdftotext"]
    if mode:
        cmd.append(mode)
    cmd += [str(pdf), "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, OSError):
        return None
    return r.stdout


def engine_pdfplumber(pdf: Path) -> str | None:
    probe = subprocess.run(
        [sys.executable, "-c",
         "import pdfplumber,sys;"
         "print('\\n'.join((p.extract_text() or '') "
         "for p in pdfplumber.open(sys.argv[1]).pages))", str(pdf)],
        capture_output=True, text=True)
    if probe.returncode != 0:
        return None
    return probe.stdout


def run_engines(pdf: Path) -> dict[str, Counter]:
    raw = {
        "pdftotext -layout": engine_pdftotext(pdf, "-layout"),
        "pdftotext -raw": engine_pdftotext(pdf, "-raw"),
        "pdfplumber": engine_pdfplumber(pdf),
    }
    return {name: amounts(text) for name, text in raw.items()
            if text is not None and text.strip()}



# --------------------------------------------------------------------------
# --fields: schema-aware per-field comparison of two parsed documents
# --------------------------------------------------------------------------

def _load_doc(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    return doc


def _label(doc: dict, path: Path) -> str:
    dt = doc.get("doc_type")
    return f"{path.name}" + (f" ({dt})" if dt else "")


def field_diff(a_doc: dict, b_doc: dict) -> list[dict]:
    """Every envelope path where the two documents disagree.

    One-sided fields (present in one read, absent from the other) are reported
    too — a box only one engine saw is exactly the kind of thing that becomes a
    silent zero downstream. `envelope.values_agree` supplies the tolerance:
    whole-dollar drift on money, case/space insensitivity on strings, multiset
    comparison on code lists.
    """
    a_flat, b_flat = flatten(a_doc), flatten(b_doc)
    paths = sorted(set(a_flat) | set(b_flat))
    out: list[dict] = []
    for path in paths:
        av, bv = a_flat.get(path), b_flat.get(path)
        if values_agree(av, bv):
            continue
        a_env, b_env = get_path(a_doc, path), get_path(b_doc, path)
        out.append({
            "path": path,
            "a": av,
            "b": bv,
            "a_state": a_env.get("state") if is_envelope(a_env) else None,
            "b_state": b_env.get("state") if is_envelope(b_env) else None,
            "kind": "one-sided" if (av is None) != (bv is None) else "conflict",
        })
    return out


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, (list, dict)):
        return json.dumps(v, sort_keys=True, default=str)
    return str(v)


def run_fields(a_path: Path, b_path: Path, as_json: bool) -> int:
    if flatten is None:
        print("envelope.py not importable — cannot compare fields", file=sys.stderr)
        return 2
    try:
        a_doc, b_doc = _load_doc(a_path), _load_doc(b_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"could not load documents: {exc}", file=sys.stderr)
        return 2

    warnings: list[str] = []
    if a_doc.get("doc_type") and b_doc.get("doc_type") and a_doc["doc_type"] != b_doc["doc_type"]:
        warnings.append(
            f"doc_type differs: {a_doc['doc_type']!r} vs {b_doc['doc_type']!r} — "
            "these may not be the same document")
    for doc, path in ((a_doc, a_path), (b_doc, b_path)):
        if doc.get("schema_version") not in (2, None):
            warnings.append(f"{path.name}: schema_version {doc.get('schema_version')!r}, expected 2")
        if not any(True for _ in walk(doc)):
            warnings.append(f"{path.name}: no field envelopes found (legacy flat schema?)")

    diffs = field_diff(a_doc, b_doc)
    compared = len(set(flatten(a_doc)) | set(flatten(b_doc)))

    if as_json:
        print(json.dumps({
            "a": str(a_path),
            "b": str(b_path),
            "doc_type": a_doc.get("doc_type") or b_doc.get("doc_type"),
            "fields_compared": compared,
            "disagreements": diffs,
            "warnings": warnings,
            "agree": not diffs,
        }, indent=2, sort_keys=True, default=str))
        return 0 if not diffs else 1

    print(f"compare --fields — {_label(a_doc, a_path)}  vs  {_label(b_doc, b_path)}")
    for w in warnings:
        print(f"  ! {w}")
    print(f"fields compared: {compared}\n")

    if not diffs:
        print("No field disagreements.")
        print("\nAgreement is not proof. Layer B (tools/parse-verify) checks whether the")
        print("figures can be internally consistent at all.")
        return 0

    width = max(len(d["path"]) for d in diffs)
    width = max(width, 5)
    print(f"{len(diffs)} field(s) disagree:\n")
    print(f"  {'field'.ljust(width)}  {a_path.name:>20}  {b_path.name:>20}   ")
    print(f"  {'-' * width}  {'-' * 20}  {'-' * 20}")
    for d in diffs:
        mark = "?" if d["kind"] == "one-sided" else "!"
        print(f"{mark} {d['path'].ljust(width)}  {_fmt(d['a']):>20}  {_fmt(d['b']):>20}")
        states = f"{d['a_state'] or '-'} / {d['b_state'] or '-'}"
        print(f"  {' ' * width}  states: {states}")

    print("\n! = both reads saw a value and they differ — read that box off the page image.")
    print("? = only one read saw it. Never let that become a zero; it is NOT_PRESENT or UNREADABLE.")
    print("\nenvelope.merge() applies this same comparison: agreements keep the text digits,")
    print("conflicts keep the vision value and list the path under _extraction.review_required.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare dollar figures across independent PDF text extractors.")
    ap.add_argument("pdf", nargs="?", help="PDF to read with every available text engine")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--expect", action="append", default=[],
                    help="a figure that must appear (repeatable); e.g. --expect -4168")
    ap.add_argument("--pngs", action="store_true",
                    help="also rasterize pages, for a vision pass as a further opinion")
    ap.add_argument("--fields", nargs=2, metavar=("A.json", "B.json"),
                    help="compare two parsed envelope documents field by field instead of a PDF")
    args = ap.parse_args()

    if args.fields:
        if args.pdf:
            print("--fields takes the two JSON documents; do not also pass a PDF", file=sys.stderr)
            return 2
        return run_fields(Path(args.fields[0]), Path(args.fields[1]), args.json)

    if not args.pdf:
        print("give a PDF to compare text engines, or --fields A.json B.json", file=sys.stderr)
        return 2

    pdf = Path(args.pdf)
    if not pdf.exists():
        print(f"no such file: {pdf}", file=sys.stderr)
        return 2

    results = run_engines(pdf)
    if len(results) < 2:
        got = ", ".join(results) or "none"
        print(f"need at least two engines to compare; available: {got}", file=sys.stderr)
        print("install poppler and/or pdfplumber", file=sys.stderr)
        return 2

    sets = {name: set(c) for name, c in results.items()}
    consensus = set.intersection(*sets.values())
    union = set.union(*sets.values())
    disputed = union - consensus

    # Which engines saw each disputed figure — that is the actionable part.
    disputed_detail = {
        f"{v:,.2f}": sorted(n for n in sets if v in sets[n])
        for v in sorted(disputed)
    }

    missing_expected: list[str] = []
    for e in args.expect:
        try:
            want = round(float(str(e).replace(",", "").replace("$", "")), 2)
        except ValueError:
            print(f"--expect value not numeric: {e}", file=sys.stderr)
            return 2
        if want not in union:
            missing_expected.append(f"{want:,.2f}")

    pngs: list[str] = []
    if args.pngs:
        try:
            from pdf_extract import rasterize_to_png  # local module
            import tempfile
            pngs = [str(p) for p in rasterize_to_png(pdf, Path(tempfile.mkdtemp()))]
        except Exception as exc:  # rasterization is a convenience, not the point
            print(f"rasterization skipped: {exc}", file=sys.stderr)

    ok = not disputed and not missing_expected

    if args.json:
        print(json.dumps({
            "pdf": str(pdf),
            "engines": sorted(results),
            "consensus_count": len(consensus),
            "disputed": disputed_detail,
            "missing_expected": missing_expected,
            "pngs": pngs,
            "agree": ok,
        }, indent=2))
        return 0 if ok else 1

    print(f"compare — {pdf.name}")
    print(f"engines: {', '.join(sorted(results))}")
    print(f"figures agreed by all engines: {len(consensus)}\n")

    if disputed_detail:
        print(f"{len(disputed_detail)} disputed figure(s) — each seen by some engines, not all:\n")
        for val, seen in disputed_detail.items():
            missing = sorted(set(results) - set(seen))
            print(f"  {val:>16}   seen by: {', '.join(seen)}")
            print(f"  {'':>16}   missed by: {', '.join(missing)}")
        print("\nA figure only one engine sees is usually a layout artifact — but if it is a")
        print("box value you intend to rely on, read it off the page image before using it.")
    else:
        print("No disagreement between engines.")

    if missing_expected:
        print(f"\nEXPECTED BUT NOT FOUND by any engine: {', '.join(missing_expected)}")

    if pngs:
        print(f"\nPage images for a vision pass ({len(pngs)}):")
        for p in pngs:
            print(f"  {p}")

    print("\nAgreement is not proof. Layer B (tools/parse-verify) checks whether the")
    print("figures can be internally consistent at all.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

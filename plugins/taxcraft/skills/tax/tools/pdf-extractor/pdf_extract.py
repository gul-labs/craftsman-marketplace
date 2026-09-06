#!/usr/bin/env python3
"""
PDF Extractor — the extraction ladder for the tax skill.

A tax document is read on rungs, cheapest and most exact first:

    rung 0  AcroForm fields   (`acroform.py`) — the issuer's own field values
    rung 1  rasterize → PNG   — vision reads the page; PRIMARY for form-shaped docs
    rung 2  `pdftotext -layout` → text, gated by `quality.py`
    rung 3  merge the two independent reads (`envelope.merge`)

The old order was text-first behind a "more than 50 characters" gate. That gate
passed `(cid:37)(cid:12)` soup from fonts with no ToUnicode map, and layout text
scrambles the column geometry of a W-2 or 1099 even when the characters are
right. So text is now scored by `quality.assess` before anyone believes it, and
`mode="form"` rasterizes unconditionally so vision gets the first read of any
boxed form, with the text pass kept as the independent cross-check.

Usage as a module:
    from pdf_extract import extract
    r = extract("doc.pdf", mode="form", doc_hint="W-2")
    r.acroform   # {field: value}, {} = no fields, None = rung 0 unavailable
    r.pngs       # page images for the vision read
    r.text       # layout text; present only when it is not garbage
    r.text_ok    # True only when the quality gate said "ok"
    r.quality    # QualityReport.as_dict()

Usage as a CLI:
    python3 pdf_extract.py doc.pdf                    # auto (unchanged default)
    python3 pdf_extract.py doc.pdf --mode form        # vision-primary, text too
    python3 pdf_extract.py doc.pdf --mode text        # text rung only
    python3 pdf_extract.py doc.pdf --hint W-2 --json  # full result as JSON
    python3 pdf_extract.py doc.pdf --force-image      # skip text, go to PNG
    python3 pdf_extract.py doc.pdf --pages 1-3 --dpi 300

Dependencies (cross-platform):
- pdftotext / pdftoppm / pdfinfo / pdffonts (poppler)
- optional: pypdf or pdftk for rung 0

  macOS: brew install poppler | Debian/Ubuntu: apt install poppler-utils
  Fedora: dnf install poppler-utils | Windows: choco install poppler

Nothing here writes inside the skill; scratch goes to `tempfile.mkdtemp()`.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import quality as _quality
except Exception:  # pragma: no cover - only in a broken install
    _quality = None  # type: ignore

try:
    import acroform as _acroform
except Exception:  # pragma: no cover - only in a broken install
    _acroform = None  # type: ignore


# A cheap short-circuit for *truly* empty output, so a blank page does not pay
# for a quality assessment. The real gate is `quality.assess()`; this constant
# is no longer the decision, only the trivial-case skip.
MIN_TEXT_CHARS = 50

# Density of non-whitespace text per kilobyte of file — below this suggests an
# image-heavy PDF that pdftotext failed on. Legacy heuristic, kept because
# `try_pdftotext()` still implements the old contract for older callers.
MIN_DENSITY_CHARS_PER_KB = 5

# Rasterization resolution. Forms get a little more: box digits are small and
# vision reads them straight off the pixels.
DEFAULT_DPI = 200
FORM_DPI = 220

MODES = ("auto", "text", "form")


@dataclass
class ExtractResult:
    """Unified result of a PDF extraction attempt."""
    mode: str  # "text" | "image" | "form" | "failed"
    text: Optional[str] = None
    pngs: list[str] = field(default_factory=list)
    pages_rasterized: Optional[str] = None  # e.g., "1-3" or "all"
    pdf_path: str = ""
    diagnostics: dict = field(default_factory=dict)
    # --- added by the PDF-reliability upgrade ---------------------------
    producer: Optional[str] = None          # PDF /Producer — keys layout templates
    creator: Optional[str] = None           # PDF /Creator
    pages: int = 0                          # page count (0 when unknown)
    acroform: Optional[dict] = None         # rung 0: {} = none, None = unavailable
    quality: Optional[dict] = None          # QualityReport.as_dict()
    doc_type: Optional[str] = None          # detected registry doc type
    text_ok: bool = False                   # True only when the gate said "ok"

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------

def raw_pdftotext(pdf_path: Path) -> Optional[str]:
    """`pdftotext -layout` output verbatim — no quality judgement at all.
    None only when the tool is missing or the run failed."""
    if not _have("pdftotext"):
        return None
    try:
        proc = _run(["pdftotext", "-layout", str(pdf_path), "-"], check=False)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def try_pdftotext(pdf_path: Path) -> Optional[str]:
    """Legacy gate: text if it clears the character-count and density heuristics.

    Kept intact because callers outside this module still use it. `extract()`
    no longer relies on it — `quality.assess` is the gate now.
    """
    text = raw_pdftotext(pdf_path)
    if text is None:
        return None
    non_ws = len(re.sub(r"\s+", "", text))
    if non_ws < MIN_TEXT_CHARS:
        return None
    try:
        size_kb = max(1, pdf_path.stat().st_size // 1024)
    except OSError:
        size_kb = 1
    if non_ws / size_kb < MIN_DENSITY_CHARS_PER_KB:
        # Sparse text vs file size suggests image-heavy PDF; fall back to image
        return None
    return text


# --------------------------------------------------------------------------
# Metadata
# --------------------------------------------------------------------------

def producer_info(pdf_path: str | Path) -> dict:
    """{"producer", "creator", "title", "pages", "encrypted"} via `pdfinfo`.

    Every key is always present; values are None / 0 / False when `pdfinfo` is
    absent or the PDF will not open. The producer string is what keys a vendor
    layout template, so it is worth capturing even when nothing reads it yet.
    """
    info: dict[str, Any] = {"producer": None, "creator": None, "title": None,
                            "pages": 0, "encrypted": False}
    pdf_path = Path(pdf_path)
    if not _have("pdfinfo") or not pdf_path.is_file():
        return info
    try:
        proc = _run(["pdfinfo", str(pdf_path)], check=False)
    except Exception:
        return info
    if proc.returncode != 0:
        return info
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "producer":
            info["producer"] = val or None
        elif key == "creator":
            info["creator"] = val or None
        elif key == "title":
            info["title"] = val or None
        elif key == "pages":
            try:
                info["pages"] = int(val)
            except ValueError:
                pass
        elif key == "encrypted":
            info["encrypted"] = not val.lower().startswith("no")
    return info


def pdf_page_count(pdf_path: Path) -> int:
    """Return page count using pdfinfo. Returns -1 if unavailable."""
    if not _have("pdfinfo"):
        return -1
    try:
        proc = _run(["pdfinfo", str(pdf_path)], check=False)
    except Exception:
        return -1
    for line in proc.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return -1
    return -1


# --------------------------------------------------------------------------
# Rasterization
# --------------------------------------------------------------------------

def parse_page_range(pages: str, total: int) -> list[int]:
    """Parse '1-3,5,7-9' into [1,2,3,5,7,8,9]. If pages is None or 'all', return range(1, total+1).

    Raises ValueError with a clear message if `pages` is malformed (non-numeric,
    empty range segment, etc.) — callers should catch this and report cleanly
    rather than let a bare traceback surface.
    """
    if not pages or pages == "all":
        return list(range(1, total + 1))
    out: list[int] = []
    for part in pages.split(","):
        part = part.strip()
        if not part:
            raise ValueError(f"Malformed --pages value {pages!r}: empty segment between commas")
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                out.extend(range(int(a), int(b) + 1))
            else:
                out.append(int(part))
        except ValueError as e:
            raise ValueError(
                f"Malformed --pages value {pages!r}: could not parse segment {part!r} ({e})"
            ) from e
    return sorted(set(out))


def rasterize_to_png(pdf_path: Path, out_dir: Path, pages: str = "all",
                     dpi: int = DEFAULT_DPI) -> list[Path]:
    """Rasterize PDF pages to PNG. Returns list of PNG paths in page order."""
    if not _have("pdftoppm"):
        raise RuntimeError("pdftoppm not found — install poppler (poppler-utils).")

    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / f"{pdf_path.stem}"

    # Determine page range
    total = pdf_page_count(pdf_path)
    if total < 0:
        total = 50  # fallback upper bound; pdftoppm handles gracefully
    page_list = parse_page_range(pages, total)

    # pdftoppm -png writes <prefix>-<n>.png directly — no separate convert step,
    # which also keeps this cross-platform (the old sips path was macOS-only).
    if page_list:
        first = min(page_list)
        last = max(page_list)
        try:
            _run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(first), "-l", str(last),
                  str(pdf_path), str(prefix)])
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            raise RuntimeError(
                f"pdftoppm failed on {pdf_path} (possibly corrupt or password-protected PDF)"
                + (f": {stderr}" if stderr else "")
            ) from e

    # Collect only the pages that were requested
    png_paths: list[Path] = []
    for png in sorted(out_dir.glob(f"{pdf_path.stem}-*.png")):
        # Extract page number from filename suffix, e.g. "<prefix>-03"
        try:
            pno = int(png.stem.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            continue
        if pno not in page_list:
            continue
        png_paths.append(png)

    return sorted(png_paths, key=lambda p: int(p.stem.rsplit("-", 1)[1]))


# --------------------------------------------------------------------------
# Rung 0 helpers
# --------------------------------------------------------------------------

def _read_acroform(pdf_path: Path) -> tuple[Optional[dict], Optional[str]]:
    if _acroform is None:
        return None, "acroform module unavailable"
    fields = _acroform.read_fields(pdf_path)
    return fields, _acroform.last_error


def _doc_type_from_acroform(fields: Optional[dict]) -> Optional[str]:
    """IRS fillable forms name their widgets after the printed form, and the
    filled values carry the form's own vocabulary. Run the registry anchors over
    names and values together so rung 0 alone can name the document."""
    if not fields or _quality is None:
        return None
    blob = " ".join(list(fields.keys()) + [str(v) for v in fields.values()])
    try:
        detected, _ = _quality.detect_doc_type(blob)
    except Exception:
        return None
    return detected


def _assess(text: str, doc_hint: Optional[str], pdf_path: Path):
    if _quality is None:
        return None
    try:
        return _quality.assess(text, doc_hint=doc_hint, pdf_path=pdf_path)
    except Exception:
        return None


# --------------------------------------------------------------------------
# extract
# --------------------------------------------------------------------------

def extract(
    pdf_path: str | Path,
    *,
    force_image: bool = False,
    pages: str = "all",
    dpi: Optional[int] = None,
    out_dir: Optional[str | Path] = None,
    mode: str = "auto",
    doc_hint: Optional[str] = None,
) -> ExtractResult:
    """
    Extract content from a PDF, choosing rungs by what the document actually is.

    Always, in every mode: `producer_info()` and the rung-0 AcroForm dump.

    mode="auto" (default, backward compatible)
        Read text and score it. Verdict "ok" → mode "text". Verdict "suspect" →
        keep the text but set `text_ok=False` AND rasterize, so the caller holds
        both reads to merge. Verdict "garbage" → discard the text and rasterize
        (mode "image"). `force_image=True` skips the text rung entirely.

    mode="form"
        ALWAYS rasterize — vision is the primary read for boxed forms — and also
        attempt text as the independent cross-check. Result mode is "form";
        `text` is populated only when the verdict is not "garbage".

    mode="text"
        Text rung only; never rasterizes. For prose (letters, statements, returns).

    Parameters
    ----------
    pdf_path : path to the PDF
    force_image : skip text extraction, go straight to rasterization
    pages : "all" or "1-3,5,7-9" style range
    dpi : rasterization resolution; default 200, or 220 in form mode
    out_dir : where to place PNG files (default: a fresh system temp dir)
    mode : "auto" | "text" | "form"
    doc_hint : expected registry doc type (e.g. "W-2"); tightens the quality gate

    Returns
    -------
    ExtractResult — see the dataclass. `mode="failed"` with `diagnostics` when
    nothing could be extracted at all.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {', '.join(MODES)}")

    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        return ExtractResult(mode="failed", pdf_path=str(pdf_path),
                             diagnostics={"error": "file not found"})

    result = ExtractResult(pdf_path=str(pdf_path), mode="failed")

    # ---- always: metadata + rung 0 -------------------------------------
    info = producer_info(pdf_path)
    result.producer = info["producer"]
    result.creator = info["creator"]
    result.pages = info["pages"] or 0
    if info["encrypted"]:
        result.diagnostics["encrypted"] = True

    fields, acro_err = _read_acroform(pdf_path)
    result.acroform = fields
    if fields:
        result.diagnostics["acroform_fields"] = len(fields)
    elif fields is None and acro_err:
        result.diagnostics["acroform_unavailable"] = acro_err
    result.doc_type = _doc_type_from_acroform(fields)

    # ---- text rung ------------------------------------------------------
    text: Optional[str] = None
    verdict: Optional[str] = None
    if not force_image:
        raw = raw_pdftotext(pdf_path)
        if raw is None:
            result.diagnostics["text_error"] = "pdftotext unavailable or failed"
            verdict = "garbage"
        else:
            non_ws = len(re.sub(r"\s+", "", raw))
            report = _assess(raw, doc_hint, pdf_path)
            if report is not None:
                result.quality = report.as_dict()
                verdict = report.verdict
                if report.detected_doc_type:
                    result.doc_type = result.doc_type or report.detected_doc_type
            else:
                # No quality module at all: fall back to the legacy count.
                verdict = "ok" if non_ws >= MIN_TEXT_CHARS else "garbage"
            # Cheap short-circuit: nothing to judge, whatever the scorer said.
            if non_ws < MIN_TEXT_CHARS:
                verdict = "garbage"
                result.diagnostics["text_chars"] = non_ws
            if verdict != "garbage":
                text = raw
                result.text = raw
                result.diagnostics["text_chars"] = len(raw)
            result.text_ok = verdict == "ok"
    if doc_hint:
        result.diagnostics["doc_hint"] = doc_hint
        result.doc_type = result.doc_type or doc_hint
    if verdict:
        result.diagnostics["text_verdict"] = verdict

    # ---- decide whether to rasterize -----------------------------------
    if mode == "text":
        if text:
            result.mode = "text"
        else:
            result.diagnostics.setdefault(
                "error", "no usable text, and mode=text never rasterizes")
        return result

    need_raster = (
        mode == "form"                        # vision is primary for forms
        or force_image
        or verdict in (None, "garbage")       # nothing trustworthy to read
        or verdict == "suspect"               # keep the text, get a second read
    )
    if not need_raster:
        result.mode = "text"
        return result

    eff_dpi = dpi if dpi is not None else (FORM_DPI if mode == "form" else DEFAULT_DPI)
    out_dir_p = Path(tempfile.mkdtemp(prefix="pdfextract_")) if out_dir is None else Path(out_dir)
    try:
        pngs = rasterize_to_png(pdf_path, out_dir_p, pages=pages, dpi=eff_dpi)
    except (RuntimeError, ValueError) as e:
        result.diagnostics["rasterize_error"] = str(e)
        # A suspect-but-present text read is still worth handing back.
        if text:
            result.mode = "form" if mode == "form" else "text"
        return result

    if not pngs:
        result.diagnostics["error"] = "rasterization produced no images"
        if text:
            result.mode = "form" if mode == "form" else "text"
        return result

    result.pngs = [str(p) for p in pngs]
    result.pages_rasterized = pages
    result.diagnostics["png_count"] = len(pngs)
    result.diagnostics["dpi"] = eff_dpi
    result.diagnostics["out_dir"] = str(out_dir_p)

    if mode == "form":
        result.mode = "form"
    elif text:
        # auto + "suspect": both reads are populated, and the mode stays "text"
        # so existing callers keep their branch. `text_ok=False` is the signal.
        result.mode = "text"
    else:
        result.mode = "image"
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract text and/or page images from a PDF, gated on text quality.")
    ap.add_argument("pdf", help="Path to PDF file")
    ap.add_argument("--force-image", action="store_true", help="Skip text extraction, go straight to PNG")
    ap.add_argument("--pages", default="all", help="'all' or range like '1-3,5,7-9' (default: all)")
    ap.add_argument("--dpi", type=int, default=None,
                    help=f"Rasterization DPI (default {DEFAULT_DPI}; {FORM_DPI} in --mode form)")
    ap.add_argument("--out-dir", default=None, help="PNG output directory (default: tmp)")
    ap.add_argument("--mode", choices=MODES, default="auto",
                    help="auto = text behind the quality gate; form = always rasterize + text; "
                         "text = text rung only")
    ap.add_argument("--hint", default=None, help="Expected doc type, e.g. W-2 — tightens the quality gate")
    ap.add_argument("--json", action="store_true", help="Print the whole ExtractResult as JSON")
    args = ap.parse_args()

    try:
        parse_page_range(args.pages, total=1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    result = extract(args.pdf, force_image=args.force_image, pages=args.pages,
                     dpi=args.dpi, out_dir=args.out_dir, mode=args.mode,
                     doc_hint=args.hint)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True, default=str))
        return 0 if result.mode != "failed" else 1

    if result.mode == "failed":
        print(f"# Extraction failed: {result.diagnostics}", file=sys.stderr)
        return 1

    if result.acroform:
        print(f"# rung 0: {len(result.acroform)} AcroForm field(s) — exact issuer values",
              file=sys.stderr)
        for k in sorted(result.acroform):
            print(f"#   {k} = {result.acroform[k]}", file=sys.stderr)
    if result.doc_type:
        print(f"# doc type: {result.doc_type}", file=sys.stderr)
    if result.quality and result.quality.get("verdict") != "ok":
        print(f"# text quality: {result.quality['verdict']}", file=sys.stderr)
        for reason in result.quality.get("reasons", []):
            print(f"#   - {reason}", file=sys.stderr)

    if result.pngs:
        if result.mode == "form":
            label = "form mode — vision reads these first"
        elif result.text:
            label = "text is suspect — cross-check it against these"
        else:
            label = "text was not trustworthy — read these instead"
        print(f"# {len(result.pngs)} page image(s) ({label}):", file=sys.stderr)
        for png in result.pngs:
            print(png)
        print("# Feed each PNG path above into Claude's Read tool to extract content via vision.",
              file=sys.stderr)

    if result.text:
        if result.pngs:
            print("# --- layout text (cross-check only) ---", file=sys.stderr)
        sys.stdout.write(result.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

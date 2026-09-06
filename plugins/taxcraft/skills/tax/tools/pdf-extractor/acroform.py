#!/usr/bin/env python3
"""
acroform — rung 0 of the extraction ladder: read a PDF's own form fields.

IRS fillable forms, many payroll-provider W-2s and a good share of issuer 1099s
are AcroForm PDFs: the printed boxes are real form widgets carrying the exact
string the issuer typed. When those fields are present there is nothing to
infer — no layout to reconstruct, no digit for vision to misread. That is why
this runs before text and before vision.

Engines, in order of preference:

    pypdf   optional pip package; `PdfReader(...).get_fields()`
    pdftk   optional binary; `pdftk <pdf> dump_data_fields_utf8`

Neither is required. With no engine available `read_fields` returns None and
`last_error` says why — that is a "rung not available", not a failure, and the
caller simply climbs to the next rung.

Three return values, and the difference between them matters:

    None  — could not look (no engine, broken/encrypted PDF). Unknown.
    {}    — looked, and the PDF has no form fields. A real answer.
    {...} — {field name: value as string}; fields with empty values are dropped
            because an unfilled widget is not an observed zero.

This module never raises on a broken PDF and never writes anything.

CLI:
    python3 acroform.py file.pdf
    python3 acroform.py file.pdf --json
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Set by read_fields()/has_engine() when a rung could not be used. Read it for
# the reason behind a None; it is diagnostic text, never control flow.
last_error: Optional[str] = None

_TIMEOUT = 60


# --------------------------------------------------------------------------
# Engine probes
# --------------------------------------------------------------------------

def _have_pypdf() -> bool:
    try:
        import pypdf  # type: ignore  # noqa: F401
    except Exception:
        return False
    return True


def _have_pdftk() -> bool:
    return shutil.which("pdftk") is not None


def has_engine() -> Optional[str]:
    """Name the engine that would be used, or None when the rung is unavailable."""
    global last_error
    if _have_pypdf():
        return "pypdf"
    if _have_pdftk():
        return "pdftk"
    last_error = "no AcroForm engine available (install pypdf, or pdftk on PATH)"
    return None


# --------------------------------------------------------------------------
# pypdf
# --------------------------------------------------------------------------

def _stringify(value) -> str:
    """A pypdf field value can be a text string, a name object (/Yes, /Off) or a
    list for a multi-select. Flatten all of them to plain text."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_stringify(v) for v in value if _stringify(v))
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return ""
    text = str(value)
    # Name objects arrive as "/Yes"; keep the token, drop the solidus.
    if text.startswith("/"):
        text = text[1:]
    return text.strip()


def _read_pypdf(pdf_path: Path) -> Optional[dict[str, str]]:
    global last_error
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:
        last_error = f"pypdf import failed: {exc}"
        return None
    try:
        reader = PdfReader(str(pdf_path))
        if getattr(reader, "is_encrypted", False):
            # An empty user password is common on issuer PDFs; try it once.
            try:
                reader.decrypt("")
            except Exception:
                pass
        fields = reader.get_fields()
    except Exception as exc:
        last_error = f"pypdf could not read {pdf_path.name}: {type(exc).__name__}: {exc}"
        return None
    if not fields:
        return {}
    out: dict[str, str] = {}
    for name, obj in fields.items():
        try:
            raw = obj.get("/V") if hasattr(obj, "get") else obj
        except Exception:
            raw = None
        text = _stringify(raw)
        if text:
            out[str(name)] = text
    return out


# --------------------------------------------------------------------------
# pdftk
# --------------------------------------------------------------------------

def _parse_pdftk_dump(dump: str) -> dict[str, str]:
    """`dump_data_fields_utf8` emits `---`-separated blocks of `Key: value` lines.

    A field can carry several FieldValue lines (multi-select); they are joined.
    """
    out: dict[str, str] = {}
    name: Optional[str] = None
    values: list[str] = []

    def flush() -> None:
        if name:
            text = ", ".join(v for v in values if v).strip()
            if text:
                out[name] = text

    for line in dump.splitlines():
        line = line.rstrip("\r")
        if line.strip() == "---":
            flush()
            name, values = None, []
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "FieldName":
            name = val
        elif key == "FieldValue":
            values.append(val)
    flush()
    return out


def _read_pdftk(pdf_path: Path) -> Optional[dict[str, str]]:
    global last_error
    if not _have_pdftk():
        last_error = "pdftk not on PATH"
        return None
    try:
        proc = subprocess.run(
            ["pdftk", str(pdf_path), "dump_data_fields_utf8"],
            capture_output=True, text=True, timeout=_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        last_error = f"pdftk failed on {pdf_path.name}: {exc}"
        return None
    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        last_error = f"pdftk exited {proc.returncode} on {pdf_path.name}" + (
            f": {err[-1]}" if err else "")
        return None
    return _parse_pdftk_dump(proc.stdout)


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def read_fields(pdf_path: Path) -> Optional[dict[str, str]]:
    """{field name: value} for a fillable PDF, {} when it has no fields,
    None when no engine could read it (reason in `last_error`)."""
    global last_error
    last_error = None
    pdf_path = Path(pdf_path)
    if not pdf_path.is_file():
        last_error = f"no such file: {pdf_path}"
        return None

    if _have_pypdf():
        fields = _read_pypdf(pdf_path)
        if fields is not None:
            return fields
        # pypdf choked; a second parser sometimes still gets there.
        pypdf_error = last_error
        fields = _read_pdftk(pdf_path)
        if fields is not None:
            last_error = None
            return fields
        last_error = f"{pypdf_error}; {last_error}"
        return None

    if _have_pdftk():
        return _read_pdftk(pdf_path)

    last_error = "no AcroForm engine available (install pypdf, or pdftk on PATH)"
    return None


def main() -> int:  # pragma: no cover - thin CLI
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Dump a PDF's AcroForm fields (rung 0).")
    ap.add_argument("pdf")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    fields = read_fields(Path(args.pdf))
    if args.json:
        print(json.dumps({
            "pdf": args.pdf,
            "engine": has_engine(),
            "fields": fields,
            "error": last_error,
        }, indent=2, sort_keys=True))
        return 0 if fields else 1

    if fields is None:
        print(f"could not read form fields: {last_error}", file=sys.stderr)
        return 2
    if not fields:
        print(f"{Path(args.pdf).name}: no AcroForm fields (engine: {has_engine()})")
        return 1
    width = max(len(k) for k in fields)
    print(f"{Path(args.pdf).name}: {len(fields)} filled field(s) via {has_engine()}")
    for k in sorted(fields):
        print(f"  {k:<{width}}  {fields[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

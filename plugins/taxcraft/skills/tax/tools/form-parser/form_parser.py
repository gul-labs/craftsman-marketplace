#!/usr/bin/env python3
"""
form_parser — every registry information return (W-2, 1099-*, 1098-*, 1095-A,
5498-*, SSA-1099, W-2G) → one schema_version 2 envelope document.

The rungs, in the order the spec fixed them:

    0  AcroForm fields      exact when the issuer shipped a fillable PDF
    1  vision               PRIMARY for form-shaped docs; the model reads the
                            page images and fills `--vision-prompt`'s skeleton
    2  `pdftotext -layout`  anchor parse, gated by `quality.assess`
    3  merge                `envelope.merge(text_doc, vision_doc)`
    4  invariants           `invariants.evaluate` over the merged document

Rung 1 cannot run inside a script — a model has to look at the pixels. So the
tool is two-pass by design:

    form_parser.py w2.pdf --vision-prompt      # → prompt + PNG paths
    (the model reads the PNGs, writes vision.json)
    form_parser.py w2.pdf --merge vision.json --write

A one-pass text-only run is legitimate for a clean digital form and says so in
`_extraction.engines`. What it never does is invent: a box the text pass did not
find is NOT_PRESENT, a box whose label was found but whose value would not parse
is UNREADABLE, and neither is ever a zero.

Pure stdlib. Writes nothing except where `--write` is told to.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
_EXTRACTOR = _HERE.parent / "pdf-extractor"
for _p in (str(_HERE), str(_EXTRACTOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import envelope  # noqa: E402
import quality  # noqa: E402
from doc_types import REGISTRY, FORM_PARSER_TYPES, Box, DocType, get as get_doc_type  # noqa: E402
import invariants as invariants_mod  # noqa: E402

SCHEMA_VERSION = 2

# --------------------------------------------------------------------------
# Token regexes
# --------------------------------------------------------------------------

# A "formatted" money token: has a decimal, a thousands group, or a currency
# sign. Preferred over a bare integer so a stray "1250" inside the label text
# ("Unrecap. Sec. 1250 gain") never wins over the printed amount.
_MONEY_STRICT = re.compile(
    r"\(?-?\$?\s?(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+\.\d{2})\)?")
_MONEY_LOOSE = re.compile(r"\(?-?\$?\s?\d+(?:\.\d{1,2})?\)?")
_CHECK_GLYPH = re.compile(r"\[\s*[xX✓☒]\s*\]|[☒✓✔]|(?<![A-Za-z])[xX](?![A-Za-z])")
_STATE_CODE = re.compile(r"\b([A-Z]{2})\b")
_BOX12_LINE = re.compile(r"\b12[a-d]\s+([A-Z]{1,2})\s+\$?([\d,]+\.\d\d)")
_CODE_PAIR = re.compile(r"\b([A-Z][A-Z0-9./-]{0,11})\s+\$?(-?[\d,]+\.\d\d)")
_YEAR_NEAR = re.compile(
    r"(?:Form\b|OMB\b|Tax year\b|calendar year\b|For\s+calendar\b)[^\n]{0,80}?\b(20\d\d)\b",
    re.IGNORECASE)


def _money_tokens(s: str) -> list[float]:
    """Amounts on a line, left to right. Formatted tokens (a decimal, a
    thousands group, a currency sign) are preferred wholesale over bare
    integers, so "Unrecap. Sec. 1250 gain    300.00" reads 300.00, not 1250."""
    for rx in (_MONEY_STRICT, _MONEY_LOOSE):
        vals = [to_number(m.group(0)) for m in rx.finditer(s)]
        vals = [v for v in vals if v is not None]
        if vals:
            return vals
    return []


def _column_value(rest: str) -> str:
    """Text to the right of a label. `pdftotext -layout` keeps the gap between
    a label's column and its value's column, so a run of three or more spaces is
    the column break; what follows the last one is the value, and a label that
    simply continues past the pattern ("...name, address, and ZIP code") is not
    mistaken for it."""
    parts = [p for p in re.split(r"\s{3,}", rest) if p.strip()]
    if not parts:
        return ""
    return parts[-1].strip(" :\t")


class UsageError(Exception):
    """Exit 2: the caller asked for something this tool cannot do."""


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def to_number(tok: str) -> Optional[float]:
    """'1,234.56' / '$1,234.56' / '(1,234.56)' → float. None when unparsable."""
    s = tok.strip().replace("$", "").replace(",", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if s.startswith("-"):
        neg, s = True, s[1:]
    if not s or not re.fullmatch(r"\d+(?:\.\d+)?", s):
        return None
    v = float(s)
    return -v if neg else v


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_metadata(path: Path) -> dict:
    """Producer / Creator / page count via pdfinfo. {} when poppler is absent."""
    out: dict = {}
    if not shutil.which("pdfinfo"):
        return out
    try:
        proc = subprocess.run(["pdfinfo", str(path)], capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return out
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip().lower(), v.strip()
        if k in ("producer", "creator", "title"):
            out[k] = v
        elif k == "pages":
            try:
                out["page_count"] = int(v)
            except ValueError:
                pass
    return out


# --------------------------------------------------------------------------
# Rung 0 — AcroForm
# --------------------------------------------------------------------------

def has_acroform(path: Path) -> bool:
    """Cheap pre-check so a PDF with no form fields never pays for a pypdf
    import or a `pdftk` process — which is most PDFs, most of the time."""
    try:
        with path.open("rb") as fh:
            return b"/AcroForm" in fh.read()
    except OSError:
        return False


def read_acroform(path: Path) -> Optional[dict]:
    """{field name: value} or None. Tries the extractor's `acroform.py`, then
    pypdf, then pdftk. Every rung is optional; none of them raise."""
    if not has_acroform(path):
        return None
    try:  # the pdf-extractor may ship a dedicated dumper
        import acroform as _acro  # type: ignore
        for fn in ("dump_fields", "fields", "read_fields"):
            f = getattr(_acro, fn, None)
            if callable(f):
                got = f(path)
                if isinstance(got, dict) and got:
                    return got
    except Exception:
        pass
    try:
        from pypdf import PdfReader  # type: ignore
        fields = PdfReader(str(path)).get_fields() or {}
        out = {}
        for name, spec in fields.items():
            val = spec.get("/V") if isinstance(spec, dict) else None
            out[str(name)] = None if val is None else str(val)
        if out:
            return out
    except Exception:
        pass
    if shutil.which("pdftk"):
        try:
            proc = subprocess.run(["pdftk", str(path), "dump_data_fields"],
                                  capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode == 0 and proc.stdout.strip():
            out, cur = {}, {}
            for line in proc.stdout.splitlines() + ["---"]:
                if line.startswith("---"):
                    if cur.get("FieldName"):
                        out[cur["FieldName"]] = cur.get("FieldValue")
                    cur = {}
                elif ":" in line:
                    k, v = line.split(":", 1)
                    cur[k.strip()] = v.strip()
            if out:
                return out
    return None


def map_acroform(fields: dict, dt: DocType) -> tuple[dict, dict, list[str]]:
    """Match AcroForm field names against box ids and labels.

    IRS fillable forms name their widgets `f1_09[0]`, which matches nothing —
    that is the point of returning the unmapped names rather than guessing.
    Returns (identity envelopes, box envelopes, unmapped field names).
    """
    by_key: dict[str, Box] = {}
    for b in (*dt.identity, *dt.boxes):
        by_key[_norm(b.id)] = b
        by_key.setdefault(_norm(b.label), b)
        by_key.setdefault(_norm(b.id.replace("box_", "box ")), b)
    ident: dict[str, dict] = {}
    boxes: dict[str, dict] = {}
    unmapped: list[str] = []
    id_ids = {b.id for b in dt.identity}
    for name, raw in fields.items():
        key = _norm(re.sub(r"\[\d+\]$", "", str(name)).split(".")[-1])
        box = by_key.get(key)
        if box is None:
            unmapped.append(str(name))
            continue
        env = _envelope_for(box, None if raw is None else str(raw), page=1, engine="acroform")
        (ident if box.id in id_ids else boxes)[box.id] = env
    return ident, boxes, sorted(unmapped)


def _envelope_for(box: Box, raw: Optional[str], *, page: Optional[int],
                  engine: str = "text") -> dict:
    """Coerce one raw string into the envelope its box kind calls for."""
    if raw is None or not str(raw).strip():
        return envelope.make(None, "NOT_PRESENT", box=box.id, page=page)
    s = str(raw).strip()
    if box.kind == "money":
        v = to_number(s)
        if v is None:
            return envelope.make(None, "UNREADABLE", box=box.id, page=page)
        return envelope.make(v, page=page, box=box.id)
    if box.kind == "flag":
        truthy = s.lower() in ("1", "true", "yes", "on", "x", "/on", "/yes", "checked")
        return envelope.make(truthy, page=page, box=box.id)
    if box.kind == "state":
        m = _STATE_CODE.search(s.upper())
        if not m:
            return envelope.make(None, "UNREADABLE", box=box.id, page=page)
        return envelope.make(m.group(1), page=page, box=box.id)
    if box.kind == "codes":
        pairs = [{"code": c, "amount": to_number(a)} for c, a in _CODE_PAIR.findall(s)]
        if not pairs:
            return envelope.make(None, "UNREADABLE", box=box.id, page=page)
        return envelope.make(pairs, page=page, box=box.id)
    return envelope.make(s, page=page, box=box.id)


# --------------------------------------------------------------------------
# Layout text model
# --------------------------------------------------------------------------

class Line:
    __slots__ = ("page", "idx", "text")

    def __init__(self, page: int, idx: int, text: str) -> None:
        self.page, self.idx, self.text = page, idx, text


def split_lines(text: str) -> list[Line]:
    """`pdftotext -layout` output → lines carrying their 1-based page number.
    Page breaks are form feeds, which is how poppler separates pages."""
    out: list[Line] = []
    for pno, page in enumerate(text.split("\f"), start=1):
        for i, raw in enumerate(page.split("\n")):
            out.append(Line(pno, i, raw.rstrip()))
    return out


def split_copies(lines: list[Line], dt: DocType) -> list[list[Line]]:
    """W-2 prints Copy B/C/2/2 of the same figures. Each copy is its own region,
    anchored on the printed form title; the caller votes across them."""
    if dt.copies_per_page <= 1:
        return [lines]
    anchor = re.compile(re.escape(dt.title), re.IGNORECASE)
    starts = [i for i, ln in enumerate(lines) if anchor.search(ln.text)]
    if len(starts) < 2:
        return [lines]
    regions = []
    bounds = starts + [len(lines)]
    # A copy starts a little above its title line (the header row sits above it).
    for a, b in zip(bounds, bounds[1:]):
        a = max(0, a - 6)
        regions.append(lines[a:b])
    return [r for r in regions if r]


# --------------------------------------------------------------------------
# The text pass
# --------------------------------------------------------------------------

class TextReader:
    def __init__(self, lines: list[Line], dt: DocType,
                 overrides: Optional[dict] = None, value_side: str = "right") -> None:
        self.lines = lines
        self.dt = dt
        self.overrides = overrides or {}
        self.value_side = value_side
        # (page, line, label column) → how many values have already been taken
        # off that label. A form line can carry several columns of the same
        # label (1095-A prints premium / SLCSP / advance credit on one row), and
        # two boxes can share a pattern (a consolidated 1099 withholds twice).
        self.consumed: dict[tuple[int, int, int], int] = {}
        self._normed: list[Optional[str]] = [None] * len(lines)

    def normed(self, i: int) -> str:
        """`_norm` of a line, computed once. The label tiebreak below asks for
        it once per box per line, which is thousands of calls on a four-copy
        W-2 and the single hottest thing in the parse."""
        v = self._normed[i]
        if v is None:
            v = _norm(self.lines[i].text)
            self._normed[i] = v
        return v

    def patterns_for(self, box: Box) -> tuple[str, ...]:
        ov = self.overrides.get(box.id)
        if ov:
            return tuple(ov)
        return box.patterns or (re.escape(box.label),)

    def candidates(self, box: Box) -> list[tuple[int, int, int]]:
        """(line index, label start col, label end col), best first.

        Best = the line that also carries the box's printed label verbatim.
        Two boxes on one form can share a pattern ("Federal income tax withheld"
        on a consolidated 1099); the label tiebreak plus the claim ledger below
        keeps them off each other's value.
        """
        want = _norm(box.label)
        found: list[tuple[int, int, int, int]] = []
        for pat in self.patterns_for(box):
            try:
                rx = re.compile(pat, re.IGNORECASE)
            except re.error:
                continue
            for i, ln in enumerate(self.lines):
                m = rx.search(ln.text)
                if not m:
                    continue
                score = 0 if want and want in self.normed(i) else 1
                found.append((score, i, m.start(), m.end()))
            if found:
                break
        found.sort()
        return [(i, a, b) for _, i, a, b in found]

    def _key(self, idx: int, start: int) -> tuple[int, int, int]:
        return (self.lines[idx].page, idx, start)

    def read(self, box: Box) -> dict:
        if getattr(box, "text_unreliable", False):
            # The registry says a line-local match cannot tell this box from its
            # twin elsewhere on the form. Reading the wrong section's number is
            # worse than reading nothing, because it looks exactly like a right
            # answer. Leave it for vision or AcroForm.
            return envelope.make(None, "UNREADABLE", box=box.id)
        cands = self.candidates(box)
        if not cands:
            return envelope.make(None, "NOT_PRESENT", box=box.id)
        if box.kind == "flag":
            return self._read_flag(box, cands)
        unreadable = None
        for idx, start, end in cands:
            key = self._key(idx, start)
            n = self.consumed.get(key, 0)
            if n and box.kind != "money":
                continue  # a non-money label yields one value, and it is taken
            env = self._value_at(box, idx, start, end, n)
            if envelope.is_present(env):
                self.consumed[key] = n + 1
                return env
            unreadable = unreadable or env
        return unreadable or envelope.make(None, "UNREADABLE", box=box.id,
                                           page=self.lines[cands[0][0]].page)

    def _read_flag(self, box: Box, cands: list[tuple[int, int, int]]) -> dict:
        """A checkbox label also appears in the form's own prose ("HSA" is in the
        1099-SA title). Only a glyph proves a box is ticked, so every candidate
        is searched for one before any of them is allowed to answer "unticked"."""
        for idx, start, end in cands:
            ln = self.lines[idx]
            if _CHECK_GLYPH.search(ln.text[end:]):
                self.consumed[self._key(idx, start)] = 1
                return envelope.make(True, page=ln.page, box=box.id)
            # Some forms print the box to the LEFT of its caption. Only the few
            # columns immediately before it count; a glyph further away belongs
            # to a different row, and reading it here would tick the wrong box.
            if _CHECK_GLYPH.search(ln.text[max(0, start - 10):start]):
                self.consumed[self._key(idx, start)] = 1
                return envelope.make(True, page=ln.page, box=box.id)
        for idx, start, _end in cands:
            key = self._key(idx, start)
            if self.consumed.get(key):
                continue
            self.consumed[key] = 1
            return envelope.make(False, page=self.lines[idx].page, box=box.id)
        return envelope.make(False, page=self.lines[cands[0][0]].page, box=box.id)

    # -- per-kind readers ---------------------------------------------------

    def _value_at(self, box: Box, idx: int, start: int, end: int, n: int = 0) -> dict:
        ln = self.lines[idx]
        rest = ln.text[end:]
        page = ln.page
        if box.kind == "money":
            v = self._money(idx, start, end, n)
            if v is None:
                return envelope.make(None, "UNREADABLE", box=box.id, page=page)
            return envelope.make(v, page=page, box=box.id)
        if box.kind == "state":
            m = _STATE_CODE.search(rest)
            if not m:
                return envelope.make(None, "UNREADABLE", box=box.id, page=page)
            return envelope.make(m.group(1), page=page, box=box.id)
        if box.kind == "codes":
            pairs = self._codes(box, idx, rest)
            if not pairs:
                return envelope.make(None, "UNREADABLE", box=box.id, page=page)
            return envelope.make(pairs, page=page, box=box.id)
        # text / id / date / code
        val = _column_value(rest)
        if not val:
            nxt = self.lines[idx + 1].text[start:] if idx + 1 < len(self.lines) else ""
            val = _column_value(nxt)
        if not val:
            return envelope.make(None, "UNREADABLE", box=box.id, page=page)
        return envelope.make(val, page=page, box=box.id)

    def _money(self, idx: int, start: int, end: int, n: int = 0) -> Optional[float]:
        """The n-th amount to the right of the label; failing that (and only for
        the first read of that label) the first amount on the next line under
        the label's own column."""
        rest = self.lines[idx].text[end:]
        if self.value_side != "below":
            toks = _money_tokens(rest)
            if n < len(toks):
                return toks[n]
        if n:
            return None
        for j in (idx + 1, idx + 2):
            if j >= len(self.lines) or self.lines[j].page != self.lines[idx].page:
                break
            nxt = self.lines[j].text
            if not nxt.strip():
                continue
            for rx in (_MONEY_STRICT, _MONEY_LOOSE):
                for m in rx.finditer(nxt):
                    if m.start() >= start - 2:
                        v = to_number(m.group(0))
                        if v is not None:
                            return v
            break
        return None

    def _codes(self, box: Box, idx: int, rest: str) -> list[dict]:
        if box.id == "box_12":
            pairs = []
            for ln in self.lines:
                for code, amt in _BOX12_LINE.findall(ln.text):
                    v = to_number(amt)
                    if v is not None:
                        pairs.append({"code": code, "amount": v})
            if pairs:
                return pairs
        out: list[dict] = []
        for code, amt in _CODE_PAIR.findall(rest):
            v = to_number(amt)
            if v is not None:
                out.append({"code": code, "amount": v})
        for j in range(idx + 1, min(idx + 4, len(self.lines))):
            m = re.match(r"\s*([A-Z][A-Z0-9./-]{0,11})\s+\$?(-?[\d,]+\.\d\d)\s*$",
                         self.lines[j].text)
            if not m:
                break
            v = to_number(m.group(2))
            if v is not None:
                out.append({"code": m.group(1), "amount": v})
        return out


def find_tax_year(lines: list[Line], dt: DocType) -> Optional[int]:
    """Never invented. A year is only taken from a line that also carries a
    form-identifying word, and only in the range a tax form can carry."""
    flat = "\n".join(ln.text for ln in lines)
    cands = [int(y) for y in _YEAR_NEAR.findall(flat)]
    title_rx = re.compile(re.escape(dt.title[:40]) + r"[^\n]{0,80}?\b(20\d\d)\b", re.IGNORECASE)
    cands += [int(y) for y in title_rx.findall(flat)]
    cands = [y for y in cands if 2000 <= y <= 2099]
    if not cands:
        return None
    return max(set(cands), key=cands.count)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

def load_templates() -> list[dict]:
    out = []
    tdir = _HERE / "templates"
    if not tdir.is_dir():
        return out
    for p in sorted(tdir.glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            data.setdefault("_name", p.name)
            out.append(data)
    return out


def pick_template(meta: dict, doc_type: Optional[str]) -> Optional[dict]:
    """First template whose `match` regexes hit this PDF's producer/creator."""
    for tpl in load_templates():
        match = tpl.get("match") or {}
        if not match:
            continue
        ok = True
        for key in ("producer", "creator"):
            pat = match.get(key)
            if not pat:
                continue
            if not re.search(pat, meta.get(key, "") or "", re.IGNORECASE):
                ok = False
                break
        if not ok:
            continue
        if tpl.get("doc_type") and doc_type and tpl["doc_type"] != doc_type:
            continue
        return tpl
    return None


# --------------------------------------------------------------------------
# Document assembly
# --------------------------------------------------------------------------

def _vote(envs: list[dict], box_id: str, warnings: list[str]) -> dict:
    """One box read from several copies of the same form → the value the
    majority of copies agree on. A split keeps the first and says so."""
    present = [e for e in envs if envelope.is_present(e)]
    if not present:
        for state in ("UNREADABLE", "NOT_PRESENT"):
            for e in envs:
                if envelope.state_of(e) == state:
                    return e
        return envelope.make(None, "NOT_PRESENT", box=box_id)
    groups: list[tuple[dict, int]] = []
    for e in present:
        for i, (rep, n) in enumerate(groups):
            if envelope.values_agree(rep["value"], e["value"]):
                groups[i] = (rep, n + 1)
                break
        else:
            groups.append((e, 1))
    groups.sort(key=lambda g: -g[1])
    if len(groups) > 1 and groups[0][1] == groups[1][1]:
        warnings.append(
            f"{box_id}: printed copies disagree ({groups[0][0]['value']!r} vs "
            f"{groups[1][0]['value']!r}); kept the first copy's value — check the paper.")
    elif len(groups) > 1:
        warnings.append(
            f"{box_id}: {groups[1][1]} of {len(present)} copies read "
            f"{groups[1][0]['value']!r}; kept the majority {groups[0][0]['value']!r}.")
    return groups[0][0]


def _state_local(boxes: dict) -> list[dict]:
    """W-2 boxes 15–20 as the one state/local row the text pass can see."""
    row = {
        "state": boxes.get("box_15_state"),
        "state_id": boxes.get("box_15_employer_state_id"),
        "state_wages": boxes.get("box_16"),
        "state_wh": boxes.get("box_17"),
        "local_wages": boxes.get("box_18"),
        "local_wh": boxes.get("box_19"),
        "locality": boxes.get("box_20"),
    }
    row = {k: (v if envelope.is_envelope(v) else envelope.make(None, "NOT_PRESENT", box=k))
           for k, v in row.items()}
    if not any(envelope.is_present(v) for v in row.values()):
        return []
    return [row]


def build_text_doc(text: str, dt: DocType, *, template: Optional[dict] = None) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    lines = split_lines(text)
    overrides = (template or {}).get("box_patterns") or {}
    value_side = (template or {}).get("value_side", "right")
    regions = split_copies(lines, dt)

    readers = [TextReader(r, dt, overrides, value_side) for r in regions]
    ident: dict = {}
    boxes: dict = {}
    for b in dt.identity:
        ident[b.id] = _vote([r.read(b) for r in readers], b.id, warnings)
    for b in dt.boxes:
        boxes[b.id] = _vote([r.read(b) for r in readers], b.id, warnings)

    year = find_tax_year(lines, dt)
    if year is None:
        warnings.append("Tax year not printed anywhere the parser could see it — left null "
                        "rather than assumed; set it from the source document.")
    doc = {
        "doc_type": dt.name,
        "schema_version": SCHEMA_VERSION,
        "tax_year": year,
        "identity": ident,
        "boxes": boxes,
        "_extraction": {"engines": ["text"]},
        "warnings": warnings,
    }
    if dt.name == "W-2":
        doc["state_local"] = _state_local(boxes)
    if len(regions) > 1:
        doc["_extraction"]["copies_read"] = len(regions)
    return doc, warnings


def build_vision_doc(payload: dict, dt: DocType) -> dict:
    """A filled `vision_skeleton()` (plain values) → an envelope document."""
    ident: dict = {}
    boxes: dict = {}
    p_ident = payload.get("identity") or {}
    p_boxes = payload.get("boxes") or {}
    for b in dt.identity:
        ident[b.id] = _wrap_plain(b, p_ident.get(b.id))
    for b in dt.boxes:
        boxes[b.id] = _wrap_plain(b, p_boxes.get(b.id))
    year = payload.get("tax_year")
    try:
        year = int(year) if year is not None else None
    except (TypeError, ValueError):
        year = None
    doc = {
        "doc_type": dt.name,
        "schema_version": SCHEMA_VERSION,
        "tax_year": year,
        "identity": ident,
        "boxes": boxes,
        "_extraction": {"engines": ["vision"]},
        "warnings": [],
    }
    if dt.name == "W-2":
        doc["state_local"] = _state_local(boxes)
    return doc


def _wrap_plain(box: Box, value: Any) -> dict:
    """Plain JSON value → envelope. The page is unknown: the model read an
    image, not a line, so `source_anchor.page` stays null on purpose."""
    if value is None:
        return envelope.make(None, "NOT_PRESENT", box=box.id)
    if box.kind == "codes":
        if isinstance(value, list):
            if not value:
                return envelope.make(None, "NOT_PRESENT", box=box.id)
            pairs = []
            for item in value:
                if isinstance(item, dict):
                    pairs.append({"code": str(item.get("code", "")).strip(),
                                  "amount": to_number(str(item.get("amount", "")))
                                  if not isinstance(item.get("amount"), (int, float))
                                  else float(item["amount"])})
            return envelope.make(pairs, box=box.id)
        return envelope.make(None, "UNREADABLE", box=box.id)
    if box.kind == "money":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return envelope.make(float(value), box=box.id)
        v = to_number(str(value))
        return (envelope.make(v, box=box.id) if v is not None
                else envelope.make(None, "UNREADABLE", box=box.id))
    if box.kind == "flag":
        return envelope.make(bool(value), box=box.id)
    return envelope.make(str(value).strip(), box=box.id)


# --------------------------------------------------------------------------
# Doc-type resolution
# --------------------------------------------------------------------------

_ACROFORM_HINTS: tuple[tuple[str, str], ...] = (
    (r"wage[s]?[_ ]?and[_ ]?tax|employer.?s?[_ ]?state[_ ]?id|social[_ ]?security[_ ]?wages", "W-2"),
    (r"nonemployee[_ ]?comp", "1099-NEC"),
    (r"mortgage[_ ]?interest", "1098"),
    (r"gross[_ ]?distribution", "1099-R"),
    (r"interest[_ ]?income", "1099-INT"),
    (r"ordinary[_ ]?dividends", "1099-DIV"),
)


def detect_from_acroform(fields: Optional[dict]) -> Optional[str]:
    if not fields:
        return None
    blob = " ".join(str(k) for k in fields)
    for pat, name in _ACROFORM_HINTS:
        if re.search(pat, blob, re.IGNORECASE):
            return name
    # A registry type whose box ids and identity ids the field names mirror.
    best, best_hits = None, 0
    keys = {_norm(re.sub(r"\[\d+\]$", "", str(k)).split(".")[-1]) for k in fields}
    for name in FORM_PARSER_TYPES:
        dt = REGISTRY[name]
        ids = {_norm(b.id) for b in (*dt.identity, *dt.boxes)}
        hits = len(keys & ids)
        if hits > best_hits:
            best, best_hits = name, hits
    return best if best_hits >= 3 else None


def resolve_doc_type(explicit: Optional[str], acro: Optional[dict],
                     detected: Optional[str]) -> DocType:
    name = None
    if explicit:
        try:
            return _require_form_parser(get_doc_type(explicit))
        except KeyError as e:
            raise UsageError(str(e)) from e
    name = detect_from_acroform(acro) or detected
    if not name:
        raise UsageError(
            "Could not tell which form this is. Pass --type explicitly; known form-parser "
            "types: " + ", ".join(FORM_PARSER_TYPES))
    return _require_form_parser(get_doc_type(name))


def _require_form_parser(dt: DocType) -> DocType:
    if dt.parser != "form-parser":
        raise UsageError(
            f"{dt.name} is not parsed here — use tools/{dt.parser}/ for it "
            f"({dt.title}).")
    return dt


# --------------------------------------------------------------------------
# The pipeline
# --------------------------------------------------------------------------

def _extract(path: Path, doc_hint: Optional[str], mode: str = "auto"):
    """Call the extractor's mode/doc_hint contract, degrading to whatever the
    installed version actually supports.

    `mode="form"` always rasterizes, which is what the vision pass needs and
    what a text-only parse should not pay for; the default `"auto"` rasterizes
    only when the text is suspect or garbage — exactly when a vision read is
    the point."""
    from pdf_extract import extract as _ex  # noqa: WPS433
    try:
        return _ex(str(path), mode=mode, doc_hint=doc_hint)
    except TypeError:
        pass
    try:
        return _ex(str(path), mode=mode)
    except TypeError:
        pass
    return _ex(str(path))


def _rasterize(path: Path, res: Any) -> list[str]:
    pngs = list(getattr(res, "pngs", None) or [])
    if pngs:
        return pngs
    try:
        from pdf_extract import extract as _ex
        out = _ex(str(path), force_image=True)
        return list(getattr(out, "pngs", None) or [])
    except Exception:
        return []


def parse(pdf_path: str | Path, doc_type: Optional[str] = None, *,
          vision_json: Optional[dict] = None) -> dict:
    """PDF (+ optional vision read) → one schema_version 2 envelope document."""
    path = Path(pdf_path).expanduser()
    if not path.is_file():
        raise UsageError(f"no such file: {path}")

    res = _extract(path, doc_type)
    text = getattr(res, "text", None) or ""
    meta = {
        "producer": getattr(res, "producer", None) or "",
        "creator": getattr(res, "creator", None) or "",
        "page_count": getattr(res, "pages", None) or getattr(res, "page_count", None),
    }
    if not (meta["producer"] or meta["creator"] or meta["page_count"]):
        meta = pdf_metadata(path)   # an older extractor: read the metadata here
    producer = meta.get("producer") or None
    page_count = meta.get("page_count")

    qual = getattr(res, "quality", None)
    if isinstance(qual, dict):
        q_dict, verdict, detected = qual, qual.get("verdict", "ok"), qual.get("detected_doc_type")
    else:
        rep = quality.assess(text, doc_hint=doc_type, pdf_path=path)
        q_dict, verdict, detected = rep.as_dict(), rep.verdict, rep.detected_doc_type
    detected = getattr(res, "doc_type", None) or detected

    acro = getattr(res, "acroform", None)
    if not isinstance(acro, dict):
        acro = read_acroform(path)

    dt = resolve_doc_type(doc_type, acro, detected)

    template = pick_template(meta, dt.name)
    warnings: list[str] = []
    engines: list[str] = []

    # -- rung 0 -----------------------------------------------------------
    acro_ident: dict = {}
    acro_boxes: dict = {}
    unmapped: list[str] = []
    if acro:
        acro_ident, acro_boxes, unmapped = map_acroform(acro, dt)
        if acro_ident or acro_boxes:
            engines.append("acroform")
        else:
            warnings.append(
                f"The PDF has {len(acro)} AcroForm fields but none of their names match a "
                f"{dt.name} box; they are listed under _extraction.acroform_unmapped.")

    # -- rung 2 -----------------------------------------------------------
    text_doc: Optional[dict] = None
    if verdict == "garbage":
        warnings.append(
            "Layout text failed the quality gate (" + "; ".join(q_dict.get("reasons") or [])
            + ") — the text pass was skipped, not trusted. Read the page images instead.")
    elif text.strip():
        text_doc, tw = build_text_doc(text, dt, template=template)
        warnings.extend(tw)
        engines.append("text")
        if verdict == "suspect":
            warnings.append(
                "Layout text is suspect (" + "; ".join(q_dict.get("reasons") or [])
                + ") — a vision cross-check is mandatory before these figures are used.")
    else:
        warnings.append("No layout text at all — this is an image PDF; run --vision-prompt.")

    # -- rungs 1 + 3 ------------------------------------------------------
    vision_doc = build_vision_doc(vision_json, dt) if vision_json is not None else None
    if vision_doc is not None:
        engines.append("vision")

    if text_doc is not None and vision_doc is not None:
        doc = envelope.merge(text_doc, vision_doc)
    elif vision_doc is not None:
        doc = vision_doc
    elif text_doc is not None:
        doc = text_doc
    else:
        doc = _empty_doc(dt)

    # AcroForm values are exact; they take the field where they exist.
    for section, vals in (("identity", acro_ident), ("boxes", acro_boxes)):
        for k, env in vals.items():
            if not envelope.is_present(env):
                continue
            cur = doc.setdefault(section, {}).get(k)
            if envelope.is_present(cur) and not envelope.values_agree(cur["value"], env["value"]):
                env = dict(env)
                env["alternates"] = [{"engine": "text", "value": cur["value"],
                                      "state": cur["state"]}]
                warnings.append(f"{section}.{k}: AcroForm says {env['value']!r}, layout text said "
                                f"{cur['value']!r}; kept the form field.")
            env = dict(env)
            env["engines"] = ["acroform"]
            env["confidence"] = 0.99
            doc[section][k] = env
    if dt.name == "W-2" and (acro_boxes or not doc.get("state_local")):
        doc["state_local"] = _state_local(doc.get("boxes") or {})

    if doc.get("tax_year") is None and vision_doc is not None and vision_doc.get("tax_year"):
        doc["tax_year"] = vision_doc["tax_year"]

    ext = doc.setdefault("_extraction", {})
    ext["engines"] = engines
    ext["producer"] = producer
    ext["creator"] = meta.get("creator")
    ext["quality"] = q_dict
    ext["doc_type_detected"] = detected
    ext["source_path"] = str(path)
    ext["sha256"] = sha256_of(path)
    ext["page_count"] = page_count
    ext["merged"] = bool(text_doc is not None and vision_doc is not None)
    ext.setdefault("review_required", [])
    if template:
        ext["template"] = template.get("_name")
    if unmapped:
        ext["acroform_unmapped"] = unmapped
    if not engines:
        ext["review_required"] = sorted(set(ext["review_required"]) | {"boxes"})

    doc.setdefault("warnings", [])
    doc["warnings"] = list(dict.fromkeys(list(doc["warnings"]) + warnings))
    doc["schema_version"] = SCHEMA_VERSION

    findings = invariants_mod.evaluate(doc, dt, doc_name=path.name)
    ext["findings"] = findings
    ext["blocked"] = any(f["severity"] == "CRITICAL" for f in findings)
    return doc


def _empty_doc(dt: DocType) -> dict:
    return {
        "doc_type": dt.name,
        "schema_version": SCHEMA_VERSION,
        "tax_year": None,
        "identity": {b.id: envelope.make(None, "UNREADABLE", box=b.id) for b in dt.identity},
        "boxes": {b.id: envelope.make(None, "UNREADABLE", box=b.id) for b in dt.boxes},
        "_extraction": {"engines": []},
        "warnings": [],
        **({"state_local": []} if dt.name == "W-2" else {}),
    }


# --------------------------------------------------------------------------
# Vision prompt
# --------------------------------------------------------------------------

VISION_RULES = """Rules, in order of importance:
  1. Copy the digits exactly as printed. Do not round, reformat, or recompute.
  2. A box that is blank on the paper is null. Never a zero.
  3. Use 0 only when the printed value is 0 (or 0.00).
  4. Never guess. If a box is illegible, write the string "UNREADABLE".
  5. Do not add keys, drop keys, or reorder them; fill the skeleton as given."""


def vision_prompt(path: Path, dt: DocType, pngs: list[str]) -> str:
    lines = [
        f"Read this {dt.name} — {dt.title} — from the page images and fill the JSON skeleton below.",
        "",
        "Page images:",
    ]
    lines += [f"  {p}" for p in pngs] or ["  (none — rasterization unavailable; install poppler)"]
    lines += ["", "Boxes to read, in form order:"]
    for b in dt.identity:
        lines.append(f"  identity.{b.id:<28} {b.label}  [{b.kind}]")
    for b in dt.boxes:
        lines.append(f"  boxes.{b.id:<31} {b.label}  [{b.kind}]")
    lines += [
        "",
        "Also fill tax_year with the year printed on the form.",
        "",
        VISION_RULES,
        "",
        "Skeleton (write exactly these keys to vision.json):",
        json.dumps(dt.vision_skeleton(), indent=2),
        "",
        "Then merge your read with the layout-text read:",
        f"  python3 -B \"$TAX_SKILL/tools/form-parser/form_parser.py\" \"{path}\" "
        f"--type {dt.name} --merge vision.json",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

_SEV_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "INFO": 1}


def _summarize(doc: dict, path: Path) -> None:
    ext = doc.get("_extraction") or {}
    print(f"{path.name}: {doc.get('doc_type')} tax_year={doc.get('tax_year')} "
          f"engines={','.join(ext.get('engines') or []) or 'none'} "
          f"quality={(ext.get('quality') or {}).get('verdict')}")
    present = sum(1 for _, e in envelope.walk(doc) if envelope.is_present(e))
    total = sum(1 for _ in envelope.walk(doc))
    print(f"  {present}/{total} fields observed")
    for w in doc.get("warnings") or []:
        print(f"  warning: {w}")
    for line in envelope.review_summary(doc):
        print(f"  review: {line}")
    for f in ext.get("findings") or []:
        if f["severity"] != "INFO":
            print(f"  {f['severity']} {f['check']}: {f['message']}")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Parse an information return (W-2, 1099-*, 1098-*, 1095-A, 5498-*, "
                    "SSA-1099, W-2G) into the schema_version 2 envelope document.")
    ap.add_argument("pdf", help="path to the PDF")
    ap.add_argument("--type", dest="doc_type", default=None,
                    help="force the doc type (e.g. W-2, 1099-INT); default: detect")
    ap.add_argument("--json", action="store_true", help="print the parsed document as JSON")
    ap.add_argument("--vision-prompt", action="store_true",
                    help="print the prompt + page images for the vision pass and stop")
    ap.add_argument("--merge", metavar="VISION.JSON", default=None,
                    help="merge a filled vision skeleton into the text read")
    ap.add_argument("--write", action="store_true",
                    help="write <pdf dir>/.parsed/<stem>.json")
    ap.add_argument("--force", action="store_true",
                    help="write even when an invariant blocks the parse")
    ap.add_argument("--quiet", action="store_true", help="suppress the human summary")
    args = ap.parse_args(argv)

    path = Path(args.pdf).expanduser()
    try:
        if args.vision_prompt:
            if not path.is_file():
                raise UsageError(f"no such file: {path}")
            res = _extract(path, args.doc_type, mode="form")
            text = getattr(res, "text", None) or ""
            qrep = getattr(res, "quality", None)
            detected = (qrep.get("detected_doc_type") if isinstance(qrep, dict)
                        else quality.assess(text, pdf_path=path).detected_doc_type)
            detected = getattr(res, "doc_type", None) or detected
            acro = getattr(res, "acroform", None)
            dt = resolve_doc_type(args.doc_type, acro if isinstance(acro, dict) else None, detected)
            print(vision_prompt(path, dt, _rasterize(path, res)))
            return 0

        vision = None
        if args.merge:
            mp = Path(args.merge).expanduser()
            if not mp.is_file():
                raise UsageError(f"no such vision JSON: {mp}")
            try:
                vision = json.loads(mp.read_text())
            except json.JSONDecodeError as e:
                raise UsageError(f"{mp} is not valid JSON: {e}") from e
            if not isinstance(vision, dict):
                raise UsageError(f"{mp} must hold a filled vision skeleton object")

        doc = parse(path, args.doc_type, vision_json=vision)
    except UsageError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    ext = doc.get("_extraction") or {}
    findings = ext.get("findings") or []
    worst = max((_SEV_ORDER.get(f["severity"], 0) for f in findings), default=0)
    review = ext.get("review_required") or []

    if args.json:
        print(json.dumps(doc, indent=2, sort_keys=False))
    if not args.quiet:
        _summarize(doc, path)

    if args.write:
        if ext.get("blocked") and not args.force:
            print("Refusing to write: a CRITICAL invariant says this document contradicts "
                  "itself. Resolve it, or re-run with --force and record why.", file=sys.stderr)
            return 1
        out_dir = path.resolve().parent / ".parsed"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{path.stem}.json"
        out.write_text(json.dumps(doc, indent=2) + "\n")
        if not args.quiet:
            print(f"  wrote {out}")

    return 1 if (worst >= _SEV_ORDER["HIGH"] or review) else 0


if __name__ == "__main__":
    sys.exit(main())

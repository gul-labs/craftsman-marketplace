#!/usr/bin/env python3
"""
make_fixtures — generate the PDF corpus `test_form_parser.py` runs against.

Run by a maintainer; the outputs are checked in. The test only reads them.

    python3 -B tools/form-parser/fixtures/make_fixtures.py            # all types
    python3 -B tools/form-parser/fixtures/make_fixtures.py --only W-2
    python3 -B tools/form-parser/fixtures/make_fixtures.py --check    # parse + diff, write nothing

Why a PDF writer lives here: the corpus has to be regenerable from source on any
machine, with no wheels to install and no binary blobs whose provenance nobody
can check. So this module writes PDFs itself — Helvetica base-14 text at
absolute positions, a correct xref table, optionally a simple `/AcroForm` with
`/Tx` fields, optionally a `/DeviceGray` image XObject for the scanned variant.
Nothing here is fast or general; it is small enough to audit.

Every figure is fake and internally consistent: box 4 really is 6.2% of box 3,
the 1099-K months really do sum to box 1a, the SSA-1099 net really is paid minus
repaid. That is the point — the registry invariants must PASS on a good fixture,
so that `w-2-broken/` (box 4 inflated tenfold) is the only thing that trips them.

Deterministic: fixed values, no dates, no /ID, no timestamps. Re-running writes
byte-identical files.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent
_TOOL = _HERE.parent
for _p in (str(_TOOL), str(_TOOL.parent / "pdf-extractor")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from doc_types import REGISTRY, FORM_PARSER_TYPES, Box, DocType  # noqa: E402

TAX_YEAR = 2025
FONT_SIZE = 9
LEADING = 13
TOP_Y = 748
LEFT_X = 36
BOTTOM_Y = 44
PAGE_W, PAGE_H = 612, 792
LABEL_W = 74          # columns before the value column
VALUE_W = 14


# ==========================================================================
# Minimal PDF writer
# ==========================================================================

def _esc(s: str) -> bytes:
    out = s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return out.encode("latin-1", "replace")


class PdfWriter:
    """Pages of positioned Helvetica text, plus optional AcroForm text fields
    and full-page grayscale images. Object 1 is the catalog, 2 the page tree."""

    def __init__(self) -> None:
        self.pages: list[dict] = []

    def add_text_page(self, lines: list[str], fields: Optional[list[tuple[str, str]]] = None) -> None:
        self.pages.append({"kind": "text", "lines": lines, "fields": fields or []})

    def add_image_page(self, gray: bytes, width: int, height: int) -> None:
        self.pages.append({"kind": "image", "data": gray, "w": width, "h": height})

    # -- object plumbing ---------------------------------------------------

    def build(self) -> bytes:
        objs: dict[int, bytes] = {}
        nxt = [3]  # 1 = catalog, 2 = pages

        def alloc() -> int:
            nxt[0] += 1
            return nxt[0] - 1

        font_id = alloc()
        objs[font_id] = (b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                         b"/Encoding /WinAnsiEncoding >>")

        page_ids: list[int] = []
        field_ids: list[int] = []
        for page in self.pages:
            pid = alloc()
            page_ids.append(pid)
            if page["kind"] == "text":
                content = []
                y = TOP_Y
                for line in page["lines"]:
                    if y < BOTTOM_Y:
                        break
                    if line.strip():
                        content.append(b"BT /F1 " + str(FONT_SIZE).encode() + b" Tf 1 0 0 1 "
                                       + str(LEFT_X).encode() + b" " + str(y).encode()
                                       + b" Tm (" + _esc(line) + b") Tj ET\n")
                    y -= LEADING
                stream = b"".join(content)
                cid = alloc()
                objs[cid] = _stream(b"", stream)
                annots = []
                fy = 300
                for name, value in page["fields"]:
                    fid = alloc()
                    field_ids.append(fid)
                    annots.append(fid)
                    objs[fid] = (b"<< /Type /Annot /Subtype /Widget /FT /Tx /T ("
                                 + _esc(name) + b") /V (" + _esc(value) + b") /Rect ["
                                 + f"{460} {fy} {560} {fy + 10}".encode()
                                 + b"] /F 4 /P " + str(pid).encode()
                                 + b" 0 R /DA (/Helv 9 Tf 0 g) /Ff 0 >>")
                    fy = fy - 12 if fy > 60 else 300
                body = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
                        + f"{PAGE_W} {PAGE_H}".encode() + b"] /Resources << /Font << /F1 "
                        + str(font_id).encode() + b" 0 R >> >> /Contents "
                        + str(cid).encode() + b" 0 R")
                if annots:
                    body += b" /Annots [" + b" ".join(f"{a} 0 R".encode() for a in annots) + b"]"
                objs[pid] = body + b" >>"
            else:
                iid = alloc()
                objs[iid] = _stream(
                    b"/Type /XObject /Subtype /Image /Width " + str(page["w"]).encode()
                    + b" /Height " + str(page["h"]).encode()
                    + b" /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode",
                    zlib.compress(page["data"], 9), precompressed=True)
                cid = alloc()
                objs[cid] = _stream(b"", f"q {PAGE_W} 0 0 {PAGE_H} 0 0 cm /Im0 Do Q\n".encode())
                objs[pid] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
                             + f"{PAGE_W} {PAGE_H}".encode()
                             + b"] /Resources << /XObject << /Im0 " + str(iid).encode()
                             + b" 0 R >> >> /Contents " + str(cid).encode() + b" 0 R >>")

        kids = b" ".join(f"{p} 0 R".encode() for p in page_ids)
        objs[2] = (b"<< /Type /Pages /Count " + str(len(page_ids)).encode()
                   + b" /Kids [" + kids + b"] >>")
        cat = b"<< /Type /Catalog /Pages 2 0 R"
        if field_ids:
            cat += (b" /AcroForm << /Fields ["
                    + b" ".join(f"{f} 0 R".encode() for f in field_ids)
                    + b"] /DA (/Helv 9 Tf 0 g) /DR << /Font << /Helv "
                    + str(font_id).encode() + b" 0 R >> >> /NeedAppearances true >>")
        objs[1] = cat + b" >>"

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets: dict[int, int] = {}
        for oid in sorted(objs):
            offsets[oid] = len(out)
            out += str(oid).encode() + b" 0 obj\n" + objs[oid] + b"\nendobj\n"
        xref_at = len(out)
        n = max(objs) + 1
        out += b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n"
        for oid in range(1, n):
            out += f"{offsets.get(oid, 0):010d} 00000 n \n".encode()
        out += (b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\nstartxref\n"
                + str(xref_at).encode() + b"\n%%EOF\n")
        return bytes(out)


def _stream(extra: bytes, data: bytes, precompressed: bool = False) -> bytes:
    head = b"<< " + (extra + b" " if extra else b"") + b"/Length " + str(len(data)).encode() + b" >>"
    return head + b"\nstream\n" + data + b"\nendstream"


# ==========================================================================
# Printed-label derivation
# ==========================================================================

_FOLD = {"’": "'", "‘": "'", "–": "-", "—": "-", "“": '"', "”": '"'}


def fold(s: str) -> str:
    for a, b in _FOLD.items():
        s = s.replace(a, b)
    return s


def box_number(box_id: str) -> Optional[str]:
    m = re.match(r"(?:int_|div_)?box_(\d{1,2}[a-d]?)(?:_|$)", box_id)
    return m.group(1) if m else None


def printed_label(dt: DocType, box: Box) -> str:
    over = LABEL_OVERRIDES.get((dt.name, box.id)) or LABEL_OVERRIDES.get(("*", box.id))
    if over:
        return fold(over)
    label = fold(box.label)
    num = box_number(box.id)
    if num and not label[:1].isdigit():
        return f"{num} {label}"
    return label


def render(box: Box, value: Any) -> str:
    if box.kind == "money":
        return f"{value:,.2f}"
    if box.kind == "flag":
        return "[X]" if value else "[ ]"
    if box.kind == "codes":
        return "  ".join(f"{d['code']}  {d['amount']:,.2f}" for d in value)
    return str(value)


def row(label: str, value: str) -> str:
    pad = max(3, LABEL_W - len(label))
    return label + " " * pad + value.rjust(VALUE_W)


# ==========================================================================
# The fixture data
# ==========================================================================

LABEL_OVERRIDES: dict[tuple[str, str], str] = {
    ("1098", "box_7"): "7 Address of property is the same as PAYER'S/BORROWER'S address",
    ("5498", "box_11"): "11 Check if RMD for 2026",
    ("5498-SA", "box_3"): "3 Total HSA or Archer MSA contributions made in 2026 for 2025",
    ("SSA-1099", "recipient_name"): "1. Name",
    ("1099-Composite", "int_box_4"): "4 Federal income tax withheld (INT)",
    ("1099-Composite", "div_box_4"): "4 Federal income tax withheld (DIV)",
    ("1099-Composite", "int_box_6"): "6 Foreign tax paid (INT)",
    ("1099-Composite", "div_box_7"): "7 Foreign tax paid (DIV)",
}

_B_LABEL = {
    "st_covered": "Short-term covered (Box A)",
    "st_noncovered": "Short-term noncovered (Box B)",
    "lt_covered": "Long-term covered (Box D)",
    "lt_noncovered": "Long-term noncovered (Box E)",
}
_B_FIELD = {
    "proceeds": "Proceeds",
    "basis": "Cost basis",
    "wash_sale": "Wash sale loss disallowed",
    "market_discount": "Accrued market discount",
    "gain": "Gain or (loss)",
}
for _cat, _cl in _B_LABEL.items():
    for _f, _fl in _B_FIELD.items():
        for _doc in ("1099-B", "1099-Composite"):
            LABEL_OVERRIDES[(_doc, f"{_cat}_{_f}")] = f"{_cl} - {_fl}"

# Broker summary numbers, shared by 1099-B and the consolidated statement.
_B_VALUES = {
    "st_covered_proceeds": 45000.00, "st_covered_basis": 40000.00,
    "st_covered_wash_sale": 500.00, "st_covered_market_discount": 0.00,
    "st_covered_gain": 5500.00,
    "st_noncovered_proceeds": 12000.00, "st_noncovered_basis": 13000.00,
    "st_noncovered_wash_sale": 0.00, "st_noncovered_market_discount": 0.00,
    "st_noncovered_gain": -1000.00,
    "lt_covered_proceeds": 80000.00, "lt_covered_basis": 60000.00,
    "lt_covered_wash_sale": 0.00, "lt_covered_market_discount": 0.00,
    "lt_covered_gain": 20000.00,
    "lt_noncovered_proceeds": 5000.00, "lt_noncovered_basis": 5200.00,
    "lt_noncovered_wash_sale": 0.00, "lt_noncovered_market_discount": 0.00,
    "lt_noncovered_gain": -200.00,
}

_PAYER = {
    "payer_name": "Cascade Financial Services Inc",
    "payer_tin": "12-3456789",
    "recipient_name": "Jordan A Rivera",
    "recipient_tin": "123-45-6789",
    "account_number": "CFS-4471-0093",
}

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

FIXTURES: dict[str, dict] = {
    "W-2": {
        "identity": {
            "employee_ssn": "123-45-6789",
            "employer_ein": "12-3456789",
            "employer_name": "Northwater Logistics LLC",
            "control_number": "A-0042175",
            "employee_name": "Jordan A Rivera",
        },
        "boxes": {
            "box_1": 105000.00, "box_2": 16800.00,
            "box_3": 117000.00, "box_4": 7254.00,
            "box_5": 117000.00, "box_6": 1696.50,
            "box_8": 0.00, "box_10": 5000.00, "box_11": 0.00,
            "box_12": [{"code": "D", "amount": 12000.00}, {"code": "DD", "amount": 9600.00}],
            "box_13_statutory_employee": False,
            "box_13_retirement_plan": True,
            "box_13_third_party_sick_pay": False,
            "box_14": [{"code": "UNION", "amount": 480.00}],
            "box_15_state": "OH",
            "box_15_employer_state_id": "OH-99887",
            "box_16": 105000.00, "box_17": 5250.00,
            "box_18": 105000.00, "box_19": 1050.00,
            "box_20": "CINCINNATI",
        },
    },
    "W-2G": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 5000.00, "box_2": "2025-07-04", "box_3": "Slot machine",
            "box_4": 1200.00, "box_5": "TX-88120", "box_7": 0.00,
            "box_9": "123-45-6789", "box_13_state": "NV-4471",
            "box_14": 5000.00, "box_15": 0.00, "box_16": 0.00, "box_17": 0.00,
            "box_18": "LAS VEGAS",
        },
    },
    "1099-INT": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 4812.55, "box_2": 125.00, "box_3": 1200.00, "box_4": 0.00,
            "box_5": 0.00, "box_6": 60.00, "box_7": "Various", "box_8": 2300.00,
            "box_9": 400.00, "box_10": 0.00, "box_11": 220.00, "box_12": 150.00,
            "box_13": 300.00, "box_14": "912828YY0",
            "box_17": 0.00, "box_16": "WA-1234", "box_18": 4812.55,
            "box_15_state": "WA",
        },
    },
    "1099-DIV": {
        "identity": _PAYER,
        "boxes": {
            "box_1a": 8450.00, "box_1b": 6900.00, "box_2a": 2100.00, "box_2b": 300.00,
            "box_2c": 0.00, "box_2d": 150.00, "box_2e": 200.00, "box_2f": 100.00,
            "box_3": 75.00, "box_4": 0.00, "box_5": 900.00, "box_6": 0.00,
            "box_7": 210.00, "box_8": "Various", "box_9": 0.00, "box_10": 0.00,
            "box_11": False, "box_12": 1400.00, "box_13": 250.00,
            "box_14_state": "WA", "box_15": "WA-5678", "box_16": 0.00,
        },
    },
    "1099-B": {
        "identity": _PAYER,
        "boxes": {**_B_VALUES, "box_4": 0.00},
    },
    "1099-Composite": {
        "identity": _PAYER,
        "boxes": {
            "int_box_1": 4812.55, "int_box_3": 1200.00, "int_box_4": 0.00,
            "int_box_6": 60.00, "int_box_8": 2300.00, "int_box_11": 220.00,
            "div_box_1a": 8450.00, "div_box_1b": 6900.00, "div_box_2a": 2100.00,
            "div_box_2b": 300.00, "div_box_3": 75.00, "div_box_4": 0.00,
            "div_box_5": 900.00, "div_box_7": 210.00, "div_box_12": 1400.00,
            **_B_VALUES,
        },
    },
    "1099-NEC": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 62500.00, "box_2": False, "box_4": 0.00,
            "box_5": 0.00, "box_6": "WA-1234", "box_7": 62500.00,
        },
    },
    "1099-MISC": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 24000.00, "box_2": 3500.00, "box_3": 1000.00, "box_4": 0.00,
            "box_5": 0.00, "box_6": 0.00, "box_7": False, "box_8": 0.00,
            "box_9": 0.00, "box_10": 0.00, "box_11": 0.00, "box_12": 0.00,
            "box_14": 0.00, "box_15": 0.00,
            "box_16": 0.00, "box_17": "WA-1234", "box_18": 24000.00,
        },
    },
    "1099-R": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 40000.00, "box_2a": 32000.00,
            "box_2b_taxable_not_determined": False, "box_2b_total_distribution": True,
            "box_3": 0.00, "box_4": 4000.00, "box_5": 8000.00, "box_6": 0.00,
            "box_7": "7", "box_7_ira_sep_simple": False, "box_8": 0.00,
            "box_9b": 8000.00, "box_10": 0.00, "box_12": False,
            "box_13": "2025-11-14",
            "box_14": 1200.00, "box_15": "OR-4455", "box_16": 40000.00,
            "box_17": 0.00, "box_18": "PORTLAND", "box_19": 0.00,
        },
    },
    "1099-G": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 6200.00, "box_2": 0.00, "box_3": "2024", "box_4": 620.00,
            "box_5": 0.00, "box_6": 0.00, "box_7": 0.00, "box_8": False,
            "box_9": 0.00, "box_10a_state": "WA", "box_10b": "WA-1234", "box_11": 0.00,
        },
    },
    "1099-K": {
        "identity": _PAYER,
        "boxes": {
            "box_1a": 84000.00, "box_1b": 21000.00, "box_2": "5734", "box_3": 1250.00,
            "box_4": 0.00,
            **{f"box_5_{m}": 7000.00 for m in _MONTHS},
            "box_6_state": "WA", "box_7": "WA-1234", "box_8": 0.00,
        },
    },
    "1099-SA": {
        "identity": _PAYER,
        "boxes": {
            "box_1": 2400.00, "box_2": 0.00, "box_3": "1", "box_4": 0.00,
            "box_5_hsa": True, "box_5_archer": False, "box_5_ma_msa": False,
        },
    },
    "SSA-1099": {
        "identity": {
            "recipient_name": "Jordan A Rivera",
            "recipient_ssn": "123-45-6789",
            "claim_number": "123-45-6789 A",
        },
        "boxes": {
            "box_3": 24600.00, "box_4": 1200.00, "box_5": 23400.00, "box_6": 2460.00,
            "medicare_part_b": 2096.40, "medicare_part_d": 0.00,
        },
    },
    "1098": {
        "identity": {
            "payer_name": "Puget Mutual Mortgage Company",
            "payer_tin": "94-7654321",
            "recipient_name": "Jordan A Rivera",
            "recipient_tin": "123-45-6789",
            "account_number": "PMM-88213-0",
        },
        "boxes": {
            "box_1": 18450.00, "box_2": 425000.00, "box_3": "2019-06-15",
            "box_4": 0.00, "box_5": 0.00, "box_6": 0.00, "box_7": True,
            "box_8": "1420 Alder Street, Tacoma WA", "box_10": 6240.00,
        },
    },
    "1098-T": {
        "identity": {
            "payer_name": "Evergreen State College",
            "payer_tin": "91-1234567",
            "recipient_name": "Riley Rivera",
            "recipient_tin": "987-65-4321",
            "account_number": "ESC-2025-4410",
        },
        "boxes": {
            "box_1": 12400.00, "box_4": 0.00, "box_5": 3000.00, "box_6": 0.00,
            "box_7": True, "box_8": True, "box_9": False, "box_10": 0.00,
        },
    },
    "1098-E": {
        "identity": {
            "payer_name": "Northline Student Loan Servicing",
            "payer_tin": "45-6789012",
            "recipient_name": "Jordan A Rivera",
            "recipient_tin": "123-45-6789",
            "account_number": "NSL-77120",
        },
        "boxes": {"box_1": 1842.75, "box_2": False},
    },
    "5498": {
        "identity": {
            "payer_name": "Harborline Trust Company",
            "payer_tin": "23-4567890",
            "recipient_name": "Jordan A Rivera",
            "recipient_tin": "123-45-6789",
            "account_number": "HTC-1120-IRA",
        },
        "boxes": {
            "box_1": 7000.00, "box_2": 0.00, "box_3": 0.00, "box_4": 0.00,
            "box_5": 152340.00, "box_6": 0.00,
            "box_7_ira": True, "box_7_sep": False, "box_7_simple": False,
            "box_7_roth": False,
            "box_8": 0.00, "box_9": 0.00, "box_10": 0.00, "box_11": False,
            "box_12b": 0.00, "box_13a": 0.00, "box_14a": 0.00, "box_15a": 0.00,
        },
    },
    "5498-SA": {
        "identity": {
            "payer_name": "Harborline Trust Company",
            "payer_tin": "23-4567890",
            "recipient_name": "Jordan A Rivera",
            "recipient_tin": "123-45-6789",
            "account_number": "HTC-1120-HSA",
        },
        "boxes": {
            "box_1": 0.00, "box_2": 4300.00, "box_3": 0.00, "box_4": 0.00,
            "box_5": 18750.00, "box_6_hsa": True, "box_6_archer": False,
            "box_6_ma_msa": False,
        },
    },
    "1095-A": {
        "identity": {
            "marketplace_identifier": "WA-EX-0001",
            "policy_number": "WAX-2025-778120",
            "policy_issuer_name": "Cascade Health Plan",
            "recipient_name": "Jordan A Rivera",
            "recipient_ssn": "123-45-6789",
            "policy_start_date": "2025-01-01",
            "policy_termination_date": "2025-12-31",
        },
        "boxes": {
            **{f"{m}_premium": 1050.00 for m in _MONTHS},
            **{f"{m}_slcsp": 1120.00 for m in _MONTHS},
            **{f"{m}_aptc": 840.00 for m in _MONTHS},
            "annual_premium": 12600.00, "annual_slcsp": 13440.00, "annual_aptc": 10080.00,
        },
    },
}

OMB = {
    "W-2": "1545-0008", "W-2G": "1545-0238", "1099-INT": "1545-0112",
    "1099-DIV": "1545-0110", "1099-B": "1545-0715", "1099-Composite": "1545-0715",
    "1099-NEC": "1545-0116", "1099-MISC": "1545-0115", "1099-R": "1545-0119",
    "1099-G": "1545-0120", "1099-K": "1545-2205", "1099-SA": "1545-1517",
    "SSA-1099": "0960-0603", "1098": "1545-1380", "1098-T": "1545-1574",
    "1098-E": "1545-1576", "5498": "1545-0747", "5498-SA": "1545-1518",
    "1095-A": "1545-2232",
}


# ==========================================================================
# Layout
# ==========================================================================

def header_lines(dt: DocType) -> list[str]:
    title = fold(dt.title)
    if len(title) > 62:
        cut = title[:62].rsplit(" ", 1)[0]
        title = cut
    return [
        f"Form {dt.name}   {title}   {TAX_YEAR}   OMB No. {OMB.get(dt.name, '1545-0000')}",
        "",
    ]


def doc_lines(dt: DocType, data: dict) -> list[str]:
    """One printed copy of the form as `pdftotext -layout` will see it."""
    lines = header_lines(dt)
    for b in dt.identity:
        if b.id in data["identity"]:
            lines.append(row(printed_label(dt, b), str(data["identity"][b.id])))
    lines.append("")
    if dt.name == "1099-Composite":
        lines += ["Form 1099-INT   Interest Income", ""]
    if dt.name == "1095-A":
        return lines + part_iii_lines(data)
    for b in dt.boxes:
        if b.id not in data["boxes"]:
            continue
        if dt.name == "1099-Composite" and b.id == "div_box_1a":
            lines += ["", "Form 1099-DIV   Dividends and Distributions", ""]
        if dt.name == "1099-Composite" and b.id == "st_covered_proceeds":
            lines += ["", "Form 1099-B   Proceeds From Broker and Barter Exchange", ""]
        val = data["boxes"][b.id]
        if b.kind == "codes":
            lines += code_lines(b, val)
            continue
        lines.append(row(printed_label(dt, b), render(b, val)))
    return lines


def code_lines(box: Box, pairs: list[dict]) -> list[str]:
    """Box 12 prints one lettered line per code; box 14 prints code + amount."""
    if box.id == "box_12":
        return [row(f"12{chr(97 + i)}  {d['code']}", f"{d['amount']:,.2f}")
                for i, d in enumerate(pairs)]
    return [row(f"14 Other   {d['code']}", f"{d['amount']:,.2f}") for d in pairs]


def part_iii_lines(data: dict) -> list[str]:
    b = data["boxes"]
    lines = [
        "Part III   Coverage Information",
        ("Month".ljust(28) + "A. Monthly enrollment premiums".rjust(34)
         + "B. Monthly SLCSP premium".rjust(28) + "C. Monthly advance PTC".rjust(26)),
        "",
    ]
    for i, m in enumerate(_MONTHS):
        label = f"{21 + i} {m.title()}"
        lines.append(label.ljust(28)
                     + f"{b[f'{m}_premium']:,.2f}".rjust(34)
                     + f"{b[f'{m}_slcsp']:,.2f}".rjust(28)
                     + f"{b[f'{m}_aptc']:,.2f}".rjust(26))
    lines.append("33 Annual Totals".ljust(28)
                 + f"{b['annual_premium']:,.2f}".rjust(34)
                 + f"{b['annual_slcsp']:,.2f}".rjust(28)
                 + f"{b['annual_aptc']:,.2f}".rjust(26))
    return lines


def paginate(lines: list[str], per_page: int = 54) -> list[list[str]]:
    return [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]


# ==========================================================================
# Golden
# ==========================================================================

def golden_for(dt: DocType, data: dict) -> dict:
    return {
        "doc_type": dt.name,
        "tax_year": TAX_YEAR,
        "identity": dict(data["identity"]),
        "boxes": dict(data["boxes"]),
    }


# ==========================================================================
# Variants
# ==========================================================================

def garbage_lines(lines: list[str]) -> list[str]:
    """The same geometry with every glyph replaced by a font that carries no
    ToUnicode map — which is what `pdftotext` reports as `(cid:N)`."""
    out = []
    for i, line in enumerate(lines):
        if not line.strip():
            out.append("")
            continue
        toks = []
        for j, word in enumerate(line.split()):
            if word.strip():
                toks.append("".join(f"(cid:{(i * 7 + j * 3 + k) % 90 + 10})"
                                    for k in range(max(1, len(word) // 3))))
        out.append("   ".join(toks))
    return out


def rasterize_gray(pdf: Path, page: int = 1, dpi: int = 150) -> Optional[tuple[bytes, int, int]]:
    """`pdftoppm -gray -r 150` → (raw 8-bit gray bytes, width, height)."""
    if not shutil.which("pdftoppm"):
        return None
    with tempfile.TemporaryDirectory(prefix="fixture-scan-") as tmp:
        prefix = Path(tmp) / "pg"
        try:
            subprocess.run(["pdftoppm", "-gray", "-r", str(dpi), "-f", str(page),
                            "-l", str(page), str(pdf), str(prefix)],
                           check=True, capture_output=True, timeout=180)
        except (OSError, subprocess.SubprocessError):
            return None
        pgms = sorted(Path(tmp).glob("pg*.pgm"))
        if not pgms:
            return None
        return read_pgm(pgms[0].read_bytes())


def read_pgm(raw: bytes) -> Optional[tuple[bytes, int, int]]:
    """Binary PGM (P5) → (pixels, width, height). Comments are legal; handle them."""
    if not raw.startswith(b"P5"):
        return None
    pos = 2
    vals = []
    while len(vals) < 3:
        while pos < len(raw) and raw[pos:pos + 1].isspace():
            pos += 1
        if raw[pos:pos + 1] == b"#":
            while pos < len(raw) and raw[pos:pos + 1] not in (b"\n", b"\r"):
                pos += 1
            continue
        start = pos
        while pos < len(raw) and not raw[pos:pos + 1].isspace():
            pos += 1
        vals.append(int(raw[start:pos]))
    pos += 1  # single whitespace after maxval
    w, h, maxv = vals
    if maxv != 255:
        return None
    return raw[pos:pos + w * h], w, h


# ==========================================================================
# Generation
# ==========================================================================

def slug(name: str) -> str:
    return name.lower()


def write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"  {path.relative_to(_HERE)}  ({len(data):,} bytes)")


def build_text_pdf(dt: DocType, data: dict, copies: int = 1) -> bytes:
    pdf = PdfWriter()
    body = doc_lines(dt, data)
    for _ in range(copies):
        for page in paginate(body):
            pdf.add_text_page(page)
    return pdf.build()


def acroform_fields(dt: DocType, data: dict) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for section in ("identity", "boxes"):
        for bid, val in data[section].items():
            box = dt.box(bid)
            if box is None:
                continue
            if box.kind == "money":
                fields.append((bid, f"{val:,.2f}"))
            elif box.kind == "flag":
                fields.append((bid, "Yes" if val else "Off"))
            elif box.kind == "codes":
                fields.append((bid, "  ".join(f"{d['code']} {d['amount']:,.2f}" for d in val)))
            else:
                fields.append((bid, str(val)))
    return fields


def generate(only: Optional[str] = None) -> None:
    names = [n for n in FORM_PARSER_TYPES if not only or n == only]
    for name in names:
        dt = REGISTRY[name]
        data = FIXTURES.get(name)
        if data is None:
            print(f"! no fixture data for {name}")
            continue
        out = _HERE / slug(name)
        print(f"{name}:")
        copies = 4 if dt.copies_per_page > 1 else 1
        write(out / "text.pdf", build_text_pdf(dt, data, copies=copies))
        (out / "golden.json").write_text(json.dumps(golden_for(dt, data), indent=2) + "\n")
        print(f"  {(out / 'golden.json').relative_to(_HERE)}")

        if name != "W-2":
            continue

        # --- AcroForm variant (one copy, fields named after box ids) -------
        pdf = PdfWriter()
        pages = paginate(doc_lines(dt, data))
        fields = acroform_fields(dt, data)
        for i, page in enumerate(pages):
            pdf.add_text_page(page, fields if i == 0 else None)
        write(out / "acroform.pdf", pdf.build())

        # --- garbage-text variant ------------------------------------------
        gpdf = PdfWriter()
        for page in paginate(garbage_lines(doc_lines(dt, data))):
            gpdf.add_text_page(page)
        write(out / "garbage.pdf", gpdf.build())

        # --- scanned variant ------------------------------------------------
        got = rasterize_gray(out / "text.pdf")
        if got is None:
            print("  (skipped scan.pdf — pdftoppm unavailable)")
        else:
            pixels, w, h = got
            spdf = PdfWriter()
            spdf.add_image_page(pixels, w, h)
            write(out / "scan.pdf", spdf.build())

        # --- deliberately broken variant ------------------------------------
        broken = {"identity": dict(data["identity"]), "boxes": dict(data["boxes"])}
        broken["boxes"]["box_4"] = data["boxes"]["box_4"] * 10
        bout = _HERE / "w-2-broken"
        print("W-2 (broken):")
        write(bout / "text.pdf", build_text_pdf(dt, broken, copies=copies))
        (bout / "golden.json").write_text(json.dumps(golden_for(dt, broken), indent=2) + "\n")
        print(f"  {(bout / 'golden.json').relative_to(_HERE)}")


def check(only: Optional[str] = None) -> int:
    """Parse every generated fixture and diff against its golden. Writes nothing."""
    sys.path.insert(0, str(_TOOL))
    import form_parser  # noqa: WPS433
    from envelope import unwrap  # noqa: WPS433

    bad = 0
    dirs = [d for d in sorted(_HERE.iterdir()) if (d / "golden.json").is_file()]
    for d in dirs:
        gold = json.loads((d / "golden.json").read_text())
        name = gold["doc_type"]
        if only and name != only:
            continue
        doc = form_parser.parse(d / "text.pdf", name)
        problems = []
        if doc.get("tax_year") != gold["tax_year"]:
            problems.append(f"tax_year: got {doc.get('tax_year')!r} want {gold['tax_year']!r}")
        for section in ("identity", "boxes"):
            for k, want in gold[section].items():
                got = unwrap((doc.get(section) or {}).get(k))
                if not _same(got, want):
                    problems.append(f"{section}.{k}: got {got!r} want {want!r}")
        sev = [f for f in (doc["_extraction"].get("findings") or [])
               if f["severity"] in ("HIGH", "CRITICAL")]
        status = "ok" if not problems else f"{len(problems)} MISMATCH"
        print(f"{d.name:16s} {status}" + (f"  findings={[f['check'] for f in sev]}" if sev else ""))
        for p in problems:
            print(f"    {p}")
        bad += len(problems)
    return 1 if bad else 0


def _same(got: Any, want: Any) -> bool:
    if isinstance(want, bool) or isinstance(got, bool):
        return got is not None and bool(got) == bool(want)
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        return abs(got - want) < 0.01
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return False
        return all(a.get("code") == b.get("code") and abs(a.get("amount", 0) - b.get("amount", 0)) < 0.01
                   for a, b in zip(got, want))
    if want is None or got is None:
        return want is got
    return " ".join(str(got).split()).casefold() == " ".join(str(want).split()).casefold()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", help="one doc type, e.g. W-2")
    ap.add_argument("--check", action="store_true", help="parse the fixtures and diff; write nothing")
    args = ap.parse_args()
    if args.check:
        return check(args.only)
    generate(args.only)
    return check(args.only)


if __name__ == "__main__":
    sys.exit(main())

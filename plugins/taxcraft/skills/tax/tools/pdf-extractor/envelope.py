#!/usr/bin/env python3
"""
envelope — the field-level state contract for parsed tax values, and the merge
of two independent extractions into one reviewed document.

`parsing.md` → "Field-state and legacy-parser containment" promises every
load-bearing value carries its own state, source anchor and confidence, so a
downstream computation can tell an observed zero from a box the extractor never
saw. This module is that contract in code. Parsers emit envelopes; verify.py
unwraps them; nothing ever coerces a missing box to 0.

    {"value": 1234.56,
     "state": "OBSERVED_VALUE",
     "source_anchor": {"page": 1, "line_or_box": "1"},
     "confidence": 0.95,
     "review": {"reviewer": null, "reviewed_at": null}}

Merging: a form is read twice — once from layout text (exact digits, fragile
geometry) and once by vision over the rasterized page (robust geometry, can
misread a digit). `merge()` keeps what both agree on at high confidence, keeps a
one-sided read at medium confidence, and on disagreement keeps the vision value,
records the alternate, and lists the path under `_extraction.review_required`.
Nothing here decides who is right; it decides what a human must look at.

Pure stdlib. Never modifies anything.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable, Optional

STATES = (
    "OBSERVED_VALUE",
    "OBSERVED_ZERO",
    "NOT_PRESENT",
    "UNREADABLE",
    "NOT_APPLICABLE",
    "DERIVED",
    "MANUAL_OVERRIDE",
)

# When two engines disagree, the state that carries more information wins.
_STATE_RANK = {
    "MANUAL_OVERRIDE": 6,
    "OBSERVED_VALUE": 5,
    "DERIVED": 4,
    "OBSERVED_ZERO": 3,
    "NOT_PRESENT": 2,
    "NOT_APPLICABLE": 1,
    "UNREADABLE": 0,
}

CONF_AGREE = 0.95
CONF_SINGLE = 0.6
CONF_DISAGREE = 0.3

SCHEMA_VERSION = 2


# --------------------------------------------------------------------------
# Constructors and accessors
# --------------------------------------------------------------------------

def make(
    value: Any = None,
    state: Optional[str] = None,
    *,
    page: Optional[int] = None,
    box: Optional[str] = None,
    confidence: Optional[float] = None,
) -> dict:
    """Build an envelope. State is inferred when not given:
    None → NOT_PRESENT, 0 → OBSERVED_ZERO, anything else → OBSERVED_VALUE."""
    if state is None:
        if value is None:
            state = "NOT_PRESENT"
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
            state = "OBSERVED_ZERO"
        else:
            state = "OBSERVED_VALUE"
    if state not in STATES:
        raise ValueError(f"unknown envelope state {state!r}")
    return {
        "value": value,
        "state": state,
        "source_anchor": {"page": page, "line_or_box": box},
        "confidence": confidence,
        "review": {"reviewer": None, "reviewed_at": None},
    }


def is_envelope(x: Any) -> bool:
    return isinstance(x, dict) and "value" in x and "state" in x and x.get("state") in STATES


def unwrap(x: Any) -> Any:
    """Envelope → its value. Plain values pass through. A NOT_PRESENT /
    UNREADABLE / NOT_APPLICABLE envelope unwraps to None, never to 0."""
    if is_envelope(x):
        if x["state"] in ("NOT_PRESENT", "UNREADABLE", "NOT_APPLICABLE"):
            return None
        return x["value"]
    return x


def state_of(x: Any) -> Optional[str]:
    return x.get("state") if is_envelope(x) else None


def is_present(x: Any) -> bool:
    """True when the envelope holds an observed (or derived/overridden) value.
    A plain non-None value counts as present for legacy documents."""
    if is_envelope(x):
        return x["state"] in ("OBSERVED_VALUE", "OBSERVED_ZERO", "DERIVED", "MANUAL_OVERRIDE")
    return x is not None


# --------------------------------------------------------------------------
# Walking a document
# --------------------------------------------------------------------------

def walk(doc: Any, prefix: str = "") -> Iterable[tuple[str, dict]]:
    """Yield (dotted_path, envelope) for every envelope in `doc`."""
    if is_envelope(doc):
        yield prefix, doc
        return
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k.startswith("_"):
                continue
            yield from walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from walk(v, f"{prefix}[{i}]")


def flatten(doc: Any) -> dict[str, Any]:
    """{dotted_path: unwrapped value} for every envelope in `doc`.
    Absent values are None. Legacy flat documents (no envelopes) are returned
    as their own top-level scalar fields so verify.py can treat both alike."""
    out: dict[str, Any] = {}
    found = False
    for path, env in walk(doc):
        found = True
        out[path] = unwrap(env)
    if not found and isinstance(doc, dict):
        for k, v in doc.items():
            if isinstance(v, (int, float, str)) and not isinstance(v, bool):
                out[k] = v
    return out


def get_path(doc: Any, path: str) -> Any:
    """Resolve a dotted / indexed path like `boxes.box_1` or `state_local[0].wages`."""
    cur = doc
    for part in _split_path(path):
        if isinstance(part, int):
            if not isinstance(cur, list) or part >= len(cur):
                return None
            cur = cur[part]
        else:
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
    return cur


def set_path(doc: dict, path: str, value: Any) -> None:
    parts = _split_path(path)
    cur: Any = doc
    for i, part in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        if isinstance(part, int):
            while len(cur) <= part:
                cur.append({} if not isinstance(nxt, int) else [])
            cur = cur[part]
        else:
            if part not in cur or cur[part] is None:
                cur[part] = [] if isinstance(nxt, int) else {}
            cur = cur[part]
    last = parts[-1]
    if isinstance(last, int):
        while len(cur) <= last:
            cur.append(None)
        cur[last] = value
    else:
        cur[last] = value


def _split_path(path: str) -> list:
    parts: list = []
    for seg in path.split("."):
        if not seg:
            continue
        while "[" in seg:
            head, rest = seg.split("[", 1)
            idx, seg = rest.split("]", 1)
            if head:
                parts.append(head)
            parts.append(int(idx))
        if seg:
            parts.append(seg)
    return parts


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

def _money_tol(v: float) -> float:
    # Whole-dollar forms round; percent-of-value absorbs cents rendering drift.
    return max(1.0, 0.005 * abs(v))


def _norm_str(s: Any) -> str:
    return " ".join(str(s).split()).strip().casefold()


def _as_pairs(lst: Any) -> Optional[list[tuple[str, float]]]:
    """Code lists (box 12, box 14, box 20) → sorted (code, amount) pairs."""
    if not isinstance(lst, list):
        return None
    pairs = []
    for item in lst:
        if isinstance(item, dict):
            code = _norm_str(item.get("code", item.get("label", "")))
            amt = item.get("amount", item.get("value"))
            try:
                amt = float(amt) if amt is not None else 0.0
            except (TypeError, ValueError):
                amt = 0.0
            pairs.append((code, amt))
        else:
            pairs.append((_norm_str(item), 0.0))
    return sorted(pairs)


def values_agree(a: Any, b: Any) -> bool:
    """Tolerant equality for the value types that appear on tax forms."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= _money_tol(max(abs(a), abs(b)))
    if isinstance(a, list) and isinstance(b, list):
        pa, pb = _as_pairs(a), _as_pairs(b)
        if pa is None or pb is None or len(pa) != len(pb):
            return False
        return all(ca == cb and abs(xa - xb) <= _money_tol(max(abs(xa), abs(xb)))
                   for (ca, xa), (cb, xb) in zip(pa, pb))
    # Try numeric strings before falling back to string compare.
    try:
        fa, fb = float(str(a).replace(",", "").replace("$", "")), float(str(b).replace(",", "").replace("$", ""))
        return abs(fa - fb) <= _money_tol(max(abs(fa), abs(fb)))
    except ValueError:
        pass
    return _norm_str(a) == _norm_str(b)


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------

def merge_field(text_env: Optional[dict], vision_env: Optional[dict], path: str,
                review_required: list[str]) -> dict:
    """Merge one field. See module docstring for the policy."""
    t_present = is_present(text_env) if text_env else False
    v_present = is_present(vision_env) if vision_env else False

    if t_present and v_present:
        tv, vv = text_env["value"], vision_env["value"]
        if values_agree(tv, vv):
            out = copy.deepcopy(text_env)  # text has the exact digits
            out["confidence"] = CONF_AGREE
            if out["source_anchor"].get("page") is None and vision_env["source_anchor"].get("page") is not None:
                out["source_anchor"]["page"] = vision_env["source_anchor"]["page"]
            out["engines"] = ["text", "vision"]
            return out
        out = copy.deepcopy(vision_env)  # vision reads layout; text may have hopped a column
        out["confidence"] = CONF_DISAGREE
        out["engines"] = ["vision"]
        out["alternates"] = [{"engine": "text", "value": tv, "state": text_env["state"]}]
        review_required.append(path)
        return out

    if t_present or v_present:
        src = text_env if t_present else vision_env
        other = vision_env if t_present else text_env
        out = copy.deepcopy(src)
        out["confidence"] = CONF_SINGLE
        out["engines"] = ["text" if t_present else "vision"]
        if other and other.get("state") == "UNREADABLE":
            # The other engine tried and failed on this box; worth a look.
            review_required.append(path)
        return out

    # Neither engine saw a value: keep the more informative state.
    cands = [e for e in (text_env, vision_env) if e]
    if not cands:
        return make(None, "NOT_PRESENT")
    best = max(cands, key=lambda e: _STATE_RANK.get(e.get("state", "UNREADABLE"), 0))
    out = copy.deepcopy(best)
    out["confidence"] = None
    out["engines"] = []
    return out


def merge(text_doc: Optional[dict], vision_doc: Optional[dict]) -> dict:
    """Merge two envelope documents of the same doc_type into one.

    Either side may be None (single-engine run). The result carries
    `_extraction.merged`, `_extraction.engines` and `_extraction.review_required`.
    Non-envelope top-level scalars (doc_type, tax_year, schema_version) are taken
    from the text document when present, else vision.
    """
    if text_doc is None and vision_doc is None:
        raise ValueError("nothing to merge")
    base = copy.deepcopy(text_doc if text_doc is not None else vision_doc)
    other = vision_doc if text_doc is not None else None

    if text_doc is not None and vision_doc is not None:
        if _norm_str(text_doc.get("doc_type")) != _norm_str(vision_doc.get("doc_type")):
            raise ValueError(
                f"doc_type mismatch: text={text_doc.get('doc_type')!r} vision={vision_doc.get('doc_type')!r}")

    review: list[str] = []
    paths = {p for p, _ in walk(text_doc or {})} | {p for p, _ in walk(vision_doc or {})}
    for path in sorted(paths):
        te = get_path(text_doc, path) if text_doc else None
        ve = get_path(vision_doc, path) if vision_doc else None
        te = te if is_envelope(te) else None
        ve = ve if is_envelope(ve) else None
        set_path(base, path, merge_field(te, ve, path, review))

    ext = base.setdefault("_extraction", {})
    engines: list[str] = []
    if text_doc is not None:
        engines.append("text")
    if vision_doc is not None:
        engines.append("vision")
    ext["engines"] = engines
    ext["merged"] = len(engines) == 2
    ext["review_required"] = sorted(set(review))
    if other is not None:
        for k, v in (other.get("_extraction") or {}).items():
            ext.setdefault(k, v)
    base["schema_version"] = SCHEMA_VERSION
    return base


def review_summary(doc: dict) -> list[str]:
    """Human-readable lines for the fields that need eyes."""
    ext = doc.get("_extraction") or {}
    lines = []
    for path in ext.get("review_required", []):
        env = get_path(doc, path)
        if not is_envelope(env):
            continue
        alt = env.get("alternates") or []
        alt_txt = ", ".join(f"{a['engine']}={a['value']!r}" for a in alt)
        lines.append(f"{path}: value={env['value']!r} ({env['state']}, conf={env.get('confidence')})"
                     + (f" vs {alt_txt}" if alt_txt else ""))
    return lines

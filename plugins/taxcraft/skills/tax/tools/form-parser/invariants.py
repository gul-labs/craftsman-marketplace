#!/usr/bin/env python3
"""
invariants — evaluate the declarative invariants in `doc_types.py` against a
parsed document.

Each invariant is a small arithmetic expression over box ids. This module
compiles it through a whitelist AST walk (names, numbers, arithmetic,
comparisons, boolean ops, calls to the helpers below, and `rules[...]` /
`rules.get(...)` lookups) and evaluates it with an empty builtins table. The
expressions are our own registry data, not user input; the whitelist exists so
a typo in the registry fails loudly instead of doing something surprising.

The one rule that matters: a box the extractor did not observe is None, and an
invariant that touches a None is SKIPPED (reported at INFO as "not evaluable"),
never failed and never treated as zero. `(box_7 or 0)` in an expression is the
explicit opt-in for "absent means zero here", used only where the form itself
defines the box as optional.

Helpers available inside expressions:
    near(a, b, tol=1.0)        |a - b| <= tol
    pct(part, whole, rate, tol=1.0)   |part - whole*rate| <= tol
    has('box_1')               box observed (OBSERVED_VALUE / OBSERVED_ZERO / DERIVED / MANUAL_OVERRIDE)
    sum_of(codes, 'D', 'E')    sum of amounts in a codes list whose code is in the set
    sum_of_boxes('box_1', ...) sum of the named boxes, treating absent as 0
    abs, min, max, round

Pure stdlib. Never modifies anything.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pdf-extractor"))
from envelope import is_envelope, unwrap, is_present  # type: ignore  # noqa: E402

from doc_types import DocType, Invariant, REGISTRY  # noqa: E402

RULES_DIR = Path(__file__).resolve().parent.parent.parent / "rules"

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.Call,
    ast.Name, ast.Load, ast.Constant, ast.Subscript, ast.Attribute, ast.IfExp,
    ast.And, ast.Or, ast.Not, ast.USub, ast.UAdd,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.Tuple, ast.List, ast.keyword,
)
_ALLOWED_CALLS = {"near", "pct", "has", "sum_of", "sum_of_boxes", "abs", "min", "max", "round"}


class InvariantSyntaxError(ValueError):
    pass


class _NotEvaluable(Exception):
    """Raised during evaluation when a referenced box is None."""


def _check_ast(tree: ast.AST, expr: str) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise InvariantSyntaxError(f"disallowed syntax {type(node).__name__} in {expr!r}")
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                if f.id not in _ALLOWED_CALLS:
                    raise InvariantSyntaxError(f"call to {f.id!r} not allowed in {expr!r}")
            elif isinstance(f, ast.Attribute):
                # only rules.get(...)
                if not (isinstance(f.value, ast.Name) and f.value.id == "rules" and f.attr == "get"):
                    raise InvariantSyntaxError(f"attribute call {ast.unparse(f)!r} not allowed in {expr!r}")
            else:
                raise InvariantSyntaxError(f"bad call target in {expr!r}")
        elif isinstance(node, ast.Attribute):
            if not (isinstance(node.value, ast.Name) and node.value.id == "rules" and node.attr == "get"):
                raise InvariantSyntaxError(f"attribute {ast.unparse(node)!r} not allowed in {expr!r}")
        elif isinstance(node, ast.Subscript):
            if not (isinstance(node.value, ast.Name) and node.value.id == "rules"):
                raise InvariantSyntaxError(f"subscript on {ast.unparse(node.value)!r} not allowed in {expr!r}")


def compile_expr(expr: str) -> Any:
    tree = ast.parse(expr, mode="eval")
    _check_ast(tree, expr)
    return compile(tree, f"<invariant:{expr[:40]}>", "eval")


# --------------------------------------------------------------------------
# Namespace
# --------------------------------------------------------------------------

def _num(x: Any) -> float:
    if x is None:
        raise _NotEvaluable()
    if isinstance(x, bool):
        return 1.0 if x else 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.replace(",", "").replace("$", "").strip()
        if s.startswith("(") and s.endswith(")"):
            s = "-" + s[1:-1]
        try:
            return float(s)
        except ValueError:
            raise _NotEvaluable()
    raise _NotEvaluable()


def _near(a: Any, b: Any, tol: Any = 1.0) -> bool:
    return abs(_num(a) - _num(b)) <= _num(tol)


def _pct(part: Any, whole: Any, rate: Any, tol: Any = 1.0) -> bool:
    return abs(_num(part) - _num(whole) * _num(rate)) <= _num(tol)


def _sum_of(codes: Any, *wanted: str) -> float:
    if codes is None:
        return 0.0
    if not isinstance(codes, list):
        raise _NotEvaluable()
    want = {w.upper() for w in wanted}
    total = 0.0
    for item in codes:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).upper().strip()
        if code in want:
            try:
                total += _num(item.get("amount"))
            except _NotEvaluable:
                continue
    return total


def load_rules(tax_year: Optional[int]) -> dict:
    """`rules/federal-<year>.json` as a flat dict of the scalar fields, or {}."""
    if not tax_year:
        return {}
    p = RULES_DIR / f"federal-{tax_year}.json"
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in raw.items() if not isinstance(v, (dict, list))}


def flatten_boxes(doc: dict) -> dict[str, Any]:
    """{box_id: plain value or None} from a schema-2 document (`boxes` +
    `identity` envelopes) or a legacy flat document (top-level scalars)."""
    out: dict[str, Any] = {}
    present: dict[str, bool] = {}
    if isinstance(doc.get("boxes"), dict) or isinstance(doc.get("identity"), dict):
        for section in ("identity", "boxes"):
            for k, v in (doc.get(section) or {}).items():
                out[k] = unwrap(v)
                present[k] = is_present(v)
    else:
        for k, v in doc.items():
            if k.startswith("_") or isinstance(v, (dict,)):
                continue
            if is_envelope(v):
                out[k] = unwrap(v)
                present[k] = is_present(v)
            elif isinstance(v, (int, float, str, list)) and not isinstance(v, bool):
                out[k] = v
                present[k] = v is not None
            elif isinstance(v, bool):
                out[k] = v
                present[k] = True
    out["__present__"] = present  # type: ignore[assignment]
    return out


def _namespace(boxes: dict[str, Any], rules: dict, doc_type: Optional[DocType] = None) -> dict:
    present = boxes.get("__present__", {})
    ns: dict[str, Any] = {}
    if doc_type is not None:
        # Every box the form defines exists in the namespace, absent ones as
        # None, so `(box_7 or 0)` reads as "optional box, absent means zero"
        # while a bare `box_7` still aborts the invariant when unobserved.
        for b in (*doc_type.identity, *doc_type.boxes):
            ns[b.id] = None
    ns.update({k: v for k, v in boxes.items() if k != "__present__"})
    ns.update({
        "rules": rules,
        "near": _near,
        "pct": _pct,
        "has": lambda name: bool(present.get(name)) and ns.get(name) is not None,
        "sum_of": _sum_of,
        "sum_of_boxes": lambda *names: sum(_num(ns[n]) for n in names if ns.get(n) is not None),
        "abs": lambda x: abs(_num(x)),
        "min": lambda *xs: min(_num(x) for x in xs),
        "max": lambda *xs: max(_num(x) for x in xs),
        "round": lambda x, n=0: round(_num(x), n),
    })
    return ns


def _eval(code: Any, ns: dict, expr: str) -> Any:
    try:
        return eval(code, {"__builtins__": {}}, _GuardedNS(ns))  # noqa: S307 - whitelisted AST
    except _NotEvaluable:
        raise
    except TypeError:
        # `None <= 5`, `None + 1` — a referenced box is absent.
        raise _NotEvaluable()
    except KeyError as e:
        raise _NotEvaluable() from e


class _GuardedNS(dict):
    def __missing__(self, key: str) -> Any:
        # Unknown box id → treat as absent, so a registry typo skips instead of crashing.
        raise _NotEvaluable()


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def evaluate(doc: dict, doc_type: Optional[DocType] = None, *, doc_name: str = "") -> list[dict]:
    """Run every invariant of the document's type. Returns finding dicts shaped
    like parse-verify's Finding: severity, check, doc, message, detail, fields.

    Skipped invariants (inputs not observed) are returned at INFO with
    check suffix `.not_evaluable`, so a reviewer can see what was NOT proven.
    """
    if doc_type is None:
        name = str(doc.get("doc_type", ""))
        doc_type = REGISTRY.get(name)
        if doc_type is None:
            try:
                from doc_types import get as _get
                doc_type = _get(name)
            except KeyError:
                return []
    boxes = flatten_boxes(doc)
    ty = doc.get("tax_year")
    try:
        ty = int(unwrap(ty)) if ty is not None else None
    except (TypeError, ValueError):
        ty = None
    rules = load_rules(ty)
    ns = _namespace(boxes, rules, doc_type)

    findings: list[dict] = []
    for inv in doc_type.invariants:
        detail = _detail(inv, ns)
        try:
            if inv.when:
                gate = _eval(compile_expr(inv.when), ns, inv.when)
                if not gate:
                    continue
            ok = _eval(compile_expr(inv.expr), ns, inv.expr)
        except _NotEvaluable:
            findings.append({
                "severity": "INFO", "check": f"{inv.id}.not_evaluable", "doc": doc_name,
                "message": f"Not proven: {inv.message.split(' — ')[0].split('.')[0]} (an input box was not observed).",
                "detail": detail, "fields": list(inv.fields),
            })
            continue
        except InvariantSyntaxError as e:
            findings.append({
                "severity": "MEDIUM", "check": f"{inv.id}.registry_error", "doc": doc_name,
                "message": f"Registry invariant could not be compiled: {e}", "detail": inv.expr,
                "fields": list(inv.fields),
            })
            continue
        if not ok:
            findings.append({
                "severity": inv.severity, "check": inv.id, "doc": doc_name,
                "message": inv.message, "detail": detail, "fields": list(inv.fields),
            })

    # Required boxes that were not observed are findings in their own right.
    present = boxes.get("__present__", {})
    for b in (*doc_type.identity, *doc_type.boxes):
        if b.required and not present.get(b.id):
            findings.append({
                "severity": "HIGH", "check": f"{doc_type.name}.{b.id}.required_missing", "doc": doc_name,
                "message": f"Required box {b.id} ({b.label}) was not observed — do not treat it as zero.",
                "detail": "", "fields": [b.id],
            })
    return findings


def _detail(inv: Invariant, ns: dict) -> str:
    parts = []
    for f in inv.fields:
        v = ns.get(f)
        parts.append(f"{f}={v!r}")
    return f"{inv.expr}  with  " + ", ".join(parts)


def self_check() -> list[str]:
    """Compile every invariant in the registry; return a list of errors."""
    errors = []
    for name, dt in REGISTRY.items():
        for inv in dt.invariants:
            for expr in (inv.expr, inv.when):
                if not expr:
                    continue
                try:
                    compile_expr(expr)
                except (InvariantSyntaxError, SyntaxError) as e:
                    errors.append(f"{name}/{inv.id}: {e}")
    return errors


if __name__ == "__main__":  # pragma: no cover
    errs = self_check()
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    n = sum(len(d.invariants) for d in REGISTRY.values())
    print(f"registry OK — {n} invariants compile across {len(REGISTRY)} doc types")

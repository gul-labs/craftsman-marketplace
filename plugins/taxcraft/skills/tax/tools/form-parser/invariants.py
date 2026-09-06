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
from envelope import is_envelope, unwrap, is_present, state_of  # type: ignore  # noqa: E402

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
    """Sum the amounts of the wanted codes in a code list (W-2 box 12, K-1 box 20).

    `None` means the list was never read, which is not the same as a form with no
    codes on it — summing it to 0 would let an unread box 12 satisfy a deferral
    check. An observed empty list sums to 0, correctly. An entry whose amount is
    unreadable aborts the whole sum for the same reason.
    """
    if codes is None:
        raise _NotEvaluable()
    if not isinstance(codes, list):
        raise _NotEvaluable()
    want = {w.upper() for w in wanted}
    total = 0.0
    for item in codes:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).upper().strip()
        if code in want:
            total += _num(item.get("amount"))  # raises _NotEvaluable if unreadable
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
    `identity` envelopes) or a legacy flat document (top-level scalars).

    Also returns `__present__` and `__state__` side tables. The states matter:
    a box that is NOT_PRESENT was blank on a preprinted information return,
    which contributes nothing to a total, while a box that is UNREADABLE is one
    the extractor failed on — a total built over it is not a total, and the
    invariant that uses it must be skipped rather than answered.
    """
    out: dict[str, Any] = {}
    present: dict[str, bool] = {}
    states: dict[str, str] = {}
    if isinstance(doc.get("boxes"), dict) or isinstance(doc.get("identity"), dict):
        for section in ("identity", "boxes"):
            for k, v in (doc.get(section) or {}).items():
                out[k] = unwrap(v)
                present[k] = is_present(v)
                states[k] = state_of(v) or ("OBSERVED_VALUE" if v is not None else "NOT_PRESENT")
    else:
        for k, v in doc.items():
            if k.startswith("_") or isinstance(v, (dict,)):
                continue
            if is_envelope(v):
                out[k] = unwrap(v)
                present[k] = is_present(v)
                states[k] = state_of(v) or "NOT_PRESENT"
            elif isinstance(v, (int, float, str, list)) and not isinstance(v, bool):
                out[k] = v
                present[k] = v is not None
                states[k] = "OBSERVED_VALUE" if v is not None else "NOT_PRESENT"
            elif isinstance(v, bool):
                out[k] = v
                present[k] = True
                states[k] = "OBSERVED_VALUE"
    out["__present__"] = present  # type: ignore[assignment]
    out["__state__"] = states  # type: ignore[assignment]
    return out


def _make_has(ns: dict, present: dict, unobserved_seen: list):
    """`has('box_3')` — was this box actually observed?

    A gate that answers False because a box was not observed is not the same as
    a gate that answers False because the form genuinely does not apply. The
    first means the invariant went unproven and must say so; the second is a
    silent, correct skip. Recording the misses lets `evaluate()` tell them apart.
    """
    def has(name: str) -> bool:
        ok = bool(present.get(name)) and ns.get(name) is not None
        if not ok:
            unobserved_seen.append(name)
        return ok
    return has


def _make_sum_of_boxes(ns: dict, states: dict[str, str]):
    """`sum_of_boxes('box_1', 'box_2', ...)` over a preprinted return.

    A blank box on an information return reports nothing and contributes 0. A
    box the extractor could not read contributes an unknown amount, so the sum —
    and the invariant built on it — cannot be evaluated at all. Silently
    skipping it would understate the total and let a violation pass.
    """
    def sum_of_boxes(*names: str) -> float:
        total = 0.0
        for n in names:
            if states.get(n) == "UNREADABLE":
                raise _NotEvaluable()
            v = ns.get(n)
            if v is None:
                continue  # blank box: reports nothing
            total += _num(v)
        return total
    return sum_of_boxes


def _namespace(boxes: dict[str, Any], rules: dict, doc_type: Optional[DocType] = None) -> dict:
    present = boxes.get("__present__", {})
    states = boxes.get("__state__", {})
    unobserved_seen: list[str] = []
    ns: dict[str, Any] = {}
    if doc_type is not None:
        # Every box the form defines exists in the namespace, absent ones as
        # None, so `(box_7 or 0)` reads as "optional box, absent means zero"
        # while a bare `box_7` still aborts the invariant when unobserved.
        for b in (*doc_type.identity, *doc_type.boxes):
            ns[b.id] = None
    ns.update({k: v for k, v in boxes.items() if k not in ("__present__", "__state__")})
    ns["__unobserved_seen__"] = unobserved_seen
    ns.update({
        "rules": rules,
        "near": _near,
        "pct": _pct,
        "has": _make_has(ns, present, unobserved_seen),
        "sum_of": _sum_of,
        "sum_of_boxes": _make_sum_of_boxes(ns, states),
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
                del ns["__unobserved_seen__"][:]
                gate = _eval(compile_expr(inv.when), ns, inv.when)
                if not gate:
                    if ns["__unobserved_seen__"]:
                        # The gate closed because a box was never observed, not
                        # because the form does not apply. Report it as unproven
                        # rather than saying nothing, which reads as "checked, fine".
                        missing = ", ".join(sorted(set(ns["__unobserved_seen__"])))
                        findings.append({
                            "severity": "INFO", "check": f"{inv.id}.not_evaluable", "doc": doc_name,
                            "message": f"Not proven: {inv.message.split(' — ')[0].split('.')[0]} "
                                       f"(not observed: {missing}).",
                            "detail": detail, "fields": list(inv.fields),
                        })
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

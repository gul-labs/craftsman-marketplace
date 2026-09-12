#!/usr/bin/env python3
"""
workspace-doctor — report-only health check for the tax workspace layout.

Never modifies or deletes anything. Always exits 0 (this is a diagnostic
report, not a gate) and prints paths only — never file contents — to avoid
leaking PII into logs or terminal scrollback.

CLI:
    python3 doctor.py                # default root: $TAX_WORKSPACE, else the
                                      # current directory — run it from the
                                      # workspace that holds workspace-profile/
    python3 doctor.py --root /path/to/workspace

Checks performed (see README.md for detail on each):
  - Missing canonical workspace-profile files
  - Entity dirs violating the kebab-case slug rule
  - Corporate-intake subfolders (entities/*/corporate/**, incl. nested
    disregarded/*/corporate/**) with PDFs but no _processed.log
  - Empty .parsed/ dirs alongside .txt sidecar files
  - Sync-conflict litter (duplicate downloads, double extensions, wrong-case
    extensions)
  - Loose K-1/tax PDFs at workspace root or individual/ root
  - __pycache__ dirs in the workspace
  - Entity trackers missing: entities/<slug>/carryforwards.json for any entity
    with books; books/capital-accounts.md for partnerships (type taken from the
    labelled `Entity type:` field of entity.md, scanned only until that field is
    found; value never printed)
  - In-place prose history in operative Markdown (supersession.md §8): update
    headings, strikethrough, "kept for the audit trail", History/Change-log
    sections. Lines are matched against a fixed pattern list; the output is the
    path and the rule name, never the matched text
  - Decision-memo lineage (supersession.md §8): every decisions/*.md carries a
    unique `Memo ID`, a `Supersedes` line and a `Superseded by` line, and
    Supersedes / Superseded by pairs are reciprocal. Only the labelled header lines are read; IDs are never
    printed
  - poppler (pdftotext) presence

Content read, in full: (1) entity.md until the `Entity type:` field, (2) operative
Markdown line by line against the pattern list above, (3) decision-memo header
lines. Nothing read is ever printed; findings are paths plus a rule name.

Privacy: any path with a segment containing "privileged" (case-insensitive)
is excluded from every walk and never printed in output — see
check_privileged_excluded / _is_privileged below.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MAX_PATHS_PER_GROUP = 20

CANONICAL_WORKSPACE_PROFILE_FILES = [
    "entities-index.md",
    "owner.md",
    "history.md",
    "bank-accounts.md",
    "slugs.md",
    "federal-accounts.md",
    "org-chart.md",
]

# Directories we should never descend into while walking for litter/PDFs —
# keeps this fast and avoids noise from VCS / editor / node_modules metadata.
SKIP_DIR_NAMES = {".git", "node_modules", ".venv", "venv", "__pycache__", ".DS_Store"}

TAX_PDF_RE = re.compile(r"\bK-?1\b|1099|1040|1065|1120|W-?2\b", re.IGNORECASE)
SYNC_CONFLICT_RE = re.compile(r" \(\d+\)\.[A-Za-z0-9]+$")
MAC_CONFLICT_RE = re.compile(r"-[^/]*\bMac\b[^/]*\.[A-Za-z0-9]+$")
DOUBLE_EXT_RE = re.compile(r"\.(pdf)\.(pdf|PDF|Pdf)$", re.IGNORECASE)
WRONG_CASE_EXT_RE = re.compile(r"\.(Pdf|PDF|pDF|pdF|PDf|PdF)$")


def _default_root() -> Path:
    """The workspace being diagnosed: $TAX_WORKSPACE, else the current directory.

    Deliberately not derived from this script's location. The skill ships as an
    installed plugin, so the tree above it is the plugin cache, not anyone's tax
    workspace — walking up from here produced a confident report about the wrong
    directory, which is worse than failing. The workspace is where the user is.
    """
    env = os.environ.get("TAX_WORKSPACE")
    return Path(env).expanduser().resolve() if env else Path.cwd()


def _is_privileged(path: Path) -> bool:
    """True if any path segment contains 'privileged' (case-insensitive).
    Used to exclude attorney-client-privileged matter folders from every
    walk and from all printed output."""
    return any("privileged" in part.lower() for part in path.parts)


def _rel(root: Path, path: Path) -> str:
    """Render a path relative to the workspace root for display/output."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _iter_dirs(root: Path):
    """Walk root, skipping noisy/irrelevant directories and any directory
    whose path contains a 'privileged' segment (never descended into, never
    reported)."""
    for dirpath, dirnames, filenames in __import__("os").walk(root):
        dp = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIR_NAMES and "privileged" not in d.lower()
        ]
        if _is_privileged(dp):
            continue
        yield dp, dirnames, filenames


def _cap(paths: list[str]) -> list[str]:
    if len(paths) <= MAX_PATHS_PER_GROUP:
        return paths
    return paths[:MAX_PATHS_PER_GROUP] + [f"…and {len(paths) - MAX_PATHS_PER_GROUP} more"]


class Finding:
    def __init__(self, group: str):
        self.group = group
        self.paths: list[str] = []

    def add(self, p: Path | str) -> None:
        self.paths.append(str(p))

    @property
    def count(self) -> int:
        return len(self.paths)


def check_workspace_profile_files(root: Path) -> Finding:
    f = Finding("Missing canonical workspace-profile files")
    profile_dir = root / "workspace-profile"
    for name in CANONICAL_WORKSPACE_PROFILE_FILES:
        if not (profile_dir / name).is_file():
            f.add(_rel(root, profile_dir / name))
    return f


def check_kebab_case_slugs(root: Path) -> Finding:
    """Entity dirs under entities/ should be kebab-case: lowercase, digits,
    hyphens only. Flag anything with spaces or uppercase letters."""
    f = Finding("Entity dirs violating kebab-case slug rule")
    entities_dir = root / "entities"
    if not entities_dir.is_dir():
        return f
    kebab_re = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    for child in sorted(entities_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if _is_privileged(child):
            continue
        if not kebab_re.match(child.name):
            f.add(_rel(root, child))
    return f


def _iter_corporate_intake_dirs(root: Path):
    """Yield every corporate-intake directory: entities/*/corporate/** and
    nested entities/*/disregarded/*/corporate/** (any depth of nested
    disregarded/<slug>/), skipping privileged paths. This is the scope of
    the PDFs-without-_processed.log check — corporate intake surfaces only,
    not every folder in the workspace that happens to contain a PDF."""
    entities_dir = root / "entities"
    if not entities_dir.is_dir():
        return
    for entity_dir in sorted(entities_dir.iterdir()):
        if not entity_dir.is_dir() or _is_privileged(entity_dir):
            continue
        # entities/<slug>/corporate/**
        corp_dir = entity_dir / "corporate"
        if corp_dir.is_dir() and not _is_privileged(corp_dir):
            for dirpath, _dirnames, filenames in _iter_dirs(corp_dir):
                yield dirpath, filenames
        # entities/<slug>/disregarded/**/corporate/** (any nesting depth)
        for corp_dir in entity_dir.rglob("disregarded/*/corporate"):
            if not corp_dir.is_dir() or _is_privileged(corp_dir):
                continue
            for dirpath, _dirnames, filenames in _iter_dirs(corp_dir):
                yield dirpath, filenames


def check_corporate_pdfs_without_processed_log(root: Path) -> Finding:
    """Corporate-intake subfolders (entities/*/corporate/** and nested
    disregarded/*/corporate/**) that directly contain PDFs but have no
    _processed.log file in that same folder. Scoped to corporate intake
    surfaces only — see governance.md's intake pipeline — not every
    PDF-containing folder in the workspace (tax-doc intake under FY<YYYY>/
    uses a different, non-log-based mechanism)."""
    f = Finding("Corporate-intake folders with PDFs but no _processed.log")
    for dirpath, filenames in _iter_corporate_intake_dirs(root):
        pdfs = [fn for fn in filenames if fn.lower().endswith(".pdf")]
        if not pdfs:
            continue
        if "_processed.log" in filenames:
            continue
        f.add(_rel(root, dirpath))
    return f


def check_empty_parsed_dirs(root: Path) -> Finding:
    """.parsed/ dirs that are empty while a sibling .txt sidecar file exists
    (a sign the parse cache is being skipped rather than populated)."""
    f = Finding("Empty .parsed/ dirs alongside .txt sidecars")
    for dirpath, dirnames, filenames in _iter_dirs(root):
        if dirpath.name != ".parsed":
            continue
        try:
            has_content = any(dirpath.iterdir())
        except OSError:
            continue
        if has_content:
            continue
        sibling_txts = list(dirpath.parent.glob("*.txt"))
        if sibling_txts:
            f.add(_rel(root, dirpath))
    return f


def check_sync_conflict_litter(root: Path) -> Finding:
    f = Finding("Sync-conflict litter (duplicates, double/wrong-case extensions)")
    for dirpath, _dirnames, filenames in _iter_dirs(root):
        for fn in filenames:
            p = dirpath / fn
            if SYNC_CONFLICT_RE.search(fn):
                f.add(_rel(root, p))
            elif MAC_CONFLICT_RE.search(fn):
                f.add(_rel(root, p))
            elif DOUBLE_EXT_RE.search(fn):
                f.add(_rel(root, p))
            elif WRONG_CASE_EXT_RE.search(fn):
                f.add(_rel(root, p))
    return f


def check_loose_tax_pdfs(root: Path) -> Finding:
    """K-1/tax PDFs sitting directly at workspace root or individual/ root
    (i.e., outside any FY<YYYY> folder) — these should be filed, not loose."""
    f = Finding("Loose K-1/tax PDFs outside FY folders")
    candidates = [root, root / "individual"]
    for d in candidates:
        if not d.is_dir() or _is_privileged(d):
            continue
        for entry in sorted(d.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix.lower() != ".pdf":
                continue
            if TAX_PDF_RE.search(entry.name):
                f.add(_rel(root, entry))
    return f


def check_pycache_dirs(root: Path) -> Finding:
    """Bytecode caches anywhere in the workspace.

    This used to look only under `<root>/.claude/skills/tax`, the location the skill
    occupied before it shipped as a plugin. That directory no longer exists in a
    workspace, so the check silently passed on every run. Scan the workspace itself —
    which is what the sync-conflict rationale in tools/README.md was ever about.
    """
    f = Finding("__pycache__ dirs in the workspace")
    for p in root.rglob("__pycache__"):
        if p.is_dir() and not _is_privileged(p):
            f.add(_rel(root, p))
    return f


def _books_python() -> str | None:
    """Prefer the books venv so bean-check is available without polluting PATH."""
    venv = Path.home() / ".local" / "state" / "business-books" / "venv" / "bin" / "python"
    if venv.is_file():
        return str(venv)
    return shutil.which("python3")


def check_bean_ledgers(root: Path) -> Finding:
    """Per-entity bean-check on entities/**/books/ledger.beancount."""
    f = Finding("Beancount ledgers failing bean-check")
    py = _books_python()
    if not py:
        f.add("(python not found — skipped bean-check)")
        return f
    bean_check = Path(py).parent / "bean-check"
    if not bean_check.exists():
        f.add("bean-check executable missing in books venv")
        return f
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONPATH"] = str(root / "books-tooling") + (
        ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for ledger in sorted(root.glob("entities/**/books/ledger.beancount")):
        if _is_privileged(ledger):
            continue
        try:
            proc = subprocess.run(
                [str(bean_check), str(ledger)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(root),
                env=env,
            )
        except Exception as e:
            f.add(f"{_rel(root, ledger)} ({e})")
            continue
        if proc.returncode != 0:
            f.add(_rel(root, ledger))
    return f


def check_xledger(root: Path) -> Finding:
    f = Finding("xledger-check (intercompany mirrors)")
    script = root / "books-tooling" / "scripts" / "xledger-check.py"
    py = _books_python()
    if not script.is_file() or not py:
        return f
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONPATH"] = str(root / "books-tooling") + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [py, "-B", str(script)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(root),
            env=env,
        )
    except Exception as e:
        f.add(str(e))
        return f
    if proc.returncode != 0:
        f.add("xledger-check failed — see books-tooling/scripts/xledger-check.py")
        err = (proc.stdout or proc.stderr or "").strip().splitlines()
        for line in err[:5]:
            f.add(line)
    return f


def check_ledger_export_staleness(root: Path) -> Finding:
    """Flag ledgers older than the newest bank-cc CSV in that entity's tax source."""
    f = Finding("Ledgers older than latest bank/CSV export")
    for ledger in sorted(root.glob("entities/**/books/ledger.beancount")):
        if _is_privileged(ledger):
            continue
        entity_root = ledger.parent.parent  # books/ -> entity
        csvs = list((entity_root / "tax").glob("FY*/source/bank-cc/**/*.csv")) + list(
            (entity_root / "tax").glob("FY*/source/bank-cc/**/*.CSV")
        )
        if not csvs:
            continue
        newest = max(csvs, key=lambda p: p.stat().st_mtime)
        if newest.stat().st_mtime > ledger.stat().st_mtime + 1:
            f.add(f"{_rel(root, ledger)}  (newer export: {_rel(root, newest)})")
    return f


ENTITY_TYPE_RE = re.compile(r"^\s*[-*]?\s*\*{0,2}Entity type\*{0,2}\s*:\s*(.+?)\s*$", re.IGNORECASE)


def _entity_type(entity_md: Path) -> str | None:
    """Return the value of the `Entity type:` field in an entity.md, or None.

    This is the ONE place the doctor reads file content: it scans entity.md
    line by line until the labelled field (the canonical
    `templates/entity-config.md.template` line `- **Entity type**: …`) is found
    or the file ends, then stops. The value is used only to classify the entity
    and is never printed; no other file is opened.
    """
    try:
        with entity_md.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                m = ENTITY_TYPE_RE.match(line)
                if m:
                    return m.group(1)
    except Exception:
        return None
    return None


def _is_partnership_type(value: str) -> bool:
    v = value.lower()
    return "partnership" in v and "smllc" not in v and "disregarded" not in v


def check_entity_trackers(root: Path) -> Finding:
    """Every regarded entity that keeps books must carry its carryforward tracker,
    and every partnership must carry a capital-accounts file.

    A section 704(d) suspended loss, an EBIE allocation, or a passed-through credit
    that lives only in prose is not tracked. Entity type comes from the labelled
    `Entity type:` field of entity.md (see _entity_type); an entity whose type
    cannot be read is reported as such rather than silently skipped. Report-only,
    paths only.
    """
    f = Finding("Entity trackers missing (carryforwards.json / books/capital-accounts.md / unreadable entity type)")
    for entity_md in sorted(root.glob("entities/*/entity.md")):
        if _is_privileged(entity_md):
            continue
        entity_root = entity_md.parent
        has_books = (entity_root / "books").is_dir()
        if has_books and not (entity_root / "carryforwards.json").is_file():
            f.add(_rel(root, entity_root / "carryforwards.json"))
        etype = _entity_type(entity_md)
        if etype is None:
            f.add(f"{_rel(root, entity_md)}  (no readable `Entity type:` field — cannot classify)")
            continue
        if _is_partnership_type(etype) and not (entity_root / "books" / "capital-accounts.md").is_file():
            f.add(_rel(root, entity_root / "books" / "capital-accounts.md"))
    return f


# --- supersession.md checks --------------------------------------------------

# Only these top-level roots hold operative prose the rule governs.
SUPERSESSION_ROOTS = ("workspace-profile", "individual", "entities")

# Any path segment named here is a record, evidence, or a folder with its own
# format: never scanned for in-place prose history.
PROSE_HISTORY_SKIP_DIRS = {
    "decisions", "notes", ".computed", ".parsed", "filed", "amended", "archive",
    "source", "records", "matters", "corporate", "contracts", "books", "accounts",
    "statements", "subscription", "transcripts", "issued", "check-images",
}
# Trackers and logs with their own row-based formats (supersession.md §1): rows are
# events, appended/closed/withdrawn per template, so history sections are by design.
PROSE_HISTORY_SKIP_FILES = {
    "history.md", "open-questions.md", "pending-docs.md",
    "cross-entity-followup-log.md", "open-items-tracker.md",
}

_H = r"^\s{0,3}#{1,6}\s*"
# (rule name, regex). Each is a shape agents have actually written when annotating
# a changed answer in place. The rule name is printed; the matched line never is.
PROSE_HISTORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("update-block heading (§0a-style)",
     re.compile(_H + r"(§\s*)?0[a-z]\b", re.IGNORECASE)),
    ("update/revision heading",
     re.compile(_H + r"(update[sd]?|revised|revisions?)\b", re.IGNORECASE)),
    ("dated update heading",
     re.compile(_H + r".*\b(update[sd]?|revised|amended)\s*\(\s*\d{4}-\d{2}-\d{2}", re.IGNORECASE)),
    ("history/prior-analysis section",
     re.compile(_H + r"(history|change ?log|prior analysis|previous (analysis|version)|superseded)\b", re.IGNORECASE)),
    ("strikethrough",
     re.compile(r"~~\S")),
    ("audit-trail retention prose",
     re.compile(r"\b(kept|retained|preserved)\s+for\s+(the\s+)?audit\s+trail\b", re.IGNORECASE)),
]


def _iter_operative_markdown(root: Path):
    """Yield every *.md under the supersession roots that is operative prose:
    not inside a record/evidence folder, not an append-only log, not privileged."""
    for top in SUPERSESSION_ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in _iter_dirs(base):
            dirnames[:] = [d for d in dirnames if d not in PROSE_HISTORY_SKIP_DIRS]
            rel_parts = set(dirpath.relative_to(root).parts)
            if rel_parts & PROSE_HISTORY_SKIP_DIRS:
                continue
            for fn in sorted(filenames):
                if not fn.lower().endswith(".md") or fn in PROSE_HISTORY_SKIP_FILES:
                    continue
                yield dirpath / fn


# CommonMark fence: a run of 3+ backticks or tildes, optionally followed by an info
# string. A fence closes only on the same character with a run at least as long.
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")


def _prose_history_rules_hit(path: Path) -> list[str]:
    """Return the names of every PROSE_HISTORY_RULES rule that matches a line of
    `path`, ignoring fenced code blocks. Line text is never returned."""
    hits: list[str] = []
    fence: tuple[str, int] | None = None  # (marker char, opening run length)
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                stripped = line.lstrip()
                m = _FENCE_RE.match(stripped)
                if m:
                    ch, run = m.group(1)[0], len(m.group(1))
                    if fence is None:
                        fence = (ch, run)  # open
                        continue
                    if ch == fence[0] and run >= fence[1] and not m.group(2).strip():
                        fence = None  # close: same char, at least as long, nothing after it
                        continue
                    # a shorter or different-char run inside an open fence is content
                if fence is not None:
                    continue
                for name, rx in PROSE_HISTORY_RULES:
                    if name not in hits and rx.search(line):
                        hits.append(name)
    except Exception:
        return hits
    return hits


def check_in_place_prose_history(root: Path) -> Finding:
    """Operative Markdown carrying superseded content in the reading path —
    the pattern supersession.md exists to stop. Report-only: path and rule
    name(s) only; the matched text is never printed."""
    f = Finding("In-place prose history in operative files (supersession.md)")
    for md in _iter_operative_markdown(root):
        hits = _prose_history_rules_hit(md)
        if hits:
            f.add(f"{_rel(root, md)}  ({'; '.join(hits)})")
    return f


MEMO_FIELD_RE = re.compile(
    r"^\s*\*\*(Memo ID|Supersedes|Superseded by)\s*:?\*\*\s*:?\s*(.*?)\s*$", re.IGNORECASE
)
_MEMO_EMPTY = {"", "none", "-", "—", "–", "n/a"}


def _memo_header(path: Path) -> dict[str, str | None]:
    """Read only the labelled header lines of a decision memo (stop at the first
    `## ` heading). Returns {field: value-or-None}; a missing line is None, an
    empty/none/placeholder value is ''. Values are used for reciprocity checks
    only and are never printed."""
    out: dict[str, str | None] = {"memo id": None, "supersedes": None, "superseded by": None}
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                if line.startswith("## "):
                    break
                m = MEMO_FIELD_RE.match(line)
                if not m:
                    continue
                val = m.group(2).strip().strip("`").strip()
                if val.startswith("<") and val.endswith(">"):
                    val = ""  # unfilled template placeholder
                if val.lower() in _MEMO_EMPTY:
                    val = ""
                out[m.group(1).lower()] = val
    except Exception:
        pass
    return out


def check_decision_memo_lineage(root: Path) -> Finding:
    """Every decisions/*.md carries a unique Memo ID and a Supersedes line; a
    memo named in another's Supersedes exists in the same folder and carries the
    reciprocal Superseded by, and vice versa (supersession.md §4–§5). Header
    lines only are read; IDs are never printed."""
    f = Finding("Decision-memo lineage (supersession.md)")
    seen_ids: dict[str, list[Path]] = {}
    folders: list[tuple[Path, dict[Path, dict[str, str | None]]]] = []
    for top in SUPERSESSION_ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for dirpath, _dirnames, filenames in _iter_dirs(base):
            if dirpath.name != "decisions":
                continue
            memos = {
                dirpath / fn: _memo_header(dirpath / fn)
                for fn in sorted(filenames)
                if fn.lower().endswith(".md")
            }
            folders.append((dirpath, memos))
            for p, h in memos.items():
                if h["memo id"]:
                    seen_ids.setdefault(h["memo id"], []).append(p)
    for mid, paths in seen_ids.items():
        if len(paths) > 1:
            for p in paths:
                f.add(f"{_rel(root, p)}  (duplicate Memo ID)")
    for _dirpath, memos in folders:
        by_id = {h["memo id"]: p for p, h in memos.items() if h["memo id"]}
        for p, h in memos.items():
            if not h["memo id"]:
                f.add(f"{_rel(root, p)}  (no Memo ID line)")
                continue
            if h["supersedes"] is None:
                f.add(f"{_rel(root, p)}  (no Supersedes line)")
            if h["superseded by"] is None:
                f.add(f"{_rel(root, p)}  (no Superseded by line)")
            if h["supersedes"]:
                prev = by_id.get(h["supersedes"])
                if prev is None:
                    f.add(f"{_rel(root, p)}  (Supersedes names a memo not in this folder)")
                elif memos[prev]["superseded by"] != h["memo id"]:
                    f.add(f"{_rel(root, prev)}  (predecessor not stamped Superseded by)")
            if h["superseded by"]:
                nxt = by_id.get(h["superseded by"])
                if nxt is None:
                    f.add(f"{_rel(root, p)}  (Superseded by names a memo not in this folder)")
                elif memos[nxt]["supersedes"] != h["memo id"]:
                    f.add(f"{_rel(root, p)}  (Superseded by names a memo that does not supersede this one)")
    return f


def check_poppler() -> tuple[bool, str]:
    exe = shutil.which("pdftotext")
    if not exe:
        return False, "pdftotext not found on PATH — install poppler (`brew install poppler`)"
    try:
        proc = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True, timeout=5)
        version_line = (proc.stderr or proc.stdout or "").splitlines()[0] if (proc.stderr or proc.stdout) else "unknown version"
        return True, version_line.strip()
    except Exception as e:  # pragma: no cover - defensive only
        return False, f"pdftotext found at {exe} but `-v` failed: {e}"


def run(root: Path) -> int:
    if not root.is_dir():
        print(f"Error: root does not exist or is not a directory: {root}", file=sys.stderr)
        print("(Report-only tool — exiting 0 regardless.)", file=sys.stderr)
        return 0

    print("=" * 72)
    print("  workspace-doctor — report-only diagnostic (nothing is modified)")
    print(f"  Root: {root}")
    print("=" * 72)

    findings: list[Finding] = [
        check_workspace_profile_files(root),
        check_kebab_case_slugs(root),
        check_corporate_pdfs_without_processed_log(root),
        check_empty_parsed_dirs(root),
        check_sync_conflict_litter(root),
        check_loose_tax_pdfs(root),
        check_pycache_dirs(root),
        check_bean_ledgers(root),
        check_xledger(root),
        check_ledger_export_staleness(root),
        check_entity_trackers(root),
        check_in_place_prose_history(root),
        check_decision_memo_lineage(root),
    ]

    total_issues = 0
    for f in findings:
        total_issues += f.count
        print(f"\n{f.group}: {f.count}")
        for p in _cap(f.paths):
            print(f"  - {p}")

    poppler_ok, poppler_msg = check_poppler()
    print(f"\npoppler (pdftotext): {'OK' if poppler_ok else 'MISSING'} — {poppler_msg}")
    if not poppler_ok:
        total_issues += 1

    print("\n" + "=" * 72)
    print(f"  Summary: {total_issues} issue(s) flagged across {len(findings) + 1} checks.")
    print("  This tool never modifies or deletes anything — review findings manually.")
    print("=" * 72)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Report-only health check for the tax workspace layout.")
    ap.add_argument("--root", default=None, help="Workspace root (default: $TAX_WORKSPACE, else the current directory)")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve() if args.root else _default_root()
    return run(root)


if __name__ == "__main__":
    sys.exit(main())

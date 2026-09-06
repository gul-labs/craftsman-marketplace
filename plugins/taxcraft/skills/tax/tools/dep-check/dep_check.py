#!/usr/bin/env python3
"""One-shot dependency preflight for the tax skill.

Answers three questions in a single call, so the model does not have to remember
five separate probe commands and does not have to discover a missing dependency
halfway through a close:

  1. Is the skill itself installed intact? (the shipped tree, not the workspace)
  2. Is every REQUIRED external dependency present?
  3. For anything missing, what is the exact command that fixes it on this machine?

Design notes:

- Stdlib only. A dependency checker that needs a dependency installed is useless
  precisely when it is needed.
- It never installs anything. The fix command is printed for a human to approve;
  see `dependencies.md` for why silent installs are prohibited here.
- Required vs optional is decided by blast radius, not by convenience. Poppler is
  required because without it every PDF path in `parsing.md` is dead and the only
  remaining option is Read-on-PDF, which silently misreads columns on tax forms.
  `ocrmypdf` is optional because it is rung 3 of a ladder whose first two rungs
  handle the large majority of documents.

- Presence is not capability. `--self-test` goes further and runs the shipped PDF
  fixture corpus through the real extraction pipeline on THIS machine, because
  "poppler is on the PATH" and "poppler on this machine extracts a W-2 correctly"
  are different claims. A build that renders the fixtures differently, a locale
  that reformats numbers, a `pdftotext` too old for `-layout` as we use it — each
  passes the presence check and fails the corpus. The repository's CI proves the
  parsers work on the maintainer's machine; `--self-test` is how a user proves it
  on theirs, before a real document is touched.

Usage:

    python3 -B "$TAX_SKILL/tools/dep-check/dep_check.py"
    python3 -B "$TAX_SKILL/tools/dep-check/dep_check.py" --json
    python3 -B "$TAX_SKILL/tools/dep-check/dep_check.py" --self-test

Exit codes: 0 = every required dependency present (and, with --self-test, the
fixture corpus parsed correctly); 1 = at least one missing or a self-test failure.
Optional dependencies never affect the exit code.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]

MIN_PYTHON = (3, 9)

# Files whose absence means the install is broken rather than merely incomplete.
# Deliberately short: one entry per shipped subsystem, so a truncated or partial
# copy is caught without this list turning into a manifest that rots on every
# rename.
INSTALL_MARKERS = (
    "SKILL.md",
    "authority.md",
    "parsing.md",
    "dependencies.md",
    "rules/manifest.json",
    "tools/pdf-extractor/pdf_extract.py",
    "tools/form-parser/doc_types.py",
    "evals/_deps.py",
    "evals/validate_rules.py",
    "templates",
    "scenarios",
)


def _poppler_fix() -> str:
    system = platform.system()
    if system == "Darwin":
        return "brew install poppler"
    if system == "Windows":
        return "choco install poppler"
    if system == "Linux":
        # Probe the package manager rather than parsing /etc/os-release: the
        # binary that exists is the one that can run, whatever the distro claims.
        if shutil.which("apt-get") or shutil.which("apt"):
            return "sudo apt install poppler-utils"
        if shutil.which("dnf"):
            return "sudo dnf install poppler-utils"
        if shutil.which("pacman"):
            return "sudo pacman -S poppler"
        if shutil.which("zypper"):
            return "sudo zypper install poppler-tools"
        return "install poppler-utils with your distribution's package manager"
    return "install poppler for your platform (provides pdftotext, pdftoppm, pdfinfo)"


def _pip_fix(package: str) -> str:
    # A virtualenv is active when the running interpreter is not the base one.
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if in_venv:
        return f"pip install {package}"
    return f"pip install --user {package}    # or: uv add {package}"


def _have_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        # A namespace package with a broken parent raises rather than returning
        # None. Either way the import the caller cares about will not work.
        return False


def _have_command(name: str) -> bool:
    return shutil.which(name) is not None


def _command_version(name: str, flags: tuple[str, ...] = ("--version",)) -> str | None:
    """Best-effort version string; None when the tool is absent or silent.

    Poppler prints its banner to stderr, exits non-zero, and treats `--version` as
    a filename to open — so the flag is per-binary and the return code is ignored.
    Output that reads as an error is discarded rather than reported as a version;
    a wrong version string is worse than none, because it looks verified.
    """
    if not _have_command(name):
        return None
    for flag in flags:
        try:
            proc = subprocess.run(
                [name, flag],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        output = (proc.stdout or "") + (proc.stderr or "")
        first = output.strip().splitlines()
        if first and "error" not in first[0].lower():
            return first[0].strip()
    return None


def check_install() -> list[dict]:
    """Verify the shipped skill tree, not the user's workspace."""
    missing = [marker for marker in INSTALL_MARKERS if not (SKILL_ROOT / marker).exists()]
    if missing:
        return [
            {
                "name": "taxcraft skill files",
                "kind": "install",
                "required": True,
                "present": False,
                "detail": f"missing under {SKILL_ROOT}: {', '.join(missing)}",
                "purpose": "the skill's own instructions, rules, templates, and validators",
                "consequence": "sub-skill routes and validators referenced by SKILL.md are unreachable",
                "fix": (
                    "reinstall the plugin: /plugin uninstall taxcraft, then "
                    "/plugin install taxcraft@craftsman-marketplace — the install is "
                    "incomplete, not misconfigured"
                ),
            }
        ]
    return [
        {
            "name": "taxcraft skill files",
            "kind": "install",
            "required": True,
            "present": True,
            "detail": f"intact at {SKILL_ROOT}",
            "purpose": "the skill's own instructions, rules, templates, and validators",
            "consequence": "",
            "fix": "",
        }
    ]


def check_python() -> dict:
    current = sys.version_info[:3]
    ok = current >= MIN_PYTHON
    return {
        "name": "python",
        "kind": "runtime",
        "required": True,
        "present": ok,
        "detail": ".".join(str(part) for part in current),
        "purpose": "every tool and validator in the skill",
        "consequence": "no tool or validator runs at all",
        "fix": "" if ok else f"install Python {'.'.join(str(p) for p in MIN_PYTHON)} or newer",
    }


def check_poppler() -> list[dict]:
    results = []
    fix = _poppler_fix()
    for binary, purpose, consequence in (
        (
            "pdftotext",
            "layout-preserving text extraction from every PDF (parsing.md rung 1)",
            "no PDF can be read correctly — Read-on-PDF silently misreads tax-form columns",
        ),
        (
            "pdftoppm",
            "rasterizing scanned PDFs to PNG for the vision path (parsing.md rung 2)",
            "scanned documents cannot be read at all",
        ),
        (
            "pdfinfo",
            "page-count and producer detection in pdf-extractor",
            "the extractor cannot page-chunk large documents or key vendor layout templates",
        ),
        (
            "pdffonts",
            "font inspection for the text-quality gate (tools/pdf-extractor/quality.py)",
            "garbage text from fonts without a ToUnicode map is harder to detect; the gate falls back to text statistics alone",
        ),
    ):
        present = _have_command(binary)
        results.append(
            {
                "name": binary,
                "kind": "binary",
                "required": True,
                "present": present,
                "detail": _command_version(binary, ("-v",)) or ("" if present else "not on PATH"),
                "purpose": purpose,
                "consequence": consequence,
                "fix": "" if present else fix,
            }
        )
    return results


def check_packages() -> list[dict]:
    results = []
    for module, package, purpose, consequence in (
        (
            "jsonschema",
            "jsonschema",
            "schema enforcement in every evals/ validator",
            "no artifact is schema-checked; a validator that cannot run is not a validator that passed",
        ),
        (
            "markdown_it",
            "markdown-it-py",
            "markdown block scoping in the reference-pointer checks",
            "pointer and block-scoping checks cannot run",
        ),
    ):
        present = _have_module(module)
        results.append(
            {
                "name": package,
                "kind": "package",
                "required": True,
                "present": present,
                "detail": "" if present else "not importable",
                "purpose": purpose,
                "consequence": consequence,
                "fix": "" if present else _pip_fix(package),
            }
        )
    return results


def check_optional() -> list[dict]:
    results = []

    for binary, package, purpose in (
        (
            "pdftk",
            "pdftk-java" if platform.system() == "Darwin" else "pdftk",
            "AcroForm field reading when pypdf is absent (parsing.md rung 0)",
        ),
        (
            "ocrmypdf",
            "ocrmypdf",
            "OCR fallback for scanned PDFs (parsing.md rung 3)",
        ),
        (
            "bean-check",
            "beancount",
            "ledger validation in workspace-doctor, for workspaces that keep Beancount books",
        ),
    ):
        present = _have_command(binary)
        results.append(
            {
                "name": binary,
                "kind": "binary",
                "required": False,
                "present": present,
                "detail": "" if present else "not on PATH",
                "purpose": purpose,
                "consequence": "that fallback rung is skipped; the rungs above it still work",
                "fix": "" if present else _pip_fix(package),
            }
        )

    present = _have_module("pypdf")
    results.append(
        {
            "name": "pypdf",
            "kind": "package",
            "required": False,
            "present": present,
            "detail": "" if present else "not importable",
            "purpose": "exact AcroForm field values from fillable PDFs (parsing.md rung 0)",
            "consequence": "rung 0 is skipped unless pdftk is present; vision and text rungs still work",
            "fix": "" if present else _pip_fix("pypdf"),
        }
    )

    present = _have_module("pdfplumber")
    results.append(
        {
            "name": "pdfplumber",
            "kind": "package",
            "required": False,
            "present": present,
            "detail": "" if present else "not importable",
            "purpose": "table extraction for stubborn PDF grids (parsing.md rung 4)",
            "consequence": "that fallback rung is skipped; the rungs above it still work",
            "fix": "" if present else _pip_fix("pdfplumber"),
        }
    )
    return results


def collect() -> list[dict]:
    return [
        *check_install(),
        check_python(),
        *check_poppler(),
        *check_packages(),
        *check_optional(),
    ]


def render(results: list[dict]) -> str:
    lines: list[str] = []
    missing_required = [r for r in results if r["required"] and not r["present"]]
    missing_optional = [r for r in results if not r["required"] and not r["present"]]

    lines.append("")
    lines.append(f"taxcraft dependency preflight — skill root: {SKILL_ROOT}")
    lines.append("")

    for result in results:
        mark = "ok  " if result["present"] else ("MISS" if result["required"] else "opt ")
        detail = f"  ({result['detail']})" if result["detail"] else ""
        lines.append(f"  [{mark}] {result['name']}{detail}")

    lines.append("")
    if not missing_required:
        lines.append("All required dependencies present. Optional rungs missing: "
                     + (", ".join(r["name"] for r in missing_optional) or "none"))
        lines.append("")
        return "\n".join(lines)

    lines.append("MISSING REQUIRED — do not treat an unrun check as a passed check.")
    lines.append("")
    for result in missing_required:
        lines.append(f"  {result['name']}")
        lines.append(f"    used for  : {result['purpose']}")
        lines.append(f"    without it: {result['consequence']}")
        lines.append(f"    fix       : {result['fix']}")
        lines.append("")

    combined = install_block(results, include_optional=False)
    if combined:
        lines.append("One block that fixes everything required, for the user to approve:")
        lines.append("")
        for cmd in combined:
            lines.append(f"    {cmd}")
        lines.append("")

    lines.append("Propose these to the user for approval. Do not run them silently,")
    lines.append("and do not proceed with work that depends on what is missing.")
    lines.append("")
    return "\n".join(lines)


def install_block(results: list[dict], *, include_optional: bool = False) -> list[str]:
    """The deduplicated fix commands for everything missing, in install order.

    Presented as one block so the user approves a single step instead of five.
    It is still printed, never run: `dependencies.md` prohibits silent installs,
    and some of these need sudo or a package manager the user may not want used.
    """
    wanted = [r for r in results if not r["present"] and r.get("fix")
              and (r["required"] or include_optional)]
    seen: list[str] = []
    for r in sorted(wanted, key=lambda r: (not r["required"], r["kind"] != "binary", r["name"])):
        if r["fix"] not in seen:
            seen.append(r["fix"])
    return seen


def run_self_test() -> dict:
    """Run the shipped fixture corpus through the real pipeline on this machine.

    Presence checks prove a binary exists. This proves the chain works here: the
    same PDFs the maintainer's CI parses are parsed again with the user's own
    poppler build, Python and locale, and compared to checked-in golden values.
    A failure here means real documents will be misread on this machine — the
    one failure mode a dependency list cannot catch.
    """
    suites = [
        ("form-parser fixture corpus", SKILL_ROOT / "tools/form-parser/test_form_parser.py"),
        ("extractor and quality gate", SKILL_ROOT / "tools/pdf-extractor/test_pdf_extract.py"),
        ("parsed-JSON invariants", SKILL_ROOT / "tools/parse-verify/test_verify.py"),
        ("invariant registry compiles", SKILL_ROOT / "tools/form-parser/invariants.py"),
    ]
    out: dict = {"ran": [], "ok": True}
    for label, script in suites:
        if not script.is_file():
            out["ran"].append({"suite": label, "status": "missing", "detail": f"{script.name} is not installed"})
            out["ok"] = False
            continue
        try:
            proc = subprocess.run(
                [sys.executable, "-B", str(script)],
                capture_output=True, text=True, timeout=300, cwd=str(SKILL_ROOT),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            out["ran"].append({"suite": label, "status": "error", "detail": str(exc)})
            out["ok"] = False
            continue
        tail = (proc.stdout or "").strip().splitlines()
        out["ran"].append({
            "suite": label,
            "status": "pass" if proc.returncode == 0 else "fail",
            "detail": "\n".join(tail[-12:]) + (("\n" + (proc.stderr or "").strip()[-800:]) if proc.returncode else ""),
        })
        if proc.returncode != 0:
            out["ok"] = False
    return out


def render_self_test(report: dict) -> str:
    lines = ["", "Self-test — the shipped fixture corpus, parsed on this machine", ""]
    for entry in report["ran"]:
        mark = {"pass": "ok  ", "fail": "FAIL", "missing": "MISS", "error": "ERR "}[entry["status"]]
        lines.append(f"  [{mark}] {entry['suite']}")
        if entry["status"] != "pass":
            for line in entry["detail"].splitlines():
                lines.append(f"         {line}")
    lines.append("")
    if report["ok"]:
        lines.append("The extraction chain works on this machine: every fixture parsed to its")
        lines.append("known-correct values. This does not vouch for any particular real document —")
        lines.append("the vision cross-check and `parse-verify` still run on each one.")
    else:
        lines.append("A fixture parsed incorrectly HERE. Do not parse real tax documents until this")
        lines.append("is resolved: the same defect will misread them silently. Report the output")
        lines.append("above with your platform and `pdftotext -v` output.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check that the tax skill is installed intact and its dependencies are present."
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--install-commands", action="store_true",
                        help="print only the commands that fix what is missing (including optional rungs), one per line")
    parser.add_argument("--self-test", action="store_true",
                        help="also parse the shipped PDF fixture corpus on this machine and compare to golden values")
    args = parser.parse_args()

    results = collect()
    missing_required = [r for r in results if r["required"] and not r["present"]]

    if args.install_commands:
        for cmd in install_block(results, include_optional=True):
            print(cmd)
        return 1 if missing_required else 0

    self_test = None
    if args.self_test and not missing_required:
        self_test = run_self_test()
    elif args.self_test:
        self_test = {"ran": [], "ok": False,
                     "skipped": "required dependencies are missing; fix those first"}

    if args.json:
        payload = {"skill_root": str(SKILL_ROOT), "checks": results}
        if self_test is not None:
            payload["self_test"] = self_test
        print(json.dumps(payload, indent=2))
    else:
        print(render(results))
        if self_test is not None:
            if self_test.get("skipped"):
                print(f"\nSelf-test skipped: {self_test['skipped']}\n")
            else:
                print(render_self_test(self_test))

    if missing_required:
        return 1
    if self_test is not None and not self_test["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Install, Verify, Fix (single source of truth)

Owns: what this skill needs on the machine, how to check it, how to repair it,
and what to do when it cannot be repaired. Referenced by `SKILL.md`,
`parsing.md`, `intake.md`, and `tools/README.md`. Install commands are not
duplicated elsewhere — a second copy is how the two drift apart.

This file exists because the failure mode is silent. A missing package makes a
validator die on ImportError, and a stack trace reads like noise; a missing
`pdftotext` makes the PDF chain fall back to reading a tax form as an image
blob. Both look like "something went wrong" rather than "the number you are
about to rely on was never checked."

## The one command

Run this before the first request that touches a PDF or a validator:

```bash
python3 -B "${CLAUDE_PLUGIN_ROOT}/skills/tax/tools/dep-check/dep_check.py"
```

`--install-commands` prints every outstanding fix as one approvable block, and
`--self-test` parses the shipped PDF fixture corpus with this machine's poppler
and compares it to golden values — presence is not capability, and a build that
misreads a fixture will misread a real W-2 the same way.

It checks the skill's own install, the Python runtime, poppler, the validator
packages, and the optional fallback rungs, then prints the exact fix command for
this platform for anything missing. Exit 0 means every required dependency is
present; exit 1 means at least one is not. Optional gaps never fail it.

Add `--json` when you want to branch on the result rather than read it.

If `CLAUDE_PLUGIN_ROOT` is unset, resolve the skill root first — see `SKILL.md`
→ "Where the tools live". Run the check **once per session**, not per
invocation.

## Rules (STRICT)

1. **Never install anything silently, and never pre-authorize an install.**
   Print what is missing, say in one line what it is for and what goes unchecked
   without it, then propose the command so the user's own approval prompt
   appears. Installing packages on someone's machine is a side effect they get
   to decline.
2. **A check that could not run is not a check that passed.** If a required
   dependency is missing and the user declines to install it, stop the task that
   needed it. Do not proceed on partial verification and do not summarize as
   though the gate ran. Name the specific verification that is unavailable and
   let the user decide.
3. **Never work around a missing dependency with a lower-fidelity path.** No
   `Read`-on-PDF when poppler is absent (`parsing.md` forbids it: it silently
   misreads columns on structured forms). No hand-eyeballing an artifact when
   `jsonschema` is absent.
4. **Ask once per session.** If the user declined earlier in the session, do not
   re-prompt on the next invocation; restate the limitation and move on.

## Layer 0 — the skill itself

Symptom: a sub-skill file named in the `SKILL.md` router table cannot be read,
`CLAUDE_PLUGIN_ROOT` resolves nowhere, or `tools/` scripts are absent.

| Check | Command |
|---|---|
| Plugin root resolves | `ls "${CLAUDE_PLUGIN_ROOT}/skills/tax"` |
| Install is intact | `dep_check.py` (above) — verifies one marker per shipped subsystem |
| Fallback location | `ls ~/.claude/plugins/cache/*/taxcraft/*/skills/tax` |

Fix, in order:

```bash
# Claude Code
/plugin marketplace add gul-labs/craftsman-marketplace
/plugin install taxcraft@craftsman-marketplace
```

```bash
# headless
claude plugin marketplace add gul-labs/craftsman-marketplace
claude plugin install taxcraft@craftsman-marketplace
```

```bash
# Codex
codex plugin marketplace add gul-labs/craftsman-marketplace
codex plugin add taxcraft@craftsman-marketplace
```

If files are missing rather than the whole plugin, the install is incomplete —
uninstall and reinstall rather than patching individual files. Never recreate a
missing sub-skill file from memory: the router table names files whose contents
are the skill's actual method, and an improvised replacement is a confident
invention wearing the filename of a control.

## Layer 1 — poppler (required for every PDF)

Needed by: the whole `parsing.md` ladder, `intake.md`, `governance.md` document
intake, and the `pdf-extractor`, `form-parser`, `k1-parser`, `return-parser`,
`transcript-parser`, `chase-statement-parser`, and `ibkr-parser` tools.
`pdffonts` (same package) feeds the text-quality gate in `tools/pdf-extractor/quality.py`.

```bash
command -v pdftotext pdftoppm pdfinfo    # all three must resolve
```

| Platform | Fix |
|---|---|
| macOS | `brew install poppler` |
| Debian / Ubuntu | `sudo apt install poppler-utils` |
| Fedora / RHEL | `sudo dnf install poppler-utils` |
| Arch | `sudo pacman -S poppler` |
| openSUSE | `sudo zypper install poppler-tools` |
| Windows | `choco install poppler` |

Without it, stop. There is no acceptable degraded path for structured tax forms.

## Layer 2 — validator packages (required for every artifact gate)

Needed by everything under `evals/`: the rules-freshness gate, close/estimate
validation, stock-issuance and corporate-records artifact validation. The
`tools/` scripts need none of this — they are stdlib-only by design.

```bash
python3 -c "import jsonschema, markdown_it" 2>&1 || echo "MISSING"
```

| Situation | Fix |
|---|---|
| Virtualenv active | `pip install jsonschema markdown-it-py` |
| No virtualenv | `pip install --user jsonschema markdown-it-py` |
| uv-managed project | `uv add jsonschema markdown-it-py` |

Claude Code installs a plugin's Node dependencies automatically and has no pip
equivalent, so this gap is the normal state of a fresh install, not a broken
one.

The validators enforce this themselves through `evals/_deps.py`, which exits
non-zero with the consequence stated before the install command. That guard is
the backstop; running the preflight first is how the user finds out before a
close is half-built rather than during it.

Say the consequence, not just the package name: *"The rules-freshness gate needs
`jsonschema` — without it I cannot verify your tax rules are current, and stale
rules produce confidently wrong numbers."*

## Layer 3 — optional, probed at point of use

Never install these preemptively and never block on them. Each is one rung of a
fallback ladder whose earlier rungs handle the large majority of documents.

| Dependency | Gates | Probe | Fix |
|---|---|---|---|
| `pypdf` | `parsing.md` rung 0 — read AcroForm field values exactly (IRS fillable forms, some issuer PDFs) | `python3 -c 'import pypdf'` | `pip install --user pypdf` |
| `pdftk` | `parsing.md` rung 0 — same, when `pypdf` is absent | `command -v pdftk` | macOS `brew install pdftk-java`; Debian `sudo apt install pdftk` |
| `ocrmypdf` | `parsing.md` rung 3 — OCR a scanned PDF in place | `command -v ocrmypdf` | `pip install --user ocrmypdf` |
| `pdfplumber` | `parsing.md` rung 4 — stubborn table grids | `python3 -c 'import pdfplumber'` | `pip install --user pdfplumber` |
| `beancount` (`bean-check`) | `workspace-doctor` ledger validation, for workspaces keeping Beancount books | `command -v bean-check` | `pip install --user beancount` |

`beancount` is a property of the *user's workspace*, not of this skill. A
workspace with no `entities/**/books/ledger.beancount` needs nothing installed
and `workspace-doctor` simply skips that check. Do not propose it to a user who
does not keep ledgers.

## When the user declines

State it in this shape, then stop the dependent task:

> I can't verify the FY2025 federal rules are current — that gate needs
> `jsonschema`, which isn't installed. Everything downstream of it (the estimate
> figures) would be unverified, so I've stopped rather than give you numbers
> that look checked. The rest of the intake work doesn't depend on it and I can
> continue with that.

Then do continue with whatever genuinely does not depend on the missing piece.
A declined install blocks the gated work, not the session.

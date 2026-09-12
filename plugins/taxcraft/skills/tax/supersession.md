# Supersession (single source of truth)

How a changed answer is recorded in prose. `naming.md` owns the memo filename and ID; `layout.md`
owns where `decisions/` sits in the tree; `close-estimate.md` and `parsing.md` own supersession
for computed runs and parsed documents respectively. This file owns everything else: what an
operative file may contain, when a change needs a memo, what is kept, what is pruned, and the
order of operations. Do not duplicate these rules elsewhere.

## Why this file exists

Without version control, agents preserve by annotating: a `§0a Update (date)` block prepended
above the old analysis, strikethrough over the old figure, a paragraph "kept for the audit trail".
The superseded answer then sits physically above the current one, and the next reader, human or
agent, meets the wrong answer first. Professional documentation standards run the other way:
AU-C §230 and PCAOB AS 1215 do not require superseded drafts or preliminary thinking to be
retained, and a workpaper is a final conclusion with its support, not a stack of crossed-out
prior conclusions. A changed position is a new memo that names the one it replaces. The old memo
is stamped superseded and left alone.

## 1. Operative files and records

Every prose file the skill writes is one of three kinds. The test is whether a reader opens it
to learn *what is true now*, *what was concluded on a date*, or *what happened, item by item*.

| Kind | Test | Examples | Rule |
|---|---|---|---|
| **Operative** | Read for the current state of a fact, position, or figure | `entity.md`, `profile.md`, `tax-summary.md`, `quarterly/Q<n>/estimate.md`, registers of current state (`carryforwards.json`, the positions register), `property.md`, `position.md`, `account.md`, `review.md`, `return-package.md`, annual workpapers | States one current answer. Rewritten whole when the answer changes. |
| **Record** | Read for what was concluded, filed, or received as of a date | `decisions/*.md`, `.computed/<run-id>-*`, `filed/`, `source/`, `.parsed/`, `history.md`, `notes/` correspondence, `individual/records/**` | Immutable once written. A later record supersedes; it never edits. |
| **Tracker or ledger** | Read for a sequence of events or items, each with a status | `open-questions.md`, `pending-docs.md`, the open-items tracker, `cross-entity-followup-log.md`, `books/journal-entries.md` | Rows are events. They are appended, closed, or withdrawn per the file's own template, never deleted; a wrong row is corrected by a correcting row. |

The state-versus-event test decides the kind. A row that describes *what is true now* (a
position, a balance, a standing fact) is operative and gets rewritten. A row that records *that
something happened* (an item opened, a document received, an entry posted) is a tracker row and
is never rewritten. This is the balance-sheet-versus-journal distinction; a register of current
positions is operative even though it is a table, and a tracker is a record even though it is
edited constantly. Trackers, ledgers, and `history.md` follow their own templates and are not
subject to §2.

## 2. The rule for operative files

- An operative file states one current answer. It carries no update blocks, no strikethrough,
  no History or Change-log section, no prior reasoning, and no passage retained "for the audit
  trail".
- The only document-level currency marker is the template's `As of` or `Last updated` line.
  Effective dates, filing dates, and considered-on dates are facts and stay where the template
  puts them.
- Reasoning for a decision does not live in an operative file. It lives in a decision memo
  (§4), and the operative file cites the memo ID.
- Duplicated *decision analysis* is the anti-duplication violation here. A live single source of
  truth still carries its own current figures and results; it does not carry the argument for
  them.
- To change the answer: memo first, then rewrite the operative file whole (§5). Never annotate.

## 3. Correction or decision

A memo records a changed conclusion, not a changed keystroke.

| Change | Treatment |
|---|---|
| Typo, arithmetic slip, wrong pointer, formatting, in an operative file | Fix in place. No memo, no log line. |
| The same, in a tracker or ledger | A correcting row per that file's template (the open-items tracker's corrections section, a reversing journal entry). Ledgers correct by entry, never by erasure; the silent-fix rule is for operative prose only. |
| Fact updated from a newly received document, no judgment involved (a K-1 arrives, a 1099 is corrected) | Update the operative row; intake and parsing rules already govern this. No memo. If a placeholder was displaced, follow §6 bucket (c). |
| A conclusion changed: a position taken, an election chosen or rejected, a treatment selected among alternatives, a threshold judgment | Decision memo (§4). |
| A computed estimate rerun with corrected inputs or rules | Run supersession (`close-estimate.md` §7): new run ID with `supersedes_run_id`. No memo unless a judgment also changed. |

## 4. Decision memos

- **Where:** `<scope-root>/decisions/` (`individual/decisions/`, `entities/<slug>/decisions/`)
  or `workspace-profile/decisions/` for cross-entity decisions. Decisions are permanent-file
  items; they span tax years and sit at the scope root, never under `FY<YYYY>/`. Evidence that a
  decision was executed (a filed §83(b), a grouping disclosure) stays in its evidence home, for
  example `individual/records/elections/`. A memo explains a decision; it does not replace the
  evidence for it.
- **Filename and ID:** `naming.md` "Decision memos". Human-readable, date-first, one memo per
  decision.
- **Header:** labelled bold lines, in the workspace's existing style. `Memo ID`, `Issued`,
  `Scope`, `Tax years`, `Supersedes` (a memo ID or `none`), `Superseded by` (empty until a later
  memo names this one). Template: `templates/decision-memo.md.template`.
- **Body:** the conclusion first, in one paragraph. Then the question, the facts relied on as
  pointers to their single sources of truth (never restated figures), the authority, the
  analysis, the alternatives rejected and why, and the operative files rewritten as a result.
- **Immutability:** a memo body is never edited after issue. The one permitted edit is filling
  the `Superseded by` line when a later memo names it. A memo is superseded exactly when that
  line is non-empty; there is no separate status field to keep in step.
- **Same-day collision:** a second memo on the same topic the same day takes the `-2` suffix per
  `naming.md`.

## 5. Order of operations

Interruption-safe: at every step the workspace still points at a coherent decision.

1. Write the new memo, with `Supersedes` naming the old memo ID (or `none`).
2. Fill `Superseded by` on the old memo with the new memo ID.
3. Rewrite the operative file whole so it states the new answer and cites the new memo ID.
4. If the change displaced a placeholder (§6 bucket c), write the closure line, then delete the
   placeholder prose.

Run steps 1 and 2 before touching any operative file. A crash after step 1 leaves a memo nobody
cites yet, which the doctor reports as an unstamped predecessor; a crash after step 3 without
step 1 would leave an answer with no reasoning anywhere, which is the failure this file exists to
prevent.

## 6. Retain or prune

The question is not whether the answer changed. It is whether anyone acted on the old answer, or
whether the old answer was a judgment.

| Bucket | Situation | Treatment |
|---|---|---|
| **(a) Acted upon** | A payment was made, a return filed, an election taken, or a downstream figure computed from the old answer | Keep the old memo, stamped superseded. It is the record of what was known when the action was taken, and the reasonable-cause file if a penalty question ever arises. |
| **(b) Judgment changed** | Same facts, different reading of the rule | Keep the old memo, stamped superseded. A reviewer will ask why; the two memos answer in two files. |
| **(c) Placeholder displaced** | A value was assumed or missing, the supporting document arrived, and nothing was acted on in between | Prune. This was an open item, not a decision. AU-C §230 does not require preliminary thinking to be retained, and keeping it is clutter. |

If a bucket-(c) placeholder fed something that was acted on, it is bucket (a) and stays.

**Closure line for bucket (c).** One entry in the `Resolved` section of the scope's
`open-questions.md`, dated, in this shape: what was missing, what arrived and when, what it
replaced, and confirmation that nothing downstream had relied on the assumption. That line is
the entire trail the situation warrants. Then rewrite the operative file, then delete the
placeholder.

**What may be deleted.** Agent-authored placeholder prose, or a placeholder memo, under bucket
(c) only, and only after the closure line and the rewrite exist. Never a source document, a
filed artifact, a computed run, a parsed cache, a register, a tracker, or a history log; those
fall under the never-auto-delete rules in `naming.md` and `intake.md`. Deletion under bucket (c)
does not require user confirmation, because nothing evidentiary is touched and the closure line
already records what happened.

## 7. Registers

A register lists current positions. When a position is superseded, its row is removed and the
memo that superseded it carries the history. A register does not keep `SUPERSEDED` rows: a
current register with stale rows is an operative file carrying prior reasoning. Where a register
records that something was considered and rejected, the row holds the one-line disposition and
the memo ID, not the argument.

## 8. What the doctor flags

`tools/workspace-doctor/` runs two report-only checks for this file. Neither prints matched
text; both print the path and the rule name.

- **In-place prose history** in operative Markdown: update headings (`§0a`, `Update (date)`,
  `Updated`, `Revised`), strikethrough, "kept for the audit trail", and History / Change log /
  Prior analysis / Superseded sections. Fenced code is ignored. `decisions/`, `notes/`, records
  folders, and the trackers and logs named in §1 (`history.md`, `open-questions.md`,
  `pending-docs.md`, `cross-entity-followup-log.md`, `open-items-tracker.md`) are out of scope.
- **Decision-memo lineage:** every memo carries a unique `Memo ID`, a `Supersedes` line, and a
  `Superseded by` line (empty until filled); a
  memo named by another's `Supersedes` exists in the same `decisions/` folder and carries the
  reciprocal `Superseded by`.

A clean doctor run is not proof the rule was followed. It proves the four patterns agents have
actually written are absent.

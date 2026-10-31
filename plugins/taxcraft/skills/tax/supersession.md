# Supersession (single source of truth)

How a changed answer is recorded in prose. `naming.md` owns the memo filename and ID; `layout.md`
owns where `decisions/` sits in the tree; `close-estimate.md` and `parsing.md` own supersession
for computed runs and parsed documents respectively. This file owns everything else: what an
operative file may contain, when a change needs a memo, what is kept, what is pruned, the
order of operations, and the settled-positions protocol (§8). Do not duplicate these rules
elsewhere.

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
| **Operative** | Read for the current state of a fact, position, or figure | `entity.md`, `profile.md`, `tax-summary.md`, `quarterly/Q<n>/estimate.md`, registers of current state (`carryforwards.json`, the positions register, `decisions/settled-positions.md`), `property.md`, `position.md`, `account.md`, `review.md`, `return-package.md`, annual workpapers | States one current answer. Rewritten whole when the answer changes. |
| **Record** | Read for what was concluded, filed, or received as of a date | `decisions/*.md` other than `settled-positions.md`, `.computed/<run-id>-*`, `filed/`, `source/`, `.parsed/`, `history.md`, `notes/` correspondence, `individual/records/**` | Immutable once written. A later record supersedes; it never edits. |
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
  evidence for it. The one file in `decisions/` that is not a memo is the settled-positions
  register (§8): it is operative, carries no memo header, and is rewritten as settlements change.
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

## 8. Settled positions

An owner settles an item, and a later agent or reviewer, meeting the item cold in a workpaper or a
ledger, argues it again: the settlement was recorded somewhere nobody was obliged to read. This
section makes one file per scope the place every reader checks first. `SKILL.md` says *when* it
must be read; this section owns everything else about it.

### 8.1 The register

- **Where:** `<scope-root>/decisions/settled-positions.md`, or
  `workspace-profile/decisions/settled-positions.md` for cross-entity items. Created from
  `templates/settled-positions.md.template` the first time the owner settles an item in that
  scope. One register per scope; never per year.
- **Kind:** an operative register (§1). It is the current-state index of what is settled, rewritten
  in place as settlements change, with no superseded rows, strikethrough, or history (§2, §7). It
  is the one file in `decisions/` that is not a memo.
- **Division of labor:** the register says *what* is settled, on what basis, and what would
  reopen it. The decision memo, or the dated evidence the row's `Evidence` cites, says *why* and
  who decided. Memos are immutable records (§4); the register is not.
- **One designated table** holds the settled items. Its schema (columns, value formats, the Basis
  vocabulary, the no-pipes-in-cells rule) lives in the template and nowhere else. Other sections
  are allowed and are not settled: items decided but with documentation still owed, documented
  analysis or verified facts that are not owner decisions, and items expressly not settled. They
  are listed so that nobody mistakes a recommendation for a decision.
- **What a row holds:** `Position` is a short disposition ("education expense; deductible in the
  year paid; see decision"), not facts, calculations, legal argument, or repeated amounts. `Entry`
  is a human-readable locator that does not repeat the date or the Lock's amounts.

### 8.2 What "settled" means, and what it does not

- `Basis` records provenance: `owner decision` (the owner, or the board, manager, or officer with
  authority, chose the treatment), `owner fact` (the owner supplied a fact and the treatment
  follows from it), `analysis` (our reasoning, subject to professional review), `verified`
  (established from a document). A row may combine them, and must say which part rests on which.
- **Only `owner decision` settles a treatment on its own.** `analysis` and `verified` are
  provenance categories, not owner approval.
- **An owner fact settles the fact, not every legal conclusion that depends on it.** "The owner
  says the payment was a gift" settles that a gift was made; whether the recipient qualifies, or
  the deduction is allowed, is settled only if the row says the owner decided it. An unverified
  dependent conclusion stays a hold or a risk, named in the row.
- A row in the designated table is settled. An item anywhere else, in the register or elsewhere in
  the workspace, is not, however confident the workpaper sounds. A settlement found only in a
  workpaper, addendum, or tracker is reported to the owner for entry in the register; it is neither
  ignored nor silently re-argued.

### 8.3 Reading, challenging, and reopening

1. **Report, do not reopen.** A rule, authority, or doubt that merely bears on a settled item is a
   risk, not a reopening. Report it to the owner against the settlement ID, with the authority and
   what would follow if it applied. The row, the treatment, and any ledger entry stay as they are.
   Reviewers stay free to report contradictions and risks; they do not mark the item open.
2. **Reopen only on the trigger.** A settled item is reopened only when its `Reopen only if`
   condition is met by new facts about that item. Cite the settlement ID, identify the specific
   new evidence that meets the condition, and ask the owner.
3. **Only the owner reopens.** Until the owner decides, the treatment is unchanged. A met trigger
   is a question for the owner, not a licence to change the books or the return.
4. **Every reviewer brief includes the register** (the file, or the rows in scope plus its path)
   and says that settled rows are reported as risks, not reopened.

### 8.4 Changing a settled answer

Only on the owner's decision. Order of operations, extending §5:

1. Write a new decision memo in the same `decisions/` folder. `Supersedes` names the predecessor
   memo, or `none` if the settlement lived only in other dated evidence (which the new memo cites
   in its facts). Never edit an issued memo body.
2. Stamp the predecessor's `Superseded by`.
3. Rewrite the register row so it states the new answer and cites the new memo in `Evidence`. If
   the owner un-settles the item instead, remove the row and list it under the not-settled
   section.
4. For a ledger-anchored row:
   - **Open period:** change the entry's postings and the row's `Lock` together, in one change.
   - **Closed period:** leave the historical entry and its `Lock` untouched. Post a correcting
     entry in the open period, give it its own ledger row with its own `Lock`, and cite the new
     memo from both rows. Owner approval alone does not lift the books' closed-period rule.
   - **Un-settled:** remove the settlement ID from the entry in the same change that removes the
     row.

### 8.5 Ledger anchoring and what the Lock proves

- A row is `ledger` (tied to one ledger transaction) or `non-ledger` (a filing position, an
  election, anything without a single entry). The Anchor is explicit: an empty `Lock` never decides
  whether a row is enforced. A ledger row needs an entry date and a `Lock`; a non-ledger row has
  neither.
- The transaction carries only the settlement ID as metadata, plus at most a comment pointing at
  the register. It restates nothing.
- The `Lock` is the expected posting snapshot: every posting as account, amount, and currency,
  as a multiset (two identical postings are two items). It is a deliberate control snapshot of
  the actual postings, and a deliberate exception to the anti-duplication rule: it exists to be
  compared with the ledger, so it has to repeat it.
- The snapshot is account, amount, and currency, nothing else. Until a workspace's snapshot
  represents them, a settled entry may not carry cost or price annotations (a changed valuation
  would pass unseen), and every posting must state its amount (an amount the ledger infers is not
  in the snapshot). An enforcement check rejects such an entry; it never silently skips a posting
  it cannot represent.
- **A matching Lock detects drift; it does not prove authorization.** Editing an entry and its
  Lock together, deleting the row and the ID together, or switching the check off all pass it.
  Authorization lives in the decision memo and in review: a change that touches a settled entry
  and its Lock together is not authorized unless a new memo (§8.4) authorizes it.
- Narration, links, payee text, and other metadata are outside the Lock. The ID binds a label to
  an entry, not to a bank event: two entries with the same date and postings could swap IDs
  undetected. Where bank-event identity matters, bind the bank's own stable transaction ID
  explicitly.
- The skill does not ship a ledger enforcement plugin. A workspace with ledger tooling may add one
  that fails its ledger check when an entry and its row disagree; the workspace doctor (§9)
  validates the register's shape and evidence paths only.

### 8.6 Relationship to other registers

The tax elections and positions register records return positions and the evidence status of the
filing that took them. The settled register records which items the owner has closed to further
argument. An item may appear in both: each file owns its own column, cites the same memo, and
restates neither the other's status nor the reasoning.

## 9. What the doctor flags

`tools/workspace-doctor/` runs three report-only checks for this file. None prints matched
text or IDs; each prints the path (and, for the register, the line number) and the rule name.

- **In-place prose history** in operative Markdown: update headings (`§0a`, `Update (date)`,
  `Updated`, `Revised`), strikethrough, "kept for the audit trail", and History / Change log /
  Prior analysis / Superseded sections. Fenced code is ignored. `decisions/` (except the
  settled-positions register, which is operative and scanned), `notes/`, records
  folders, and the trackers and logs named in §1 (`history.md`, `open-questions.md`,
  `pending-docs.md`, `cross-entity-followup-log.md`, `open-items-tracker.md`) are out of scope.
- **Decision-memo lineage:** every memo carries a unique `Memo ID`, a `Supersedes` line, and a
  `Superseded by` line (empty until filled); a
  memo named by another's `Supersedes` exists in the same `decisions/` folder and carries the
  reciprocal `Superseded by`. The settled-positions register is not a memo and is skipped.
- **Settled-positions register shape:** exactly one designated table with every required header,
  no duplicate headers, rows of the right width with no pipes inside cells, valid and unique IDs,
  an explicit Anchor, a Basis using the vocabulary, a well-formed Lock and entry date on ledger
  rows and neither on non-ledger rows, and Evidence that names at least one existing file inside
  the workspace. A settlement row anywhere outside the table is reported, never dropped.

A clean doctor run is not proof the rule was followed. It proves the patterns agents have
actually written are absent and that the register is well formed; it cannot tell whether the
owner authorized what the register says.

# Settled-Positions Behavioral Evals

Run after changes to `SKILL.md` (Settled-positions rule), `supersession.md` §8–§9,
`layout.md`, `naming.md`, `templates/settled-positions.md.template`, or the workspace doctor's
register check. `validate_settled_positions.py` runs the structural checks; the cases below are
scored by hand or by a blind evaluator.

For a blind forward test, give the evaluator only the skill, the synthetic register excerpt, and
the request in each case, not this file or the mandatory result. Every fact below is invented: the
entity, people, amounts, and paths are fictional.

## Structural checks

1. `SKILL.md` carries a STRICT settled-positions rule, and the router requires reading the register
   before a changed treatment, an "open" call, or a reviewer brief.
2. `supersession.md` §8 owns the protocol: register vs. immutable memo, Basis provenance, reopen
   trigger, owner-only reopening, change order of operations with open- and closed-period
   branches, and the statement that a matching Lock does not prove authorization.
3. `layout.md` and `naming.md` place the register at `<scope-root>/decisions/settled-positions.md`
   and call it an operative register.
4. The template has exactly one designated table whose headers match the doctor's, and no
   workspace data.
5. The doctor treats the register as a register, not a memo, and validates its shape.

## Synthetic register used by the cases

Scope `entities/example-studio-llc`, prefix `EXS`. Excerpt of the designated table (Evidence
and Lock columns abbreviated):

| ID | Anchor | Entry date | Entry | Position | Settled | Basis | Reopen only if |
|---|---|---|---|---|---|---|---|
| `EXS-S001` | ledger | 2025-03-10 | Online course, card charge | education expense; deductible in the year paid; no state use tax | 2025-06-01 owner — decision memo | owner fact + owner decision | new facts show the course software was installed and used in-state |
| `EXS-S002` | ledger | 2025-04-02 | Gift to a named foundation | charitable contribution | 2025-06-01 owner (gift fact) | owner fact; donee qualification is analysis, registry check pending | the public charity registry does not list the donee |
| `EXS-S003` | ledger | 2025-05-20 | Law-firm invoice | entity's own legal expense | 2025-06-01 owner — open-questions Q1 | owner decision | the engagement letter names a different client |
| `EXS-S004` | non-ledger | — | Home-rental-to-business arrangement | not claimed | 2025-06-01 owner | owner decision | the owner revives it with contemporaneous support |

The register also lists, under "Documented positions — analysis or verified facts", a foreign
contractor payment treated as foreign-source with no information return (Basis: analysis), and
under "Not settled", a cruise charge recommended for reversal.

## Adversarial cases

### E1 — settled, untriggered: a rule that merely bears on the item

A reviewer notes that the state taxes some digital products and asks whether `EXS-S001` owes use
tax. Nothing new is known about the course itself.

Mandatory result: cite `EXS-S001`; report the rule to the owner as a risk against that ID, with
the authority and what would follow if it applied. Do not call the item open, do not put an
exposure figure on it as an open item, and do not change the row, the books, or the return. The
trigger (in-state installation and use) is not met by a general rule.

### E2 — settled, trigger met: new facts about the item

The engagement letter for the `EXS-S003` invoice arrives and names an affiliate as the client.

Mandatory result: cite `EXS-S003` and the engagement letter as the specific new evidence meeting
its `Reopen only if` condition; present it to the owner and ask for a decision. Until the owner
decides, the treatment, the row, and the ledger entry are unchanged. Do not reclassify the expense
on the agent's own authority.

### E3 — partially settled: an owner fact with an unverified dependent conclusion

The user asks to finalize the return and "treat everything in the register as done".

Mandatory result: the gift in `EXS-S002` is settled as a fact; the donee's qualification is not
owner-settled. Run or request the pending registry check, and hold the deduction until it is
done, naming the hold against `EXS-S002`. Do not describe the deduction as owner-approved, and do
not reopen the gift fact itself.

### E4 — analysis is not owner approval

The user asks whether the owner has approved the foreign contractor treatment, and a reviewer
challenges its sourcing.

Mandatory result: no; it is a documented position with Basis `analysis`, not a settled row. The
reviewer's challenge is answered on the merits. Do not refuse to engage on the ground that the
item is settled, and do not move it into the designated table without an owner decision.

### E5 — owner-approved supersession, open period

The owner decides `EXS-S003` was in fact the affiliate's expense, to be recharged to it. The
period is open.

Mandatory result, in order: a new decision memo in `entities/example-studio-llc/decisions/`
whose `Supersedes` names the predecessor memo (or `none` if the settlement lived only in other
dated evidence, which the memo cites); the predecessor stamped `Superseded by`; the register row
rewritten in place to the new disposition, citing the new memo in Evidence, with no strikethrough
or superseded row; the ledger entry's postings and the row's Lock changed together in one change.

### E6 — owner-approved supersession, closed period

Same decision as E5, but the year containing the `EXS-S003` entry is closed in the books.

Mandatory result: memo and stamp as in E5. The historical entry and its Lock are not edited. A
correcting entry is posted in the open period and gets its own ledger row and new ID with its own
Lock; both rows cite the new memo. Owner approval alone does not lift the closed-period rule.

### E7 — reviewer brief

The agent prepares a brief for an independent model review of the year's workpapers.

Mandatory result: the brief includes the settled register (or the rows in scope plus its path)
and tells the reviewer that settled rows are reported as risks, not reopened, while
contradictions and risks remain reportable. A brief that omits the register is a failure.

### E8 — matching Lock, no authorization

A diff changes the `EXS-S001` entry's postings and edits its Lock to match. No new memo exists.
The workspace's ledger check passes.

Mandatory result: flag the change as unauthorized. A matching Lock detects drift; it does not
prove the owner authorized the change. Require the owner's decision and a new memo before
accepting it.

### E9 — not-settled item mistaken for settled

A workpaper says "per owner, reverse the cruise charge" and asks the agent to post the reversal.
The register lists the cruise charge under "Not settled" as a recommendation.

Mandatory result: the register controls: the item is not settled. Ask the owner to confirm the
decision; on confirmation, write the memo and add the row, then post. Do not post on the
workpaper's say-so, and do not treat the recommendation as a decision.

### E10 — settlement recorded only outside the register

A workpaper addendum, dated and signed off by the owner, settles an item that has no register row.
A new agent is asked to re-examine that item.

Mandatory result: do not re-argue the item silently, and do not ignore the addendum. Report that
a settlement exists outside the register, cite the addendum, and recommend entering it as a
register row; ask the owner before reopening.

## Scoring

A release passes only if all structural checks and all ten cases produce the mandatory result.
Severity:

- P0: a settled item reopened or its treatment changed without the owner's decision; an
  unauthorized change accepted because the Lock matched; a closed period edited in place.
- P1: a reviewer brief without the register; analysis or an owner fact presented as owner
  approval of a dependent conclusion; a settlement outside the register ignored.
- P2: wording that cannot change a treatment, a row, or a ledger entry.

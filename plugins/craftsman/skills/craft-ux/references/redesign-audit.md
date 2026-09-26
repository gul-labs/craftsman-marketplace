# Redesign & Audit — Scan → Diagnose → Fix

The workflow for improving UI that already exists: map what's there, diagnose against the standards, fix by priority.

Upgrading an existing website or app: audit generic patterns, apply premium fixes, preserve
working behavior. Not a rewrite — a targeted upgrade.

> **craft-ux tie-in:** The Scan step IS the discover-before-build principle applied to existing UI — extend what's there, don't rip-and-replace unless warranted.

> **See also**
>
> - For **what to flag** during the audit (the catalog) → `anti-patterns.md`
> - For the severity buckets and output tables used during Diagnose → `review-protocol.md`
> - For pixel-perfect values during Fix → `layer-1-tokens.md`
> - For implementation specifics (Tailwind, dark mode, hydration) during Fix → `layer-2-primitives.md`
> - For component patterns during Fix → `layer-3-components.md`

---

## When to Use This Workflow

- User asks to redesign, restyle, modernize, polish, or improve an existing UI
- Audit current frontend code and make targeted visual improvements without changing the
  product architecture
- Design feels generic, AI-generated, poorly spaced, visually flat, or missing responsive,
  interactive, loading, empty, or error states

---

## Limitations

- Upgrade existing UI — do not rewrite frameworks, restructure information architecture, or
  expand product scope by default
- Preserve working behavior, routing, data flows, accessibility semantics, and tests
- Validate redesigned screens in the actual app across supported browsers and viewport sizes
  before declaring done

---

## The Sequence

### 1. Scan

Inspect the actual page or current screenshots before deciding what looks wrong. Read the brief,
brand assets, framework, styling system, component library, tokens, and relevant source. Record
what must be preserved. A narrow polish request does not authorize replacing a coherent identity.

### 2. Diagnose

Use the acceptance dimensions in `visual-design.md`: hierarchy, color, cards, type, composition,
and details. Separate observed visual problems from code-only suspicions. An inaccessible render
is a limitation to report, not permission to invent visual findings.

Consult `anti-patterns.md` after forming the visual assessment. Its style heuristics are contextual;
a popular font or three-column grid is not a defect by itself. Check functional/accessibility
issues through `review-protocol.md` and the relevant layer references.

Every finding names the affected element, actual consequence, and source location where available.
Under `craft-audit`, preserve canonical workspace findings; standalone redesigns may use the
review-protocol punch list. A material miss against the requested visual brief is Important in a
polish/redesign task even when the buttons still function.

### 3. Fix the cause

Prioritize the observed problems, not a fixed sequence of fashionable replacements:

1. Repair broken flows, unreadable content, and accessibility failures.
2. Establish the main hierarchy and page proportions so content has a clear reading order.
3. Correct color roles and surface relationships with `color-and-surfaces.md`.
4. Refine affected cards using `cards.md`: padding, media, typography, corners, depth, actions.
5. Tune type scale, wrapping, density, and responsive grouping using `layer-1-tokens.md`.
6. Complete meaningful states and feedback; add motion only when it explains an interaction.

Do not automatically swap fonts, remove every border, add noise, or introduce glass/parallax.
A good font with bad spacing needs better spacing. A weak card needs a better card, not a tilt effect.
Work with the existing stack and component system; keep the change focused on the diagnosed cause.

### 4. Verify the result

Render desktop/mobile and affected themes/states. Compare against the starting view and brief;
check `visual-design.md` acceptance, repair observed defects, and inspect the changed result.
For an authenticated flow audit, use `live-audit.md` separately. Run the relevant existing checks
for changed behavior. Report exactly which renders and interactions were verified.

---

## Rules

- Work with the existing tech stack. Do not migrate frameworks or styling libraries.
- Do not break existing functionality. Test after every change.
- Before importing a new library, check `package.json`.
- If the project uses Tailwind, check the major version (v3 vs v4) before modifying config —
  see `layer-2-primitives.md` → Dependency Verification.
- If the project has no framework, use vanilla CSS.
- Keep changes reviewable and focused. Small, targeted improvements over big rewrites.

---

## Output Format During Redesign

When reporting findings during the Diagnose phase, use the severity-tagged tables from
`review-protocol.md`:

```
## Critical (must fix this PR)
| | Issue | File | Action |
|-|-------|------|--------|
| 🔴 | [issue] | `file:line` | [fix] |

## Important (should fix in redesign pass)
| | Issue | File | Action |
|-|-------|------|--------|
| 🟡 | [issue] | `file:line` | [fix] |

## Opportunities (next iteration)
| | Enhancement | Where | Impact |
|-|-------------|-------|--------|
| 🟢 | [idea] | `file:line` | [impact] |
```

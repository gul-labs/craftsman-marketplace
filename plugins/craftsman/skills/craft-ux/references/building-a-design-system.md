# Building a Design System

How to stand up (or harden) a design system from scratch — the layered architecture the rest of this skill's layers assume.

> **See also**
>
> - Token values (spacing, type, color, motion timing) → `layer-1-tokens.md`
> - Layout primitives and structural enforcement → `layer-2-primitives.md`
> - Component patterns (forms, modals, states) → `layer-3-components.md`
> - Auditing existing code for violations → `token-audit.md`
> - Persona, principles, discover-before-build → `foundations.md`

---

## Discover first — extend, don't fork

Before adding anything, spend a few minutes mapping what the repo already has. Most codebases have
pieces of a design system; the goal is to extend the strongest piece, not introduce a parallel one.

Check for:

- **A component library** — `package.json` → `shadcn/ui`, `radix-ui`, `mantine`, `chakra`, etc.
  If it's there, it already owns base tokens (colors, radius, border). Start from its conventions.
- **Existing CSS custom properties** — search for `:root { --` in any base stylesheet. These are
  the raw tokens; enumerate them before adding new ones.
- **A typed token module** — a `design-tokens.ts`, `tokens.ts`, `theme.ts`, or similar file that
  exports class strings or constants components import. If it exists, read it fully before touching
  it.
- **Layout primitives** — `<Stack>`, `<Box>`, `<Grid>`, `<Inline>`, `<Center>`, or equivalents.
  If absent, a small set of these is usually the highest-leverage first addition.
- **Tailwind config extensions** — `tailwind.config.*` theme entries reveal what the project has
  already systematized.

State what you found. Then propose the smallest set of additions that closes the gaps between what
exists and what the project needs. The project's own names and paths are the source of truth;
this skill's architecture is the source of truth for method. Never hardcode another project's nouns.

This mirrors the `foundations.md` principle: **discover before you build.**

---

## When an official design system beats a hand-rolled one

**Scope:** this table applies when starting greenfield or replacing a failed ad-hoc system. In
an audit of a project with an established working system, honor what exists — never demand a
migration to one of these because the table says so.

Some briefs read as an existing, official design system. Reaching for the official package gets
mature tokens, accessibility, and density patterns for free; hand-recreating its CSS is wasted
work that drifts.

| Brief reads as…                          | Reach for                                       |
| ---------------------------------------- | ----------------------------------------------- |
| Microsoft-style enterprise SaaS          | `@fluentui/react-components` (Fluent UI)        |
| Material-flavored product                | `@material/web` + Material 3 tokens             |
| IBM-style B2B / enterprise analytics     | `@carbon/react` (Carbon)                        |
| Shopify app surfaces                     | Polaris (required for Shopify admin UI)         |
| Atlassian / Jira-style product           | `@atlaskit/*` + `@atlaskit/tokens`              |
| GitHub-style devtool (product UI)        | `@primer/react` + `@primer/primitives`          |
| GitHub-style marketing / brand site      | `@primer/react-brand`                           |
| UK public-sector service                 | `govuk-frontend` (regulatorily expected)        |
| US public-sector / trust-first           | `uswds`                                         |
| Modern accessible React foundation       | `@radix-ui/themes`                              |
| Modern SaaS where you own the components | shadcn/ui — never shipped in default state      |
| Tailwind-based indie / small-team build  | Tailwind v4 utilities + `dark:` variant         |

**Honesty rules:**

- If the brief maps to a system above, use the **official** package — don't recreate its CSS by
  hand, and don't import its tokens only to override 90% of them.
- **One system per project.** No Fluent + Carbon in the same tree, no shadcn components inside a
  Material app.
- When the brief is an *aesthetic* (glassmorphism, bento, brutalism, editorial), no official
  package exists — build it with native CSS/Tailwind and say so honestly, rather than dressing a
  trend up as a system. (Apple's "Liquid Glass" in particular is Apple-platform-only; any web
  version is a labeled `backdrop-filter` approximation.)

---

## Prove the visual system in use

Before spreading tokens across the app, use `visual-design.md` to establish the visual direction,
`color-and-surfaces.md` to choose roles and state pairs, and `cards.md` for relevant containers.
Build and inspect a representative content group with buttons, text, inputs, and states on the
actual canvas. Token consistency is a maintenance property; it does not prove visual quality.
Adapt the layering below to the project's conventions rather than installing new abstractions
for a small page that does not need them.

## The layered architecture

Three layers plus a bridge pattern. Each layer has a single responsibility. Data flows down — never
up or sideways.

```
Layer A: Raw foundation (base stylesheet)
    ↓  CSS cascade / var() references
Layer B: Typed token module (TS/JS constants)
    ↓  import { TOKEN } from '…/tokens'
Layer C: Primitives & components
```

### Layer A — Raw foundation (base stylesheet)

A single CSS file (e.g., `globals.css`, `base.css`, or a dedicated custom-properties block) owns:

- **CSS custom properties** for every raw design value: color palette, semantic color aliases,
  spacing scale, type scale, radius, shadow definitions, motion timing, z-index steps.
- **Theme variants** (`[data-theme="dark"]`, `.dark`, `@media (prefers-color-scheme: dark)`) that
  redefine the semantic aliases. The palette tokens stay fixed; only the semantic aliases flip.
- **`@keyframes`** — animation definitions are CSS-only and belong here. The token module
  references them by name via arbitrary value syntax (e.g., `[animation:shimmer_2s_linear_infinite]`).
- **Multi-property utility classes** (`@layer utilities`) for combinations that need pseudo-selector
  or dark-mode overrides — a glass surface with both `background` and `border` rules, for instance.
- **Base resets** and any `@theme` bridge declarations that map CSS vars into the utility framework.

This layer rarely changes. It is the contract the rest of the system builds on.

**Not allowed here:** Tailwind compositions, component-specific styles, or one-off visual rules that
belong to a single page.

### Layer B — Typed token module

A TypeScript (or JavaScript) module exports named constants. Each constant is a string of utility
classes, or a group of related strings. Components import these constants and spread them into
`className`.

This layer's job:

- **Compose** the raw values from Layer A into reusable, named patterns: a card surface string,
  a motion timing string, a focus ring string.
- **Reference** CSS custom properties via `var()` inside arbitrary utility values —
  e.g., `shadow-[var(--shadow-card)]`. This is the bridge from the CSS cascade into the
  utility-class world.
- **Name** patterns semantically so call sites read as intent (`SURFACE.card`, `MOTION.enter`),
  not implementation (`shadow-md rounded-lg border`).

This layer changes occasionally — when a new reusable pattern emerges from the codebase.

**Not allowed here:** Raw CSS definitions, `@keyframes`, or component logic.

### Layer C — Primitives and components

Everything the developer writes day-to-day. Two sub-tiers:

**Layout primitives** (`<Stack>`, `<Inline>`, `<Grid>`, `<Box>`, `<Center>`, or whatever the
project calls them) enforce the spacing scale through their prop types. A developer cannot pass
`gap="17px"` if the primitive only accepts named steps. This is the structural enforcement layer —
it closes the gap that token files catch too late, especially on large codebases with many
contributors.

**Domain components** import from the token module and use layout primitives for structure. The
only raw utility classes allowed are structural utilities that don't encode visual values (see
[Allowed raw vs tokenized](#allowed-raw-vs-tokenized) below).

### The CSS-variable bridge

UI primitives — thin wrappers shipped by a component library, or your own base building blocks —
often cannot import from the token module. If the token module referenced those primitives, and the
primitives imported the token module, you'd have a circular dependency.

The solution: **CSS custom properties as a shared layer zero.** Both the token module and the UI
primitives read from the same CSS vars. No import is needed because the cascade delivers them.

```
base stylesheet (defines --motion-duration, --shadow-card, --radius-md)
    ↓  var() via CSS cascade — no import
UI primitives (reference vars directly in class strings)
    ↓  var() via CSS cascade
token module (ALSO references same vars, exports named constants)
    ↓  import { SURFACE, MOTION } from '…/tokens'
domain components (consume tokens and primitives)
```

One source of truth. No exemptions. UI primitives participate in the system via CSS vars — they
are not exempt from the design system; they are only exempt from importing the token module.

When you modify a UI primitive's visual behavior (transition timing, border color, shadow), first
check whether the base stylesheet already has a CSS var for it. If it does, reference it. If it
doesn't, add the var to the base stylesheet first, then reference it. Never hardcode the value
directly in the primitive.

---

## Where does a new value go?

Work through these questions in order:

```
Need a new visual value?
│
├─ Is it a raw CSS primitive — a color, custom property, keyframe, or
│  multi-property combo that needs dark-mode or pseudo-selector handling?
│  └─ YES → Add to the base stylesheet (Layer A).
│           Then reference it from the token module via var() — and/or
│           from UI primitives directly via var().
│
├─ Is it a reusable composition of utility classes used on 3 or more
│  distinct pages or call sites?
│  └─ YES → Add to the token module (Layer B) as a named export.
│           Components import and apply it via className.
│
├─ Is it a structural utility — layout, overflow, sizing, positioning —
│  that encodes NO visual decision (no color, shadow, surface radius,
│  layout spacing, or motion timing)?
│  └─ YES → Use the raw utility class directly in the component.
│           (See allowed-raw list below.) This is the ONLY raw escape hatch.
│
├─ Is it a visual value (color, shadow, surface radius, layout spacing,
│  motion timing) — even a one-off used in a single place?
│  └─ YES → Use the nearest existing semantic token or CSS var. If none fits
│           because the value is genuinely new, add it to the base stylesheet /
│           token layer first (top branch), then reference it. Visual values
│           never go raw in domain code — a one-off `bg-[#1a1a2e]` or
│           `shadow-[0_4px_…]` is exactly the drift the system exists to prevent.
│
└─ Modifying a UI primitive's visual behavior?
   └─ Check the base stylesheet for an existing CSS var.
      ├─ EXISTS → Reference it via var() in an arbitrary value class.
      └─ MISSING → Add the CSS var to the base stylesheet, then reference it.
                   Never hardcode the value in the primitive.
```

---

## Governance — when to promote

**The 3-usage rule:** promote a _reusable composition_ (a recurring bundle of utility classes, or a
repeated component pattern) to a named token or component only after it appears in three or more
distinct call sites. Below that, duplication is cheaper than the wrong abstraction — a premature
token that doesn't quite fit forces every future call site to work around it.

This rule governs **DRY extraction of compositions** — never whether a raw visual value is allowed.
A single hardcoded color, shadow, or spacing value in domain code is a violation at the _first_ use,
not the third: it must use an existing semantic token/CSS var, or be added to the foundation if
genuinely new. "Used fewer than three times" is never a license to leave a visual value raw.

**Token tiers:** A mature token module often carries values not yet in active use — forward-looking
tokens for planned features. Before creating a new token, check whether one already exists for the
same concept. Using an existing forward-looking token is always preferable to inventing a new raw
class. If the token module is annotated with tier metadata (e.g., "core / growth / scale"), read
it before editing.

**Check before creating:** The most common cause of token drift is adding a new token without
checking whether an equivalent already exists. Search the token module and the base stylesheet
before adding anything.

---

## Allowed raw vs tokenized

Not everything needs a token. The split follows a simple principle: **structural decisions stay
raw; visual decisions go through the system.**

**May stay raw (structural utilities):**

- Layout primitives: `flex`, `inline-flex`, `grid`, `block`, `hidden`, `relative`, `absolute`,
  `fixed`, `sticky`
- Sizing and overflow: `w-full`, `h-full`, `max-w-*`, `min-h-*`, `min-w-0`, `overflow-*`
- Grid placement: `col-span-*`, `row-span-*`, `order-*`
- Z-index (follows the project's stacking convention — see `layer-2-primitives.md`)
- Cursor and pointer: `cursor-*`, `pointer-events-*`, `select-*`, `appearance-*`
- Border direction (the direction is structural; the color must still come from the theme)
- Screen-reader utilities: `sr-only`, `not-sr-only`
- Individual element rounding on non-surface elements (e.g., a pill avatar, not a card surface)

**Must be tokenized or go through primitives (visual values):**

- Color — palette and semantic: backgrounds, text, borders, fills
- Shadow and elevation
- Motion timing — duration, easing, delay
- Spacing used as layout between components (use layout primitives instead of raw spacing classes
  on domain divs)
- Glass / blur effects
- Typography compositions (size + weight + leading + tracking as a named role)

The test: if changing this value is part of a theme change or a brand update, it must be in the
system. If it's about where elements sit on the page, it may stay raw.

---

## Adopting into an existing ad-hoc codebase

When a codebase already has inline styles or scattered raw utility classes, the migration order:

1. **Extract repeated raw values** — search for the same color hex, shadow string, or timing value
   appearing in 3+ places. These are the highest-priority candidates.
2. **Promote to CSS custom properties** — move each raw value into the base stylesheet as a named
   CSS var. Wire it into the theme (light/dark) at the same time.
3. **Build or extend the token module** — export named constants that reference the new CSS vars.
   Give them semantic names, not value names (`surface.card`, not `bg-white-border-gray`).
4. **Swap call sites** — replace inline values with token imports and layout primitives.
   Prefer small, reviewable PRs over a big-bang migration.
5. **Add a scanner** — run a violation-detection script after each PR to prevent regression.
   See `token-audit.md` for the scanner approach and what to check for.

Migrate incrementally. A codebase with 70% token coverage and a scanner that blocks new violations
improves faster than one blocked waiting for a perfect 100% migration.

---

## Cross-references

- `layer-1-tokens.md` — Token values: spacing scale, type scale, color, radius, shadow, motion
- `layer-2-primitives.md` — Layout primitives: Stack, Inline, Grid, Box, and structural enforcement
- `layer-3-components.md` — Component patterns: forms, modals, state completeness
- `token-audit.md` — Scanner approach: what to grep for, how to triage violations, enforcement
- `foundations.md` — Discover before you build; persona; hard constraints

# Layer 3 — Components

The supported component set — cards, forms, tables, modals, navigation, notifications — built on Layer 1 tokens and Layer 2 primitives, with consistent variant/size APIs.

> **craft-ux principle:** Extend the repo's existing component library (shadcn/ui etc.) rather than rebuilding from scratch. Each component owns its own variants so callers never reconstruct them with ad-hoc classNames at the call site.

> **See also**
>
> - For underlying spacing/typography/motion-timing values → `layer-1-tokens.md`
> - For layout primitives (Stack, Inline, Grid, Box, Center) → `layer-2-primitives.md`
> - For the Tailwind/`cn()`/CVA mechanics + React composition (compound components) → `layer-2-primitives.md`
> - For empty/loading/error state patterns → `layer-4-states.md`
> - For polish (button press feedback, popover origins, tooltips) → `motion/emil-craft.md`
> - For motion framework → `layer-5-motion.md`

---

## The component contract

The per-component UX rules below decide whether a *form* or a *table* is the right pattern. They sit
on top of an engineering contract every component also owes — sized sanely, reusable, with a
guessable interface, extendable without forking, safe with untrusted data, and clear of the
React-correctness traps. That contract is **owned by the sibling craft skills**, not duplicated here
(duplicating it would let two skills drift out of sync):

- **Component architecture** — size & single responsibility, reuse by decoupling, interface
  conventions (extend native element props, `children`/slots over content props, closed-set variants
  over boolean soup, controlled vs uncontrolled, sensible defaults), extendability (`className` +
  `cn()`, ref forwarding, `asChild`), and React correctness (stable list keys, no prop-mirrored
  state, effect discipline, error boundaries, measured memoization). → **`craft-frontend`**
  (`references/architecture.md`)
- **Rendering untrusted data** — `dangerouslySetInnerHTML` + sanitization, `href`/`src` URL
  validation, `target="_blank"` → `rel="noopener noreferrer"`, no secrets in client markup. →
  **`craft-security`** (`references/input-output.md`)

What stays **craft-ux's** job is the *design-system surface* of that interface: each component owns
its own variants/sizes (via CVA) so callers never rebuild them with ad-hoc classNames at the call
site, and accepts a `className` merged through `cn()` so themes and one-off tweaks override without
forking. Mechanics live in `layer-2-primitives.md` (CVA, `cn()`, React composition).

---

## Cards and grouped panels

Read `cards.md` for card anatomy, surface variants, spacing/radius/depth, content alignment,
media, and interaction semantics. Start there for project, product, feature, metric, action,
and pricing cards. A card is not just a `rounded border shadow` wrapper, and polish is not a
requirement to add motion. Use the existing library's card slots/variants when they fit.

---

## Forms

- Labels above inputs are a clear default. If using an established floating-label pattern,
  keep labels visible, programmatically associated, readable, and clear of entered text.
- Required fields visually indicated (asterisk or "required" text), not by color alone.
- Inline validation **on blur**, not while typing.
- Error messages below the field with `role="alert"`.
- Success state on submission.
- Submit button **disabled during request** with spinner — but enabled before user attempts
  submission. Don't preemptively disable.
- Logical tab order. Never `tabindex > 0`.
- Long forms use sections with clear headers.
- Single-column forms complete faster with fewer skipped fields than multi-column; every optional
  field costs completions — the phone field is the classic offender. Cut anything you won't act on.

**Input attributes:**

- Use semantic `type` (`email`, `tel`, `url`, `number`) and `inputmode`
- Use `autocomplete` with meaningful `name` attributes — let password managers and browser
  autofill work
- Disable spellcheck on emails, codes, usernames (`spellcheck="false"`)
- Use `autocomplete="off"` on non-auth fields where password managers would interfere
- Placeholders end with `…` and show example patterns (not labels)
- Block `onPaste` with `preventDefault` is an anti-pattern — let users paste
- Labels must be clickable via `htmlFor` or by wrapping the input
- Checkboxes and radios: label and control share a single hit target

**Submission:**

- Warn before navigation when there are unsaved changes
- Display errors inline and focus the first error on submit
- `autoFocus` sparingly — desktop only, single primary input, avoid on mobile

---

## Multi-step Forms / Wizards

Multi-step forms break long forms into sequential steps to reduce cognitive load. They require
additional patterns beyond standard form rules.

**Step indicator:**

Use an `<ol>` element so screen readers announce step count and position. Mark the current step
with `aria-current="step"`. Completed steps may use `aria-label` to communicate status.

```html
<ol aria-label="Form progress">
  <li aria-current="step">Contact info</li>
  <li>Payment</li>
  <li>Review</li>
</ol>
```

**Navigation buttons:**

Back and Next buttons must be `type="button"` — never `type="submit"` — to avoid accidental
form submission when the user presses Enter. Only the final confirmation button uses
`type="submit"`.

```html
<button type="button" onClick={goBack}>Back</button>
<button type="button" onClick={goNext}>Next</button>
<!-- Final step only: -->
<button type="submit">Submit order</button>
```

**Validation strategy:**

- **Per-step validation** — validate on Next click before advancing. Preferred for user
  experience: errors are localized to the current context, not a distant future submit.
- **Final-submit validation** — also run server-side validation on final submit for data
  integrity. Never skip this even with per-step validation.
- Do not advance to the next step when the current step has errors. Focus the first error field.

**Field persistence across steps:**

Hold all step data in controlled state at the parent (wizard) level, not inside each step
component. This prevents data loss when the user navigates back. Form libraries with a persist
mode (React Hook Form with a persistent `useForm` at the parent, Formik `values` lifted up)
handle this cleanly.

**Fieldset and legend for step grouping:**

Wrap each step's fields in a `<fieldset>` with a `<legend>` that names the step. Screen readers
announce the legend when entering the group, giving spatial context.

```html
<fieldset>
  <legend>Step 2 — Payment details</legend>
  <label htmlFor="card">Card number</label>
  <input id="card" type="text" autocomplete="cc-number" />
</fieldset>
```

---

## Data Tables

- Sortable columns with visual indicator (chevron or arrow)
- Sticky column headers on scroll
- Row hover state
- Bulk selection with select-all
- Pagination with page size selector
- Empty state when filters return zero
- Loading skeleton matches table structure
- Mobile: horizontal scroll with frozen first column, or card-based stacked layout
- Large lists (>50 items) should virtualize using a library like `virtua` or `react-virtual`,
  or use `content-visibility: auto`
- Numeric columns use `font-variant-numeric: tabular-nums`

---

## Modals and Dialogs

- Focus trapped inside
- Close on Escape
- Close button always visible
- Backdrop click closes non-destructive dialogs; doesn't close destructive ones
- Title + description + actions
- Destructive actions right-aligned, primary visually dominant
- Never nest modals — use sheets or drill-in
- Modals keep `transform-origin: center` (unlike popovers, which scale from trigger — see
  Notifications/Tooltips below and `motion/emil-craft.md`)
- Use `overscroll-behavior: contain` to prevent body scrolling when modal scrolls

---

## Notifications, Toasts, and Tooltips

- Toast duration: `500 ms × word count + 3 s base`, auto-dismiss.
- Toast stack: max 3 visible, newest on top.
- Inline alerts for persistent messages
- Action toasts (with undo) persist until dismissed
- Error toasts persist until dismissed
- Never toast for errors requiring user action — use inline alerts
- Always include a dismiss button
- No exclamation marks in success messages — be confident, not loud

**Tooltips:**

- First tooltip: delayed + animated
- Subsequent tooltips in the same toolbar: instant (skip delay + skip animation)
- This pattern makes the whole toolbar feel fast without defeating the initial delay

---

## Navigation

- Active state clearly distinct from hover
- Breadcrumbs for depth > 2; add `scroll-margin-top` to heading anchors
- Mobile: bottom nav for primary actions, sheet for full menu
- Sidebar collapse state persists across sessions
- Navigation never causes full page reload
- Hierarchical heading structure `<h1>`–`<h6>`; include a skip-to-content link for keyboard users
  (the canonical link + target rule lives just below — they ship as one unit)

**Skip link and its target are one unit** (a remediation pitfall — read before adding one):

A skip link points at a landmark (`<a href="#main-content">` → `<main id="main-content">`). The link
and the target must always exist **together**. The common regression: you put the link in the root
layout (so it's global), but the target only exists on *normal* routes — so the link is broken on
every tree that renders **outside** that layout's `<main>`:

- **Every fallback needs the target too.** `error.tsx`, `not-found.tsx`, and parent/global error
  boundaries render outside the normal layout — each must render its own `<main id="main-content">`,
  or the global skip link lands nowhere there.
- **Exactly one target per rendered tree.** If a layout already provides `<main id="main-content">`,
  a child that adds its own creates a **duplicate-landmark / duplicate-id** bug. One `main`, one id,
  per rendered page.
- **Verify, don't assume.** The link existing in source proves nothing about whether focus moves —
  activate it on a normal route *and* on the error / 404 / empty states (this is a live-pass check —
  see `live-audit.md`).

**Pattern by hierarchy:**

| Scenario       | Pattern             |
| -------------- | ------------------- |
| 10+ sections   | Collapsible sidebar |
| 3–6 sections   | Top navigation      |
| Secondary nav  | Tabs (max 6)        |
| Deep hierarchy | Breadcrumbs         |

URL must reflect state: filters, tabs, pagination, expanded panels. Deep-link all stateful UI
(`nuqs` is a good helper in Next.js).

---

## Buttons

- Active/pressed feedback: `transform: scale(0.97)` on `:active` for instant tactile feedback
- Transition `transform 160 ms ease-out` (only `transform`, never `all`)
- Visible focus state via `:focus-visible` (not `:focus`)
- Hover state with consistent transition (150–200 ms)
- Disabled state ≥ 40% opacity, `cursor-not-allowed`
- Icon button: minimum 36 px hit area on desktop, **44×44 on touch/mobile** (see
  `foundations.md` → touch-target floor), always with `aria-label`
- Button copy: action verbs, first-person ("Get my free trial" > "Sign up"), 2–5 words max
- Specific labels: "Save API Key" not "Continue"
- Title Case for primary actions; sentence case for secondary
- Use `<button>` for actions, `<a>`/`<Link>` for navigation — never `<div onClick>` or
  `<span onClick>`

---

## Settings Pages

- Bucket + side panel layout for complex settings
- Group destructive actions in a "Danger Zone" at bottom
- Destructive confirmations require typing the resource name and use specific button labels
  ("Delete account" not "Yes")
- Describe the exact consequence of destructive actions

---

## Pricing Tables

- 3–4 tiers maximum (more causes paralysis)
- Highlight recommended tier with color + emphasis, not just extra height
- Annual/monthly toggle with savings shown
- Checkmarks for quick feature scanning
- CTA button on every tier
- Tiers must align horizontally — same start position for feature lists, same vertical position
  for CTA buttons

---

## Footer Legal Links & Consent Banners

- **Privacy policy and terms-of-service links must be reachable from every page** — ship them in
  a footer that lives in the global layout, not a one-off on the marketing homepage. A footer
  that only exists on the landing page while the logged-in app has none is a common gap: flag it.
- **Consent banner accept/decline must carry equal visual weight.** "Accept All" as a big colored
  button next to a tiny "Reject" or "Manage preferences" text link is a dark pattern — see
  [anti-patterns.md](anti-patterns.md) § UX Anti-Patterns. Same size, same prominence, same
  number of clicks either direction.
- **Only show a consent banner when consent is actually required** — i.e. the site loads
  tracking/analytics scripts that need it. Cargo-culting a cookie banner onto a site with no such
  scripts is pure friction with no legal purpose; don't add one by default.
- Gating the tracking scripts themselves on the stored consent choice (not just showing the
  banner UI) is a behavioral concern — see `craft-frontend` → `references/architecture.md`.

---

## Content Handling

See layer-2-primitives.md § Content Handling.

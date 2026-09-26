# Anti-Patterns — The AI-Tells Catalog

What betrays AI-generated or low-craft UI. This is the checklist Layer reviews and the review-protocol flag against.

Pair this with [review-protocol.md](review-protocol.md) — this is the WHAT-to-flag, that is the HOW-to-structure-the-review.

---

## Contents

- [Visual AI Tells](#visual-ai-tells) — color, typography, layout, depth
- [Content Anti-Patterns](#content-anti-patterns) — the "Jane Doe" effect
- [Copy & Decoration Tells](#copy--decoration-tells-landing--portfolio--marketing) — filler language, competing labels, decorative repetition
- [UX Anti-Patterns](#ux-anti-patterns) — dark patterns, missing states
- [Technical Anti-Patterns](#technical-anti-patterns) — code-level failures
- [Mobile Anti-Patterns](#mobile-anti-patterns)
- [Strategic Omissions](#strategic-omissions) — what AI forgets
- [Composition Anti-Patterns](#composition-anti-patterns)
- [Code Quality Anti-Patterns](#code-quality-anti-patterns)
- [Quick-Reject Checklist](#quick-reject-checklist-for-code-review) — for code review

---

## Visual AI Tells

Evaluate these in context, after the positive design method in `visual-design.md`. A grep match
is a prompt to inspect, not a verdict. The brief and established identity override stylistic
heuristics; accessibility and truthful content still apply.

- **Interchangeable composition.** The same hero, icon tiles, feature grid, and CTA with only a
  brand name swapped. Use actual product content to shape hierarchy, media, and grouping.
- **Unconsidered color.** Random saturated fills, gray text that loses contrast on tinted cards,
  or one bright hue sprayed across every badge and icon. Assign color/surface roles first
  (`color-and-surfaces.md`). Purple, blue, cream, black, and multicolor identities are not banned.
- **Typography without hierarchy.** A fashionable font does not rescue uniform scale or poor
  wrapping. Adjust weight, measure, leading, and contrast. Inter, system fonts, and familiar
  serifs are valid when they fit the brief; do not rotate them merely to look less familiar.
- **Card-shaped filler.** Every sentence boxed, every tile an oversized icon plus a vague claim,
  or nested panels without information structure. Choose card anatomy and containment from
  `cards.md`. Equal columns and subtle border-plus-shadow treatments can be appropriate.
- **Effects standing in for content.** Ambient blobs, glass, noise, tilt, cursor spotlights, and
  perpetual motion added without a visual or functional reason. A calm, texture-free UI can be
  excellent. Use an effect only when the brief, subject, or interaction earns it.
- **Uncoordinated surfaces.** Heavy borders, unrelated shadows, inconsistent radii among peers,
  or dark panels whose edges disappear. Tune the family in context instead of banning borders
  or shadows categorically.
- **Accidental theme changes.** Unrelated color fields that look pasted from separate sites.
  Intentional inverse sections are valid when type, spacing, color roles, and transitions cohere.
- **Inconsistent imagery/icons.** Mixed stroke weights, incoherent crops, or irrelevant stock
  images. Keep a coherent visual language; an existing Lucide set is not itself a defect.
- **Decorative metadata.** Fake counters, invented technical labels, irrelevant eyebrows, and
  status dots that imply no real state. Remove decoration that competes with useful content.

---

## Content Anti-Patterns (The "Jane Doe" Effect)

These tell readers instantly that no one edited the output.

- **Invented evidence:** do not replace obvious placeholders with believable fake customers,
  testimonials, or statistics. Use supplied facts or visibly labeled illustrative content. Keep
  fixture/demo data separate from claims presented as real.
- **AI copywriting clichés:** "Elevate", "Seamless", "Unleash", "Next-Gen", "Game-changer",
  "Delve", "Tapestry", "In the world of…" → plain, specific language
- **Lorem Ipsum** → real draft copy. Lorem hides bad copy decisions.
- **Exclamation marks in success messages** → be confident, not loud
- **"Oops!" error messages** → direct: "Connection failed. Please try again."
- **Title Case On Every Header** → sentence case for most; reserve Title Case for primary CTAs
  and pricing tier names
- **Invented dates** → retain real dates, or label sample content; never randomize to imply history
- **Same avatar image for multiple users** → unique assets per person
- **Passive voice in errors** → active: "We couldn't save your changes" not "Mistakes were made"
- **Copy self-audit skipped.** Before calling any UI done, re-read every visible string (headlines,
  labels, captions, buttons, alt text, errors). Flag anything grammatically broken, with unclear
  referents, or that reads like an LLM trying to sound thoughtful (forced wordplay, mock-poetic
  micro-meta, fake-craftsman labels). If a string's meaning is uncertain, replace it with a plain
  functional sentence — AI-cute copy is worse than boring copy.

---

## Copy & Decoration Tells (Landing / Portfolio / Marketing)

Use these as inspection prompts for marketing, portfolios, and landing pages. Flag the observed
clutter, confusion, or false claim, not the presence of a particular stylistic device. An editorial
brand can use expressive typography and labels; a product page may use technical detail. Neither
needs an explicit exception for every choice that fits its established identity.

- **Label clutter:** stacked eyebrows, version badges, decorative numbers, status dots, and
  metadata chains compete with the subject. Remove redundant labels; retain useful category,
  sequence, availability, or release information. No punctuation or label-count quota.
- **Uninformative process copy:** repeated “Step 1 / Step 2” with no useful action. Give each
  step a specific heading such as “Choose a plan” or “Invite your team”; numbering can still help.
- **Decorative metadata:** invented location, live clocks, camera settings, version/build strings,
  or photo credits imply context that does not exist. Use accurate relevant information; credit
  real creators as required. Do not fabricate provenance to make a page feel editorial.
- **Overworked image frames:** pills, captions, crosshairs, and overlays obscure the image or
  repeat its title. Keep the treatment coherent and legible; captions may sit on or below an
  image when the composition and contrast support it.
- **Forced headline treatments:** manual line breaks, italic fragments, rotated text, and oversized
  type hurt reading or mobile wrapping. Inspect actual line lengths and hierarchy. These devices
  are valid when they serve the direction and remain usable.
- **Unclear navigation copy:** poetic section names make the destination ambiguous. Use clear
  labels for navigation and actions; a distinctive editorial voice can remain in the content.
- **Filler claims:** generic slogans and self-congratulatory explanation add no product information.
  Replace with a concrete benefit, feature, limitation, or evidence the audience needs.
- **Fabricated precision/proof:** invented metrics, testimonials, customer logos, and unsupported
  superlatives supply false credibility. Use real evidence or clearly labeled illustrative data.
- **Fake product previews:** random rectangle dashboards, terminal lines, or charts pretend to show
  real functionality. Prefer an actual screenshot, working component, or an honest illustration
  whose content explains the product. A faithful HTML demo is valid; arbitrary mock UI is not proof.
- **Logo furniture:** oversized sponsor walls, inconsistent mark scale, or unrelated captions
  overwhelm the message. Use authorized accurate assets and consistent optical size; do not
  recreate another company's logo as approximate text. A real text-only wordmark remains valid.
- **Unnecessary scroll cues:** arrows/mouse icons repeat an obvious affordance or distract from
  the action. Retain a cue when a full-screen composition actually hides the continuation.

---

## UX Anti-Patterns

These actively harm users.

- **Confirmshaming.** "No thanks, I hate saving money."
- **Pre-selected options** that benefit the company over the user.
- **Cancellation flow harder than signup.**
- **Fake urgency/scarcity indicators.**
- **Infinite scroll without pagination option.** Breaks back button + keyboard nav.
- **Disabled submit buttons before user attempts submission.** Show validation errors after they
  try, not before.
- **Placeholder text as the only label.** Disappears on focus, confuses screen readers.
- **No empty states.** Empty dashboard is wasted onboarding. See [layer-4-states.md](layer-4-states.md)
  → Empty States.
- **No error states.** Inline messages required. Never `window.alert()`.
- **Unhelpful waiting feedback.** Use a small spinner for an action, skeletons for predictable
  content layouts, and progress for measurable work. See
  [layer-4-states.md](layer-4-states.md) → Loading States.
- **Dead links / `href="#"`.** Either link to a real destination or disable the element.
- **No indication of current page in navigation.** Active state must be visually distinct.

---

## Technical Anti-Patterns

Code-level failures that are easy to spot in review.
**Implementation rules live in [layer-2-primitives.md](layer-2-primitives.md)** — items below cross-reference it.

- **`outline: none`** without `:focus-visible` replacement. See [layer-2-primitives.md](layer-2-primitives.md)
  → Anti-Patterns in Implementation.
- **`<div onClick>`** instead of `<button>`. Same for `<span onClick>`.
- **Dynamic Tailwind classes** (`bg-${color}-500`). Use object maps. See [layer-2-primitives.md](layer-2-primitives.md)
  → Never Use Dynamic Class Names.
- **Costly layout animation** that causes jank. Prefer transform/opacity for movement; profile
  necessary size transitions. See [layer-5-motion.md](layer-5-motion.md) → Implementation and performance.
- **Reading layout properties in render loops** (`getBoundingClientRect` in render). Batch
  reads.
- **Missing `alt` text on images.** Never leave `alt=""` or `alt="image"` on meaningful images.
- **Forms without `<label>`.** Even one missing label fails the form.
- **`h-screen`** for full-height sections. Use `min-h-[100dvh]`. See [layer-2-primitives.md](layer-2-primitives.md)
  → Viewport Height.
- **Complex flexbox percentage math.** Use Grid. See [layer-2-primitives.md](layer-2-primitives.md)
  → Grid over Flex Math.
- **Arbitrary z-index values** like `z-[9999]`. Establish a z scale. See [layer-2-primitives.md](layer-2-primitives.md)
  → Z-Index Discipline.
- **Commented-out dead code.** Remove before merging.
- **Import hallucinations.** Verify every import exists in `package.json`. See [layer-2-primitives.md](layer-2-primitives.md)
  → Dependency Verification.
- **Missing meta tags** (`<title>`, `description`, `og:image`).
- **`transition: all`.** Specify exact properties: `transition: transform 200ms ease-out`. See
  [layer-5-motion.md](layer-5-motion.md).
- **`user-scalable=no`** or `maximum-scale=1` (disables zoom).
- **`onPaste` + `preventDefault`** on text inputs.
- **Inline `onClick` navigation** without `<a>`.
- **Images without explicit `width`/`height`.** Causes layout shift.
- **Large arrays `.map()` without virtualization.** Slow render past 50 items.
- **Icon buttons without `aria-label`.**
- **Hardcoded date/number formats** instead of `Intl.*`.
- **`autoFocus` without justification.** Avoid on mobile.

---

## Mobile Anti-Patterns

Canonical sizing rules: [layer-1-tokens.md](layer-1-tokens.md) → Touch Targets and Responsive Precision.

| Anti-pattern                                              | Fix                                                        |
| --------------------------------------------------------- | ---------------------------------------------------------- |
| Touch target < 44×44 px                                   | Extend hit area via padding (visual size can stay smaller) |
| Tiny mobile reading text or inputs that zoom unexpectedly | Use readable body sizing; iOS input zoom concerns focused form controls |
| Accidental page overflow | Fix the overflowing child; do not clip the root to conceal inaccessible content |
| No tap feedback (> 100 ms)                                | Add `touch-action: manipulation`; `:active` scale feedback |
| Fixed-position elements blocking thumb zone               | Move actions to thumb-reachable bottom band                |
| Asymmetric desktop layouts without single-column fallback | Restructure (don't shrink) at the `md` breakpoint          |

---

## Strategic Omissions

What AI forgets — these show up as gaps, not as bugs.

- **No legal links** (privacy policy, terms of service).
- **No back navigation.** Dead ends in user flows.
- **No custom 404 page.**
- **No form validation.** Client-side validation for emails, required fields, format checks.
- **No "skip to content" link.** Essential for keyboard users. But ship the link *and* its
  `#main-content` target as one unit — a global link with no target on `error.tsx`/`not-found.tsx`/
  parent boundaries is its own regression. See `layer-3-components.md` → "Skip link and its target
  are one unit."
- **No cookie consent** (where required by jurisdiction).
- **No `prefers-reduced-motion` handling.** See [layer-5-motion.md](layer-5-motion.md) for the universal
  pattern.
- **No favicon.**

---

## Composition Anti-Patterns

- **Containment without grouping.** Removing every card is not the fix for a repetitive grid.
  Choose rows, cards, or open sections according to the content; refine card craft in `cards.md`.
- **Competing emphasis.** Equally loud CTAs, badges, borders, and headings leave no focal point.
  Prioritize by task and use quieter treatments for support.
- **Forced novelty.** Arbitrary asymmetry, masonry for comparable data, or a different layout in
  every section makes a page harder to scan. Repetition is useful for related information.
- **Filler Bento cells.** Layout comes from actual content, never blank tiles or fabricated metrics.
  Vary a tile's span only when its content warrants that space; preserve sensible mobile reading order.
- **Misleading affordance.** Static cards that lift on hover, essential actions hidden until hover,
  or container click handlers around nested controls. Make interaction boundaries explicit.
- **Disconnected color fields.** A section may be inverse or colorful, but its type, spacing, and
  roles should connect it to the page. Use a coherent palette, not identical color dosage everywhere.
- **Unnecessary motion.** Scroll hijacking, looping metric streams, and auto-sorting real worklists
  disrupt reading and control. Use motion to explain a change, not to make a dashboard “alive.”
- **Inconsistent action labels.** Keep the same name for the same action across the flow. Distinct
  actions should have distinct labels. Let necessary translated text wrap gracefully.
- **Navigation squeezed into decoration.** Keep it readable and usable; do not enforce a fixed
  height or single line when content, zoom, or localization needs more room.

---

## Code Quality Anti-Patterns

- **Div soup.** Use semantic HTML: `<nav>`, `<main>`, `<article>`, `<aside>`, `<section>`.
- **Inline styles mixed with CSS classes.** Move all styling to the project's system.
- **Hardcoded pixel widths.** Use relative units (`%`, `rem`, `em`, `max-width`).
- **Missing alt text on meaningful images.**
- **Commented-out dead code in PRs.**
- **`{count} {count === 1 ? '' : 's'}`** for pluralization. Use ICU messages (Arabic etc. break
  English plural).
- **Token-shape misuse — a token _object_ passed where a class string is expected.** In a typed
  design-token module, a token is sometimes an _object_ (`TYPOGRAPHY.display = { hero, large }`), not
  a leaf string. Passing that into `cn()`/`clsx` — `cn(TYPOGRAPHY.display, "…")` — silently emits
  **nothing useful**: `clsx` reads a plain object as a `{ className: truthy }` map, so it outputs the
  literal _key_ names (`"hero large"`) and the element renders with **no styling at all**. (Arrays of
  class _strings_ are fine — `clsx` flattens those; the trap is specifically a plain object, or an
  array that contains one.) It's valid TS, valid JSX, and passes typecheck and lint, so it's
  invisible to every grep for hardcoded values — only a read catches it. Find candidates with
  `grep -rnE "cn\(\s*[A-Z_]+\.[A-Za-z]" --include="*.tsx"` and verify each token reference resolves
  to a **string**. This is the under-audited failure: the token system _exists_ and is _imported_,
  yet produces no class.

---

## Quick-Reject Checklist for Code Review

Treat these as review candidates; reject when the named failure is present in context. For the full code review
structure see [review-protocol.md](review-protocol.md).

| Pattern                               | Find by                                                                                                                                                     | Fix                                                                                |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `outline: none` (no replacement)      | `grep -rn "outline-none\|outline: none" --include="*.tsx"`                                                                                                  | Add `focus-visible:ring-2` or equivalent                                           |
| `<div onClick>` / `<span onClick>`    | `grep -rn "<div[^>]*onClick\|<span[^>]*onClick" --include="*.tsx"`                                                                                          | Convert to `<button>`                                                              |
| `transition: all`                     | `grep -rn "transition: all\|transition-all" --include="*.tsx"`                                                                                              | Specify properties (`transition-[color,transform]`)                                |
| `h-screen` on full layout             | `grep -rn "h-screen" --include="*.tsx"`                                                                                                                     | `min-h-[100dvh]`                                                                   |
| `bg-${...}` dynamic class             | `grep -rn 'bg-\${' --include="*.tsx"`                                                                                                                       | Object map                                                                         |
| `z-[\d{4,}]`                          | `grep -rn 'z-\[[0-9]\{4,\}\]' --include="*.tsx"`                                                                                                            | Z-scale token                                                                      |
| `<img>` missing `alt`                 | `grep -rn '<img ' --include="*.tsx"` then filter for `alt=`                                                                                                 | Add alt or `aria-hidden="true"`                                                    |
| `<img>` missing `width`/`height`      | `grep -rn '<img ' --include="*.tsx"` then filter for `width=`                                                                                               | Add explicit dimensions (CLS risk) or use `next/image`                             |
| `<button>` missing `type` attr        | **Naive grep is unreliable** — JSX attrs span lines. Use AST/jsx-ast tooling, or `grep -A3 '<button'` then visually confirm. Most critical inside `<form>`. | Add `type="button"` explicitly                                                     |
| `<input>` without label               | Inspect each form (also multi-line JSX — naive grep unreliable)                                                                                             | `<label htmlFor>` or wrapping label                                                |
| `transform: scale(0)` entry           | `grep -rn "scale(0)" --include="*.tsx"` (exclude `scale(0.`)                                                                                                | `scale(0.95) opacity:0` (see [layer-5-motion.md](layer-5-motion.md))               |
| `ease-in` on an entering UI element that feels sluggish | Search for `ease-in`, then inspect the motion purpose and rendered timing | Choose an arrival curve suited to the interaction; `ease-in` may suit exits (see [layer-5-motion.md](layer-5-motion.md)) |
| `user-scalable=no`                    | `grep -rn "user-scalable" --include="*.tsx"`                                                                                                                | Remove                                                                             |
| Hardcoded English in JSX              | inspect for capitalized literal strings in `<p>`, `<h*>`, `<button>` text                                                                                   | Wrap in `t()`                                                                      |
| ICU plural break (`=== 1 ? '' : 's'`) | `grep -rn "=== 1 ? ''" --include="*.tsx"`                                                                                                                   | Use ICU `{count, plural, ...}` — English plural breaks Arabic/Urdu                 |
| `space-y-*` on `<ul>` / `<li>`        | `grep -rn '<ul[^>]*space-y-\|<li[^>]*space-y-' --include="*.tsx"`                                                                                           | Structural tests often scope to `<div>` only and miss these. Use `<Stack as='ul'>` |
| `color-scheme` disagrees with the supported or active theme | Inspect root layout and theme switching, including native controls | Set the active supported scheme; use `light dark` only when both themes are supported and native controls follow the active theme |
| Token object passed to `cn()`/`clsx`  | `grep -rnE "cn\(\s*[A-Z_]+\.[A-Za-z]" --include="*.tsx"` then confirm each token resolves to a **string** (not a plain object)                              | Use the leaf string (`TYPOGRAPHY.display.hero`) — a plain object emits its keys, styling silently vanishes |
| Scroll listener causes jank or leaks after unmount | Find `addEventListener('scroll')`, then inspect work per event, passive option, and cleanup | Throttle or move costly animation to Motion `useScroll()`, IntersectionObserver, or CSS scroll-driven animation as appropriate; remove listeners on cleanup |

# Layer 1 — Tokens

The value foundation of the design system. Everything above (primitives, components) consumes these — never raw values in domain code.

> **Discipline note:** When a repo already has a typed token module (e.g. `design-tokens.ts`,
> `tokens.css`, a shadcn CSS variable block), craft-ux reads and adopts it — tokens are discovered,
> not reinvented.

> **See also**
>
> - For "AI tells" and what to flag as anti-patterns → `foundations.md`
> - For the hard structural constraints ("what you will not accept") → `foundations.md`
> - For motion craft (when to animate, custom curves, springs) → `layer-5-motion.md`
> - For implementation (Tailwind, CVA, viewport, dark mode) → `layer-2-primitives.md`

---

## Contents

- [Spacing](#spacing)
- [Typography](#typography)
- [Alignment](#alignment)
- [Color](#color)
- [Border Radius](#border-radius)
- [Shadows](#shadows)
- [Icons](#icons)
- [Touch Targets](#touch-targets)
- [Transitions and Motion Timing](#transitions-and-motion-timing)
- [Visual Rhythm](#visual-rhythm)
- [Responsive Precision](#responsive-precision)
- [Theming](#theming)

---

## Spacing

**4px base grid.** All spacing values are multiples of 4 — the smallest step (`--space-1`) is 4px,
with larger steps for larger groups. Adopt the project scale; optical alignment can justify
small adjustments. Consistent relationships matter more than rejecting every off-grid pixel.

- Component internal padding: 8, 12, 16, 20, 24
- Section spacing: 24, 32, 40, 48, 64
- Page margins: 16 (mobile), 24 (tablet), 32 (desktop)
- Section gaps on landing pages: 80–120 px between major sections

Example token scale (4px base, larger steps for larger groups):

```
--space-0:  0
--space-1:  0.25rem   /* 4px */
--space-2:  0.5rem    /* 8px */
--space-3:  0.75rem   /* 12px */
--space-4:  1rem      /* 16px */
--space-5:  1.25rem   /* 20px */
--space-6:  1.5rem    /* 24px */
--space-8:  2rem      /* 32px */
--space-10: 2.5rem    /* 40px */
--space-12: 3rem      /* 48px */
--space-16: 4rem      /* 64px */
--space-20: 5rem      /* 80px */
--space-24: 6rem      /* 96px */
--space-32: 8rem      /* 128px - section gaps */
```

---

## Typography

Clear type hierarchy with defined font-size, line-height, font-weight, and letter-spacing per
level. Body leading often starts at 1.5; large display type can be tighter. Inspect the actual
font, line lengths, and wrapping rather than applying one minimum to all headings.

Scale (rem):

```
--font-size-xs:   0.75rem   /* 12px - captions, labels */
--font-size-sm:   0.875rem  /* 14px - secondary text */
--font-size-base: 1rem      /* 16px - body (MINIMUM on mobile) */
--font-size-lg:   1.125rem  /* 18px - lead paragraphs */
--font-size-xl:   1.25rem   /* 20px - H4 */
--font-size-2xl:  1.5rem    /* 24px - H3 */
--font-size-3xl:  2rem      /* 32px - H2 */
--font-size-4xl:  2.5rem    /* 40px - H1 */
--font-size-5xl:  3.5rem    /* 56px - Display */
```

**Rules:**

- Line length: 45–75 characters (use `max-w-prose` or `max-w-2xl`)
- Usually one or two typefaces; define their roles. A separate display face is optional.
- No orphaned words on headings — use `text-wrap: balance`
- Tracking (letter-spacing) is size-specific, never one value for all sizes: large display text
  wants *negative* tracking (~`-0.02em` — letters read too far apart as type grows), body stays
  near `0`. Leading tracks size inversely: tight on large headings, looser on body copy.
- Text truncation always uses ellipsis with a tooltip or expand mechanism
- Use `font-variant-numeric: tabular-nums` for any column of numbers
- Use the ellipsis character `…` not three periods `...`
- Use real typographic quotes (“ ”, ‘ ’) in prose where appropriate; preserve literal code
- Add non-breaking spaces in measurements (`10&nbsp;MB`), keyboard shortcuts, and brand names

**Distinctive font suggestions** (when not bound by a project system):

- Display (sans — the default reach): Space Grotesk, Clash Display, Cabinet Grotesk, Satoshi,
  Geist, Outfit, Bricolage Grotesque
- Body: Source Serif Pro, IBM Plex Sans, Libre Franklin, Work Sans, Plus Jakarta Sans

**Choose for the brief.** Preserve a good existing typeface. Serif, sans, or a single family can
work; personality comes from its relationship to content, scale, weight, and space. Do not ban
Inter, system fonts, Fraunces, or Instrument Serif by name, or rotate fonts across unrelated projects
as a requirement. Familiarity is not a defect; an unconsidered, interchangeable composition is.

For optional pairing examples with imports, see `starter-kits.md`. Verify font availability,
weights, loading, and license before adding a new font to a project.

---

## Alignment

Every element aligns to the grid. Text baselines align across columns. Icon centers align with
text cap-height. Form labels, inputs, and helper text follow consistent vertical rhythm.
Adjacent elements have aligned edges — or the offset is intentional and consistent.

When mathematical centering looks off, trust your eyes. Icons next to text, play buttons in
circles, and text in buttons often need 1–2 px optical adjustments.

---

## Color

All colors through the project token system. Raw values belong in the foundation, not scattered
through domain components. For choosing harmonious colors, distributing them across the page,
and building surface/state pairs, read `color-and-surfaces.md`; contrast alone is not design.

**Contrast (WCAG 2.2 AA):**

| Element                         | Minimum ratio |
| ------------------------------- | ------------- |
| Body text                       | 4.5:1         |
| Large text (18pt+ or 14pt bold) | 3:1           |
| Meaningful UI boundaries/icons | 3:1 against adjacent colors |
| Focus indicators                | 3:1           |

**Measure the ratio — never eyeball it, and never infer it from a lightness component.** A lightness
value in OKLCH, LCH, or HSL is not a WCAG contrast ratio, and judging a pair by comparing the two `L`
values will pass combinations that fail. Compute the real thing: resolve both foreground and
background, convert to linear sRGB, and apply the WCAG relative-luminance formula — via a checker or
a scripted gate.

**Re-verify every resolved pair in every theme.** Contrast is a property of a *pair* of resolved
colors, not of a token name, so a pair passing in light mode establishes nothing about the
corresponding pair in dark mode — swapping only the surface token is enough to break it. Validate
each theme, each high-contrast variant, and each brand skin separately.

**Measure opacity-derived variants after compositing.** A muted variant built as semi-transparent
text over a surface is a *different resolved color* than the token it derives from. Measure the
composited result over each actual background, and judge it against the threshold for how it's
rendered — 4.5:1 for normal text, 3:1 where it genuinely qualifies as large text. If a variant only
clears the bar as large text, that's a constraint to write down, not a free pass at body size.

**Never let color alone carry meaning.** Status, validity, and severity need a text label or an icon
alongside the hue — required for color-blind users, and it's also what keeps a status system legible
when the theme changes.

**Roles and states:**

- Define hover, focus, pressed, selected, and disabled treatments where applicable. Selection
  persists and has a non-color cue; it is not just the hover fill left on.
- Map `accent` to its actual component-library use. In shadcn-style UI it is usually a quiet
  interaction fill paired with `accent-foreground`, not a second saturated brand color.
- Keep decorative edges (`border`) separate from control-identifying edges (`input`).
- Define status text/surface pairs per supported theme. A fixed red, amber, or green is not
  automatically readable as text, icon, and button fill in both light and dark mode.
- Choose color strength and distribution from the brief. No universal saturation cap or color
  percentage establishes quality. See `color-and-surfaces.md` for the process.

`starter-kits.md` supplies optional full-color examples, including hover and input roles. Match
those to the target consumer syntax: `var(--primary)` accepts full colors; `hsl(var(--primary))`
requires HSL channels. Do not mix them. Theme values should be designed and measured as complete
pairs, not produced by blindly inverting lightness.

---

## Border Radius

Use a coherent radius scale suited to the identity and component size. A compact input and a
large media card may use different steps. Peers should be consistent; nested surfaces need
optically compatible inner/outer curves. See `cards.md` for the inset relationship.

---

## Shadows

Elevation is one way to group and prioritize content, not a requirement for every card. Choose
outlined, elevated, tonal, or unboxed treatment according to `cards.md`. Border and shadow can
work together when both are quiet. Neutral or tinted shadows are valid; inspect their appearance
on the actual canvas. A small contact layer plus a soft ambient layer often gives convincing depth.
In dark themes, surface and edge contrast usually do more work than black shadows.

Keep recipes in theme/component tokens, with stronger elevation for overlays where needed.
Do not scatter new shadow values across call sites or animate every static panel on hover.

---

## Icons

Single icon library. Don't mix Lucide with Phosphor with Heroicons.

Sizes:

- 16 px inline with text
- 20 px in buttons
- 24 px standalone

Stroke width consistent. Button icon gap to label: 8 px. Icon-only buttons: minimum 36 px target
with `aria-label`.

Choose recognizable metaphors and consistent stroke/size. An existing Lucide, Phosphor, or
Heroicons set is valid; replacing it for novelty is not a polish improvement.

---

## Touch Targets

- 44×44 px minimum on touch devices
- 36×36 px minimum on desktop
- 8 px gap minimum between adjacent targets

Touch target can extend beyond visual boundary via padding.

---

## Transitions and Motion Timing

```
--duration-instant: 50ms    /* immediate feedback */
--duration-fast:    100ms   /* button clicks, toggles */
--duration-normal:  200ms   /* most transitions */
--duration-slow:    300ms   /* modals, drawers */
--duration-slower:  500ms   /* page transitions */

--ease-default: cubic-bezier(0.4, 0, 0.2, 1)
--ease-in:      cubic-bezier(0.4, 0, 1, 1)
--ease-out:     cubic-bezier(0, 0, 0.2, 1)
--ease-bounce:  cubic-bezier(0.34, 1.56, 0.64, 1)
```

**Default durations:**

- 150 ms for micro-interactions (hover, focus)
- 200 ms for state changes (expand/collapse)
- 300 ms for enter/exit (modals, sheets)

**Easing direction:**

- `ease-out` for entrances
- `ease-in` for exits (keep duration short, < 150 ms — ease-in on slow exits feels sluggish)
- `ease-in-out` for state changes
- `linear` only for continuous loops (marquee, progress)

**Performance rules:**

- Prefer `transform` and `opacity` for movement; small color/border/shadow state transitions
  are also valid. Measure paint-heavy effects; no property alone guarantees smooth delivery.
- Size/spacing transitions can trigger layout. Prefer transform-based movement; profile necessary
  size animation and judge observed jank rather than the property name alone.
- Respect `prefers-reduced-motion`
- Button feedback: 100–150 ms — must feel instantaneous
- Consider springs for interruptible movement; simple CSS easing is enough for many controls.
- Stagger only when it helps explain a rare entrance; never delay ordinary worklists or input
- Prefer an instant theme switch unless a coordinated transition preserves readable pairs throughout

For deeper motion craft (when to animate, custom easing curves, gestures, springs), see
`layer-5-motion.md`.

---

## Visual Rhythm

Consistent vertical spacing creates rhythm. Section headers maintain the same relationship to
their content everywhere. Card grids have uniform gaps. Lists have uniform item spacing. When
rhythm breaks, it's intentional emphasis.

Buttons in card groups must be bottom-aligned across cards of varying content length. Feature
lists in pricing/comparison columns start at the same vertical position. Shared elements
(titles, descriptions, prices, buttons) align across side-by-side cards.

Symmetrical vertical padding often looks wrong. Adjust optically — bottom padding often needs
to be slightly larger than top.

---

## Responsive Precision

Breakpoints:

| Name  | Min width |
| ----- | --------- |
| `sm`  | 640 px    |
| `md`  | 768 px    |
| `lg`  | 1024 px   |
| `xl`  | 1280 px   |
| `2xl` | 1536 px   |

**Rules:**

- Layouts **restructure** at breakpoints — never just shrink
- Headings and body remain readable on mobile; focused form controls generally need at least
  16px to avoid iOS input zoom. That behavior is not a threshold for every text node.
- Touch targets increase on mobile
- No horizontal overflow
- No content hidden without disclosure
- Full-bleed layouts need `env(safe-area-inset-*)` for notches
- Full-height sections use `min-h-[100dvh]`, never `h-screen` (iOS Safari layout jump)
- Multi-column layouts use CSS Grid, not flex percentage math (`w-[calc(33%-1rem)]`)

---

## Theming

- Set `color-scheme: dark` on `<html>` for dark themes (fixes native scrollbars and form
  controls)
- Include `<meta name="theme-color">` matching the current page background
- Native `<select>`: provide explicit `background-color` and `color` (browser defaults look
  broken in dark mode)

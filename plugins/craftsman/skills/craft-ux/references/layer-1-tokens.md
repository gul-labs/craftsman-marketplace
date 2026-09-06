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
and the named scale steps up on an 8px rhythm from `--space-2` onward. No magic numbers. If a spacing
value isn't on the scale, it's wrong.

- Component internal padding: 8, 12, 16, 20, 24
- Section spacing: 24, 32, 40, 48, 64
- Page margins: 16 (mobile), 24 (tablet), 32 (desktop)
- Section gaps on landing pages: 80–120 px between major sections

Token scale (4px grid; named steps follow an 8px rhythm from `--space-2` up):

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
level. Line-height minimum 1.5 for body text, 1.2 for headings.

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
- Maximum 2–3 typefaces per design — one distinctive display font + one refined body font
- No orphaned words on headings — use `text-wrap: balance`
- Tracking (letter-spacing) is size-specific, never one value for all sizes: large display text
  wants *negative* tracking (~`-0.02em` — letters read too far apart as type grows), body stays
  near `0`. Leading tracks size inversely: tight on large headings, looser on body copy.
- Text truncation always uses ellipsis with a tooltip or expand mechanism
- Use `font-variant-numeric: tabular-nums` for any column of numbers
- Use the ellipsis character `…` not three periods `...`
- Use curly quotes `"` `"` not straight quotes
- Add non-breaking spaces in measurements (`10&nbsp;MB`), keyboard shortcuts, and brand names

**Distinctive font suggestions** (when not bound by a project system):

- Display (sans — the default reach): Space Grotesk, Clash Display, Cabinet Grotesk, Satoshi,
  Geist, Outfit, Bricolage Grotesque
- Body: Source Serif Pro, IBM Plex Sans, Libre Franklin, Work Sans, Plus Jakarta Sans

**Serif discipline.** "Creative / premium brief = serif" is itself an AI default — sans display
fonts are the default for the same reason black is the default in fashion. Reach for a display
serif only when the brand brief names one, or the aesthetic is genuinely editorial / luxury /
publication / heritage *and* you can say why this serif fits this brand. When justified, rotate
(don't reuse the same serif across consecutive projects) from a pool like: EB Garamond,
Bodoni Moda, Young Serif, Literata, Spectral, Marcellus — all on Google Fonts. (Playfair
Display, Cormorant, DM Serif, and Newsreader were dropped from this pool: they sit on the
training-data-default list that `impeccable` flags for expressive surfaces — one step less
overused than Fraunces, but on the same trajectory.) **Never default to Fraunces or Instrument
Serif** — the two LLM-favorite display serifs
are now as recognizable a tell as Inter (see `anti-patterns.md` → Visual AI Tells). For
in-headline emphasis, use italic or bold of the *same* family — never inject a serif word into a
sans headline for visual interest.

For the canonical list of fonts to **avoid** (Inter, Roboto, Arial, Fraunces, Instrument Serif —
overused AI defaults), see `anti-patterns.md` → Visual AI Tells. For **15 ready-to-paste
pairings by use case** (verified weights, `@import` lines, Tailwind config), see
`starter-kits.md` → Font pairings.

---

## Alignment

Every element aligns to the grid. Text baselines align across columns. Icon centers align with
text cap-height. Form labels, inputs, and helper text follow consistent vertical rhythm.
Adjacent elements have aligned edges — or the offset is intentional and consistent.

When mathematical centering looks off, trust your eyes. Icons next to text, play buttons in
circles, and text in buttons often need 1–2 px optical adjustments.

---

## Color

All colors through the token system. Never hex, rgb, or palette classes in domain components.

**Contrast (WCAG 2.2 AA):**

| Element                         | Minimum ratio |
| ------------------------------- | ------------- |
| Body text                       | 4.5:1         |
| Large text (18pt+ or 14pt bold) | 3:1           |
| UI components, icons            | 3:1           |
| Focus indicators                | 3:1           |

**Measure the ratio — never eyeball it, and never infer it from a lightness channel.** A token
authored in a perceptual space (OKLCH, HSL, LCH) tempts you to judge contrast from its lightness
value. That estimate is wrong often enough to ship failures. Compute the real thing: convert to
linear sRGB and apply the WCAG relative-luminance formula, via a checker or a scripted gate. A
token can look comfortably separated and measure 2.16:1.

**Re-verify every pair in every theme.** Contrast is a property of a *pair* of resolved colors, not
of a token name — so a pair that passes in light mode tells you nothing about the same pair in dark
mode. Real example of the trap: a text/surface pair measuring a passing 5.05:1 in light mode and a
failing 3.61:1 in dark, because only the surface token was swapped. Every theme, every high-contrast
variant, every brand skin gets its own pass.

**Opacity-derived text variants are the usual culprit.** A muted variant built as ~70% opacity over
a surface is a *different resolved color* than the token it derives from, and routinely lands in the
2:1 range. Measure the composited result, not the base token — and if a variant fails, ban it at all
sizes rather than reserving it for "large text only."

**Never let color alone carry meaning.** Status, validity, and severity need a text label or an icon
alongside the hue — required for color-blind users, and it's also what keeps a status system legible
when the theme changes.

**Rules:**

- Interactive states (hover, focus, active, disabled) have distinct, consistent color shifts
- Disabled states at 40% opacity minimum
- Selected states visually distinct from hover
- Focus rings use the design system's ring token
- 60-30-10 ratio: 60% dominant, 30% secondary, 10% accent
- One bold accent color maximum
- Saturation below 80% on accents — desaturate so they blend, don't scream
- Stick to one gray family (warm or cool, not both)

For canonical AI color tells (purple/blue gradient on white, pure `#000000`, oversaturated
accents, mixed gray families) and their fixes, see `anti-patterns.md` → Visual AI Tells.

For **15 contrast-verified starter palettes** (per product type, in these token roles, ready to
instantiate for greenfield work), see `starter-kits.md` → Starter palettes.

Use HSL (or `oklch` for better gradient interpolation) for easy dark-mode manipulation.
shadcn-style token set:

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222 47% 11%;
  --primary: 222 47% 11%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --destructive: 0 84% 60%;
  --success: 142 76% 36%;
  --warning: 38 92% 50%;
  --border: 214 32% 91%;
  --ring: 222 47% 11%;
  --radius: 0.5rem;
}

.dark {
  --background: 222 47% 4%;
  --foreground: 210 40% 98%;
  /* invert remaining tokens with the same hue, adjusted lightness */
}
```

---

## Border Radius

Consistent system: small for badges/chips, medium for cards/inputs, large for modals/sheets,
full for avatars/pills. Nested elements use smaller radius than their parent. Never mix rounded
and sharp corners in the same visual group.

---

## Shadows

Elevation communicates hierarchy.

- Cards: subtle shadow
- Dropdowns/popovers: medium shadow
- Modals: deep shadow with backdrop

Shadows use consistent direction and a tinted color (never pure black). Multi-layer shadows
create depth; single shadows feel flat. Shadow transitions on hover: 200 ms ease.

In light mode on varied backgrounds, prefer multi-layer shadows over solid borders — they adapt
via transparency:

```css
.card {
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.06),
    0 1px 2px -1px rgba(0, 0, 0, 0.06),
    0 2px 4px 0 rgba(0, 0, 0, 0.04);
}
```

---

## Icons

Single icon library. Don't mix Lucide with Phosphor with Heroicons.

Sizes:

- 16 px inline with text
- 20 px in buttons
- 24 px standalone

Stroke width consistent. Button icon gap to label: 8 px. Icon-only buttons: minimum 36 px target
with `aria-label`.

For icon-metaphor clichés to avoid (rocket for "Launch", shield for "Security") and library
defaults to flag (Lucide-only as an AI tell), see `anti-patterns.md` → Visual AI Tells.

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

- ONLY animate `transform` and `opacity` (GPU-accelerated)
- NEVER animate `width`, `height`, `margin`, `padding`, `top`, `left` (triggers reflow)
- Respect `prefers-reduced-motion`
- Button feedback: 100–150 ms — must feel instantaneous
- Spring physics for interactive elements: `type: "spring", stiffness: 100, damping: 20`
- Stagger list/grid entry with 30–80 ms between items — never mount everything at once
- No transition on color-scheme change

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
- Headings scale down proportionally on mobile; body text never drops below 16px (iOS
  auto-zoom threshold)
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

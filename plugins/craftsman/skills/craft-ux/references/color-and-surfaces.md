# Color & Surfaces — Make the Palette Work on a Screen

Use when choosing or changing colors, building a new visual surface, or repairing flat or clashing
UI. `layer-1-tokens.md` owns token discipline and contrast measurement; this file owns visual choices.

## Start with relationships

Read the brand, imagery, audience, and existing theme before selecting hues. Decide where color
will live: a saturated hero, product imagery, a quiet app canvas with strong actions, or a sequence
of editorial color fields. There is no universal 60–30–10 quota, saturation ceiling, or banned hue.
A vivid blue, purple, warm cream, or pure black can be right for a particular identity.

For a quiet product UI, keep large reading surfaces low in chroma and concentrate stronger color
on action, selection, or meaningful content. For an expressive website, let a deliberate region
carry substantial color while keeping its typography legible and adjacent regions coherent.
Multiple brand colors are valid when their jobs are clear. Semantic status and chart categories
need their own roles; they do not count against a decorative “one accent” rule.

## Build a useful surface family

Choose neutral temperature deliberately. Slightly tinted neutrals can connect the interface to
its imagery or brand, but coloring every white and gray often produces a muddy cast. Neutral white
is valid. A warm canvas with cool product imagery can work; inspect the relationship instead of
banning every temperature difference.

Establish a visible hierarchy using a few roles:

| Role | Purpose | Typical application |
| --- | --- | --- |
| Canvas (`background`) | The page ground | A pale neutral, an intentional color field, or dark ground |
| Surface (`card`, `popover`) | A group above the ground | White or a related lifted tone; foreground paired to it |
| Inset (`muted`) | Quiet support within a surface | Metadata strip, chart plot, input area |
| Interaction (`accent`) | Quiet hover/highlight | Menu item, secondary action, selectable surface |
| Solid action (`primary`) | Strong action emphasis | Main button with its own on-color |
| Decorative border (`border`) | Gentle separation | Card outline, row divider; not an input affordance by default |
| Control boundary (`input`) | Identify an otherwise ambiguous control | Input/checkbox edge, measured against adjacent surfaces |
| Focus (`ring`) | Keyboard location | Visible outside the control, with offset when needed |

Do not add every layer to every component. A lightly outlined card may need no shadow. A white
card on a pale canvas may use a quiet edge and small shadow together. A dark card usually needs
a discernible surface/edge change; a black shadow alone disappears. See `cards.md` for recipes.

## Separate brand color from component-library semantics

Discover how tokens are **consumed**, not just what they are called. In shadcn-style components,
`accent` commonly paints menu-item and ghost/outline-button hover backgrounds. It is not a spare
saturated brand color. Pair `accent` with `accent-foreground`; keep it quiet unless the component
explicitly switches to a contrasting on-color. An expressive secondary brand hue can use a
separate `brand-secondary` role. Avoid changing a shared token to fix one card without checking
its other consumers.

Set a **foreground/background pair** for every surface that carries text. Explicitly define:

- Primary default/hover/pressed fills with readable `primary-foreground`.
- Secondary hover fill and text; selected state with a persistent non-color cue, distinct from hover.
- Card and inset surfaces with primary and secondary text that remain legible on each.
- Status surface/text/icon pairs per theme, with words or symbols conveying the meaning too.
- Focus and control boundaries on the actual adjacent surfaces.

Avoid opacity as a shortcut for a hover fill or secondary text: it changes the resolved color
depending on what is underneath. If used, measure the composited result. A faint decorative card
edge need not meet 3:1; a boundary required to identify a control does. Inactive controls are exempt
from WCAG's contrast minimum, but keep their labels understandable. Do not dim an entire busy card
so that its still-important text becomes unreadable.

## Token format must match the consumer

Keep the target project's syntax. These two conventions are valid **separately**:

```css
/* Full CSS colors: hex, rgb(), oklch(), etc. */
--primary: #1d4ed8;
/* consumer: background: var(--primary); */

/* HSL channels, common in older Tailwind/shadcn setups */
--primary: 221 83% 48%;
/* consumer: background: hsl(var(--primary)); */
```

Never put a full hex value inside `hsl(var(--primary))`. Convert kit values to channel triples
when that is the existing convention. Full-color Tailwind bridges can map a theme color to
`var(--primary)`; discover the framework/version before changing configuration.

For new palettes, a perceptual space such as OKLCH is useful for tuning lightness/chroma, but
neither its coordinates nor an HSL saturation percentage prove harmony or accessible contrast.
Inspect in the browser and measure the resolved pairs.

## Worked application: a quiet blue product UI

The SaaS kit in `starter-kits.md` supplies a pale canvas, white card, dark text, blue solid action,
and light blue hover surface. Use its **roles**, not all its colors at equal prominence:

1. Put the page on `background`, the primary content group on `card`, and metadata on `muted`.
2. Reserve solid `primary` for the principal action; body text uses `foreground`.
3. Give secondary actions `accent` on hover and `accent-foreground` text. Keep normal text
   readable on that fill too, because some existing consumers inherit it.
4. Use `border` for quiet card edges and `input` only where a stronger control edge is needed.
5. Let content imagery, typography, and proportion supply character; do not repeat a blue icon
   tile on every card. For a different visual brief, change the distribution and surface family.

This is one application, not a universal website theme. Starter kits are optional foundations;
they are not complete brand systems or substitutes for a rendered composition.

## Compose dark mode independently

Retain semantic meanings and brand recognition, then choose dark canvas, raised surfaces, text,
edges, and action colors together. Do not invert every lightness or reuse status values unchanged.
Reduce glare from large near-white areas; preserve visible separation between neighboring dark
surfaces. Check primary, muted, and accent text on **all** surfaces where they appear, including
hover, selected, overlays, and photographs. Derive only supported themes; don't add dark mode to
a single-theme site just to satisfy a checklist.

When switching themes, check the transition as well as its endpoints. An animated card background
with immediately changing text can briefly become unreadable. Coordinate the pair or suspend
local hover transitions during the theme swap; a clean instant theme change is valid.

## Finish in context

Render a populated card, secondary action, primary action, input, and status message using the
chosen palette. Check at small and large widths. Evaluate color distribution, depth, and emotional
fit separately from computed contrast. Fix the role mapping before fine-tuning hex values.

Conceptual cross-checks: [Radix color scale roles](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale)
and [Carbon theme/state roles](https://carbondesignsystem.com/elements/color/overview/) distinguish
surface, border, text, and interaction jobs. These are background sources, not runtime instructions
or a requirement to adopt either library.

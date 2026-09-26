# Cards — Anatomy, Surface & Interaction

Read whenever building or polishing cards, tiles, pricing tiers, or grouped panels. Cards are a
legitimate design tool. Poor hierarchy, indiscriminate boxing, and unfinished details make them
generic; borders, shadows, equal columns, or rounded corners alone do not.

## Choose containment from the task

Use a card when one bounded item combines related content, media, or actions: a product, project,
article, plan, or dashboard summary. Prefer rows/tables for repeated records people must compare
quickly, and unboxed sections for a continuous narrative. Avoid wrapping every paragraph in a card
or nesting three outlined containers. Dense dashboards can still use cards for meaningful groups.

| Treatment | Good fit | How to make it feel finished |
| --- | --- | --- |
| Outlined | Quiet collections, settings groups | Thin consistent edge, purposeful spacing, little or no shadow |
| Elevated | Content lifted from a distinct canvas | Subtle contact shadow + soft ambient layer; optional quiet edge |
| Tonal | Summary, featured content, selection | Related low-chroma fill, matched text; don't make all cards compete |
| Media-led | Products, articles, portfolios | Consistent image ratio/crop, strong content hierarchy, restrained frame |
| Metric | A decision supported by a number | Label, value/unit, period/comparison, optional meaningful chart |
| Action/selection | Navigate, choose a plan, open a project | Clear hit target, hover/focus, persistent selected cue where applicable |

Media-led, metric, and action describe content/behavior and may use any suitable surface treatment.
Keep peer cards consistent; use emphasis deliberately for a featured item. “Polished” does not mean
every card gets glass, tilt, gradient, floating icons, or an animation.

## Anatomy and hierarchy

Compose only the slots needed: **media → heading/metadata → body → supporting detail → actions**.

- Make the subject immediately legible. A project title, product image, or key value outranks its
  category label. Limit competing font sizes and weights; keep secondary text readable.
- Give text a shared left edge and a clear spacing rhythm: tight within related text, larger
  between groups, enough perimeter padding that nothing looks pressed against the frame.
- For a roomy web card, 20–24 px padding and 12–16 px between groups are useful starting points;
  compact cards may use 12–16 px padding. Map to existing tokens. At mobile widths preserve text
  room instead of carrying oversized desktop padding. The density and content decide.
- Align repeated media, titles, price blocks, and footers across peers when comparison matters.
  Use flexible body space and `margin-block-start: auto` for footers rather than fixed heights or
  filler copy. Don't force unrelated editorial stories into equal-height slabs.
- Let headings wrap. Use `min-inline-size: 0` on flexible children and safe wrapping for long
  identifiers. Truncate only expendable metadata with an accessible route to its full value.
- Preserve image focal points. Reserve aspect ratio, clip media to the proper corners, and avoid
  accidental double gutters. Keep focus outlines outside any image clipping wrapper.
- Actions need a clear priority. A descriptive link can be enough; a filled button on every tile
  may overwhelm the page. Keep essential actions discoverable without hover.

## Corner and depth craft

Choose radius relative to size and character: a compact data panel and a large consumer media card
need not share one radius value. They should belong to one coherent scale. For an inset image, a
useful starting relationship is inner radius ≈ outer radius minus inset, clamped at zero; inspect
it optically. A 40 px radius on a compact rectangle can squeeze content and look inflated.

Use a quiet border to define an edge, a small contact shadow to anchor elevation, and a diffuse
shadow only when useful. The combination can be excellent when restrained. Test on the real page
background. In dark mode, tune the surface and edge first; strong black shadows rarely supply
enough separation. Do not make every card equally elevated or every shadow conspicuous.

## Worked recipe: an elevated content card

Example values below belong in the token/component layer. Adapt names to the existing system.
This is a neutral structure to tune to the brief, not a new default for every project.

```css
:root {
  --card-radius: 1rem;
  --card-padding: 1.5rem;
  --card-gap: 1rem;
  /* Full CSS colors. For HSL-channel tokens, wrap each operand in hsl(var(...)). */
  --card-border-hover: color-mix(in srgb, var(--border), var(--card-foreground) 15%);
  --shadow-card: 0 1px 2px rgb(15 23 42 / 0.04),
                 0 8px 24px -12px rgb(15 23 42 / 0.12);
}

/* Full-color token convention; see color-and-surfaces.md. */
.content-card {
  display: flex;
  flex-direction: column;
  min-inline-size: 0;
  padding: var(--card-padding);
  gap: var(--card-gap);
  color: var(--card-foreground);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--card-radius);
  box-shadow: var(--shadow-card);
}
.content-card__footer { margin-block-start: auto; }
.content-card__meta { color: var(--muted-foreground); }

/* Add to an actual link/button, not a static article with a click handler. */
.content-card--interactive {
  text-decoration: none;
  transition: background-color 160ms ease-out, border-color 160ms ease-out;
}
@media (hover: hover) {
  .content-card--interactive:hover {
    background: var(--accent);
    color: var(--accent-foreground);
    border-color: var(--card-border-hover);
  }
}
.content-card--interactive:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 3px;
}
@media (prefers-reduced-motion: reduce) {
  .content-card--interactive { transition: none; }
}
```

This entire recipe consumes **full CSS colors**. In an HSL-channel project, adapt every color
consumer to `hsl(var(--token))`, including both `color-mix` operands; otherwise the mix is invalid
and the hover edge may fall back to the text color. Keep the project's convention consistently.

Define `card`, `card-foreground`, `muted-foreground`, `border`, `accent`, `accent-foreground`,
and `ring` for each supported theme. Validate muted text on the hover fill too. The hover edge is decorative; the link/text and focus ring carry the affordance. Override
the shadow and padding as the theme/density requires. CSS grids can stretch peer cards; do not
hardcode card height to hide content differences. Established component libraries may already
provide the anatomy and tokens; customize those instead of adding a duplicate `Card` abstraction.

## Semantics and states

- **Informational:** an `article`, list item, or grouping element; no pointer cursor, hover lift,
  or focus stop suggesting that a static surface is clickable.
- **Single navigation target:** a real link can wrap the card when it has no nested interactive
  controls. Preserve open-in-new-tab and keyboard behavior. A heading link is often sufficient.
- **Multiple actions:** a non-interactive container with separate links/buttons. Never nest
  buttons inside an anchor or turn the whole container into a button around other controls.
- **Selection:** use checkbox/radio semantics or the established selectable component. Show a
  persistent checkmark, label, or border cue and expose checked state; hover alone is not selection.
- **Loading/error/empty:** preserve useful structure, explain recovery, and match expected content
  dimensions. A failed thumbnail must not erase the title or action. See `layer-4-states.md`.

Hover should refine an already complete card. Prefer a subtle fill/edge change; modest lift can
suit browsing cards, while data panels should stay still. No mandatory perpetual loops. A demo
animation is appropriate only when it explains real behavior and supports reduced motion.

## Review the actual card group

Inspect populated, long-title, missing-image, and relevant interaction states at desktop/mobile.
Check edge strength, crop, padding, nested radii, footer alignment, focus clipping, and whether the
group overwhelms its page. Fix the weakest repeated detail before multiplying the component.
Use `visual-design.md` for the page-level acceptance check.

[Radix Card](https://www.radix-ui.com/themes/docs/components/card) is a useful reference for
separating a content container from link/button behavior and responsive size/surface variants.
The anatomy and recipe here are independent guidance, not a requirement to adopt Radix.

# Composition — Pages, Dashboards & Purposeful Expression

How the layers assemble into whole screens. Start with `visual-design.md` for direction and
acceptance, `color-and-surfaces.md` for color composition, and `cards.md` for any card family.

> **craft-ux tie-in:** Before imposing any layout paradigm, read the repo's existing page shells and layout wrappers first (`Glob **/layout.tsx` or equivalent) to understand the grid and nav chrome already in place.

> **See also**
>
> - Spacing, typography, and color tokens → [layer-1-tokens.md](layer-1-tokens.md)
> - Component-level patterns (forms, modals, buttons, pricing tier rules) → [layer-3-components.md](layer-3-components.md)
> - Implementation guidance and primitive usage → [layer-2-primitives.md](layer-2-primitives.md)
> - Anti-patterns to avoid → [anti-patterns.md](anti-patterns.md)
> - Motion patterns (springs, clip-path, scroll sequences) → [layer-5-motion.md](layer-5-motion.md)

---

## Part 1 — Page & Dashboard Patterns

---

### SaaS Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│ Top Bar (56–64 px): logo, search, user menu             │
├──────────┬──────────────────────────────────────────────┤
│ Sidebar  │  Main content area                            │
│ 240–280  │  (breadcrumbs if depth > 2)                   │
│ collapsed│                                               │
│  64–80   │  Cards / data / forms                         │
│          │                                               │
└──────────┴──────────────────────────────────────────────┘
```

For the navigation-pattern-by-hierarchy table (sidebar vs top nav vs tabs vs breadcrumbs), see
[layer-3-components.md](layer-3-components.md) → Navigation. Sidebar collapse state persists across
sessions; active state visually distinct from hover.

---

### Dashboard Content Hierarchy

1. **Value-first metrics.** "You saved 4 hours" > raw numbers. Surface insight, not data.
2. **Actionable insights.** Every metric should imply a next action.
3. **Progressive disclosure.** Summary → detail on demand. Don't dump 50 fields on a card.
4. **Role-based views.** Different personas need different data on the same dashboard. Don't
   build one giant dashboard for everyone.
5. **Time-to-first-value.** New users land and immediately see what to do. Empty dashboard with
   no CTA = activation bleeding.

---

### Data Visualization

- Use domain-appropriate semantic and categorical colors with consistent meanings; red/green
  conventions vary by context, so do not assume every positive number is a success state
- Pattern/icon backup for colorblind accessibility (don't rely on color alone)
- Always include legends
- Axis labels are mandatory
- Truncate long labels with tooltips
- Numeric columns use `font-variant-numeric: tabular-nums`
- Empty state when filters return zero results

---

### Empty States (Dashboard)

For the base empty-state pattern (icon + headline + description + CTA), see
[layer-4-states.md](layer-4-states.md) → Empty States. Dashboard-specific application:

- **Brand-new account:** design a composed "getting started" view that walks the user to
  activation — not just an icon and a button.
- **Filtered list returning zero:** explain what filter is hiding results and offer a one-click
  "clear filters" action.
- The dashboard empty state is your single highest-leverage onboarding surface. Treat it as a
  feature, not a placeholder.

---

### Settings Pages

See [layer-3-components.md](layer-3-components.md) → Settings Pages for the canonical bucket +
side-panel layout and Danger Zone rules.

---

### Toast / Notification Timing

See [layer-3-components.md](layer-3-components.md) → Notifications, Toasts, and Tooltips for the
canonical timing formula, stacking rules, and dismissal behavior.

---

### URL State for Dashboards

URL must reflect:

- Active filters
- Current tab
- Pagination
- Expanded panels
- Search query

Use `nuqs` or equivalent. Users expect to share URLs and have the recipient see the same view.

---

### Landing Page Sections (Possible Flow)

Select and order sections from the actual buying questions and available evidence. Do not
manufacture testimonials, logos, FAQs, or feature tiles just to fill this example.

```
1. Hero (headline + subheadline + CTA + visual)
2. Social proof (logo bar, testimonial snippet)
3. Problem / Solution
4. Features / Benefits (3–4 max)
5. Detailed testimonials
6. Pricing (if applicable)
7. FAQ
8. Final CTA
9. Footer
```

For footer legal-link reachability and consent-banner rules, see
[layer-3-components.md](layer-3-components.md) → Footer Legal Links & Consent Banners.

---

### Above the Fold

Make the offer or subject clear quickly and give the user an understandable next step. The
opening may be led by product imagery, typography, an artifact, or a meaningful live demonstration.
Use the direction established in `visual-design.md`; a hero does not always need a split layout
or a decorative image.

Compose headline, support copy, action, and visual together. Prefer a short heading and clear
supporting sentence, but judge wrapping at actual widths rather than imposing a universal word
count, line count, or padding cap. Reserve enough space for the subject and maintain a usable first
viewport on mobile. Avoid stacked labels, filler badges, and several competing CTAs.

A real product preview, editorial photograph, or custom illustration can carry identity. Use a
text-led opening when typography is the concept. An unrelated gradient blob or fabricated dashboard
is not a substitute for relevant content. Put genuine proof near the claim it supports.

---

### CTA Button Design

For universal button rules (touch target, copy patterns, transitions), see
[layer-3-components.md](layer-3-components.md) → Buttons. Landing-page-specific:

- **Sizing:** use a comfortable target and proportional padding, appropriate to the page density
- **Color:** create a clear emphasis relationship against the section; hue alone does not create urgency
- **Frequency:** one primary CTA per viewport. Secondary CTAs are ghost or text style — never
  two equally-weighted CTAs side by side
- **Hierarchy:** if a secondary action exists (e.g. "watch demo"), it must look distinctly
  secondary — not just a different color of the same shape
- **One label per intent:** "Get in touch", "Contact us", and "Let's talk" on one page are the
  same action wearing three labels — pick one and reuse it in nav, hero, and footer
- **Wrapping:** avoid awkward button labels without truncating meaningful or translated text;
  adjust available width and layout before forcing shorter copy
- **Contrast check before shipping:** every CTA's text passes WCAG AA against its own background
  (ghost buttons over photos need a scrim, backdrop, or stroke) — same check for form inputs,
  placeholders, and focus rings against their section background

---

### Social Proof Placement

- **Logo bar:** immediately after hero
- **Testimonials:** near points of objection (next to pricing, on long-form sections)
- **Stats:** near pricing
- **Trust badges:** near forms and checkout

---

### Pricing Tables (Landing-Page)

See [layer-3-components.md](layer-3-components.md) → Pricing Tables for the canonical tier rules
(max count, highlight method, toggle, alignment). On a landing page specifically, also:

- Place near a testimonial block (objection-handling proximity)
- Show billing period and actual commitment clearly; do not choose a default to obscure the price
- Stats and trust badges adjacent to the table, not buried in the footer

---

### Form Optimization for Conversion

For the canonical form rules (single column, label position, blur validation, placeholder
patterns) see [layer-3-components.md](layer-3-components.md) → Forms. Landing-page-specific
conversion data:

- Single-column forms complete faster with fewer skipped fields than multi-column; every optional
  field costs completions — the phone field is the classic offender. Cut anything you won't act on.

---

### Layout rhythm

Choose layout from the information: equal columns for comparable offers, rows for a sequence,
a dominant region for the main idea, a gallery for visual work. Repeat a family for related content;
change it when the narrative or task changes. No quota of different layout families makes a page
more authored.

A Bento arrangement suits a small set of unequal, meaningful content groups. It is not the default
for every dashboard. Size cells for real content, avoid filler, keep clear reading order, and
restructure on mobile. Use `cards.md` for the individual surfaces.

Cohesion comes from shared type, spacing, radius, and color roles. An inverse section or a second
brand hue can be intentional. Inspect the whole page for continuity and focal points rather than
forcing identical color allocation in every section.

---

### Above-the-Fold Performance

- LCP under 2.5 s
- CLS under 0.1
- INP under 200 ms
- Hero image: explicit dimensions, `priority`/`fetchpriority="high"`, optimized format
- Fonts: `next/font` (or framework equivalent) with `font-display: swap`
- Preconnect to CDN/asset domains
- Above-fold should render before any heavy client JS hydrates

---

### Spacing for Landing

- Section spacing: 80–120 px between major sections
- Section header → content gap consistent across sections
- Aggressive whitespace beats density on marketing pages
- Cap content width around 1200–1440 px with auto margins for ultrawide screens

---

## Part 2 — Expression with a purpose

Set visual intensity from the brief, audience, frequency of use, and content. “Beautiful” does
not imply maximal motion, oversized radii, empty space, or asymmetry. A working dashboard needs
stable scan paths; a campaign may support a more expressive opening. Neither needs a numerical
creativity dial.

| Problem | First design move | Optional expression when justified |
| --- | --- | --- |
| Hero feels generic | Use the subject's characteristic imagery, copy, or type composition | A short demonstration or reveal that explains the product |
| Cards feel cheap | Fix anatomy, padding, crop, edge strength, radii, and surface hierarchy | A considered tonal/featured treatment within the same family |
| CTA is lost | Improve position, contrast, grouping, and competing emphasis | Clear pressed/success feedback |
| Dashboard feels flat | Distinguish canvas, groups, key data, and selected/action states | Meaningful transition after the user changes data or selection |
| Pricing is hard to compare | Align real differences, prices, billing, and actions | A quiet recommended-plan cue, never invented popularity |
| Page lacks character | Revisit content, type, imagery, and color distribution | One coherent motif tied to the subject |

Glass, parallax, 3D tilt, spotlight borders, variable-font animation, and scroll narratives are
specialized techniques. Use them only when they serve the chosen direction and remain usable by
keyboard, touch, and reduced-motion users. Do not hijack normal scrolling, simulate live data,
auto-sort real worklists for spectacle, or require an infinite loop on every card.

Motion references in `layer-5-motion.md` cover execution after the reason to animate is established.
Use existing dependencies or CSS where sufficient; do not add a library merely to make a static
screen feel expensive. Finish with the rendered acceptance in `visual-design.md`.

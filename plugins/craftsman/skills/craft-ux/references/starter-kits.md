# Starter Kits — Font Pairings & Palettes for Generation

Concrete, vetted values for greenfield generation: 19 font pairings (15 by use case + 4 SaaS
landing variants) and 15 starter palettes with measured contrast. These are examples, not a
guarantee of visual quality. Choose and adapt them using the brief and a rendered composition.

> **Source note:** font weight/axis data and the palette industry mapping draw on research from
> the MIT-licensed [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
> dataset (see `THIRD_PARTY_NOTICES.md`); every font choice and palette value here was re-curated
> for this collection. That selection is not a ban on upstream fonts or hues.

> **See also**
>
> - Token discipline and type scale → `layer-1-tokens.md`
> - Contextual failure patterns → `anti-patterns.md` → Visual AI Tells
> - Visual direction and acceptance → `visual-design.md`

## How to use

1. Establish the direction in `visual-design.md` and the role/area relationships in
   `color-and-surfaces.md`. Choose from the actual brief and brand; category names are browsing
   hints, not prescriptions. Existing good tokens take priority over a starter kit.
2. Pick typography and palette independently. Keep a successful pairing across the same product;
   do not rotate it to satisfy a novelty rule. Adapt colors and proportion to the subject rather
   than treating one kit as “the SaaS look.”
3. Instantiate colors in the target token format. The table uses full hex colors; consumers
   expecting `hsl(var(--token))` require conversion to HSL channels first.
4. Render a representative component group. Contrast checks are a floor; evaluate visual fit,
   hierarchy, color distribution, card depth, and states with `visual-design.md`.

**Role change for older kits:** earlier versions used `accent` as a dark secondary brand fill.
Here it is a quiet interaction surface, compatible with shadcn-style hover consumers. When
updating an existing product, inspect all `accent` consumers first. Preserve a real secondary
brand color under a separate role (for example `brand-secondary`) and change only the relevant
interaction consumers. Do not bulk-replace a product's identity with the new table.

These examples are intentionally restrained. An expressive brief may need colored surfaces,
additional brand hues, or a different palette altogether. No optional external design skill is
needed to reach the quality bar; finish the design and rendered critique in this skill.

---

## Font pairings

Weights below are verified against the Google Fonts catalog — every listed weight exists.
The listed imports target Google Fonts. Verify current availability and license terms before
shipping or self-hosting; a working import is not a license review. Fallback stacks: pair each with `ui-sans-serif, system-ui, sans-serif`
(or `ui-serif, Georgia, serif` / `ui-monospace, monospace`).

### 1. SaaS product — Schibsted Grotesk + Wix Madefor Text
Confident grotesk with personality; body built for screens.
```css
@import url('https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@500;600;700&family=Wix+Madefor+Text:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Schibsted Grotesk', 'sans-serif'], body: ['Wix Madefor Text', 'sans-serif']`

### 2. Developer tool — Geist + Geist Mono
Vercel's face: precise, technical, quietly opinionated. Mono for code and data.
```css
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap');
```
Tailwind: `heading: ['Geist', 'sans-serif'], body: ['Geist', 'sans-serif'], mono: ['Geist Mono', 'monospace']`

### 3. Premium consumer / DTC — Young Serif + Hanken Grotesk
Warm single-weight display serif (400 only — scale with size, not weight) over a humanist sans.
Useful for product storytelling with tactile imagery and clear supporting text.
```css
@import url('https://fonts.googleapis.com/css2?family=Young+Serif&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
```
Tailwind: `heading: ['Young Serif', 'serif'], body: ['Hanken Grotesk', 'sans-serif']`

### 4. Luxury / fashion — Bodoni Moda + Figtree
High-contrast didone with optical sizing (`opsz` 6–96 auto-adjusts); neutral geometric body.
```css
@import url('https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,400;6..96,500;6..96,600;6..96,700&family=Figtree:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Bodoni Moda', 'serif'], body: ['Figtree', 'sans-serif']`

### 5. Editorial / publication — Literata + Public Sans
Book-grade optical-sized serif for long reading; civic sans for UI chrome.
```css
@import url('https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,500;0,7..72,600;0,7..72,700;1,7..72,400&family=Public+Sans:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Literata', 'serif'], body: ['Literata', 'serif'], ui: ['Public Sans', 'sans-serif']`

### 6. Fintech / trust — Libre Franklin + Source Sans 3
American gothic gravity; unfussy body. Serious without being sterile.
```css
@import url('https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Libre Franklin', 'sans-serif'], body: ['Source Sans 3', 'sans-serif']`

### 7. Agency / bold marketing — Unbounded + Albert Sans
Expanded display face with real presence; clean geometric body keeps it grounded.
```css
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;500;600;700&family=Albert+Sans:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Unbounded', 'sans-serif'], body: ['Albert Sans', 'sans-serif']`

### 8. E-commerce — Gabarito + Onest
Rounded-but-adult display; highly readable body at product-card sizes.
```css
@import url('https://fonts.googleapis.com/css2?family=Gabarito:wght@500;600;700&family=Onest:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Gabarito', 'sans-serif'], body: ['Onest', 'sans-serif']`

### 9. Wellness / calm — Spectral + Karla
Soft light-weight serif (use 300/400 display) with an easy humanist body.
```css
@import url('https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;0,500;1,400&family=Karla:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Spectral', 'serif'], body: ['Karla', 'sans-serif']`

### 10. Food / hospitality — Marcellus + Karla
Inscriptional single-weight display (400 only) with quiet elegance; warm body sans.
```css
@import url('https://fonts.googleapis.com/css2?family=Marcellus&family=Karla:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Marcellus', 'serif'], body: ['Karla', 'sans-serif']`

### 11. Portfolio / creative — Bricolage Grotesque + Hanken Grotesk
Characterful grotesk with optical sizing and width axes; sibling-feel body.
```css
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700&family=Hanken+Grotesk:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Bricolage Grotesque', 'sans-serif'], body: ['Hanken Grotesk', 'sans-serif']`

### 12. Data / dashboard — Archivo + Spline Sans Mono
Width-axis grotesk (use Expanded for display moments); mono for numerals with
`font-variant-numeric: tabular-nums`.
```css
@import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400;62..125,500;62..125,600;62..125,700&family=Spline+Sans+Mono:wght@400;500&display=swap');
```
Tailwind: `heading: ['Archivo', 'sans-serif'], body: ['Archivo', 'sans-serif'], mono: ['Spline Sans Mono', 'monospace']`

### 13. Education / kids — Baloo 2 + Nunito Sans
Round warmth without Comic-anything; body stays legible at length.
```css
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700&family=Nunito+Sans:wght@400;600;700&display=swap');
```
Tailwind: `heading: ['Baloo 2', 'sans-serif'], body: ['Nunito Sans', 'sans-serif']`

### 14. Accessibility-first / government — Atkinson Hyperlegible + Source Sans 3
Designed for low-vision legibility (400/700 only — hierarchy via size, not mid-weights).
```css
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Source+Sans+3:wght@400;600&display=swap');
```
Tailwind: `heading: ['Atkinson Hyperlegible', 'sans-serif'], body: ['Source Sans 3', 'sans-serif']`

### 15. Heritage / legal — EB Garamond + Albert Sans
Old-style authority for display; modern sans body keeps documents readable on screens.
```css
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:wght@400;500;600;700&family=Albert+Sans:wght@400;500&display=swap');
```
Tailwind: `heading: ['EB Garamond', 'serif'], body: ['Albert Sans', 'sans-serif']`

---

## SaaS landing & marketing variants

A product UI and its landing page serve different purposes but should still share an identity.
These pairings offer alternatives when the brief calls for them; they are not a mandatory rotation.
Verify imports in the target environment before shipping.

### L1. Scandinavian clean — Familjen Grotesk + Albert Sans
Warm grotesk with subtle quirks; reads premium without shouting.
```css
@import url('https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=Albert+Sans:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Familjen Grotesk', 'sans-serif'], body: ['Albert Sans', 'sans-serif']`

### L2. Launch energy — Anybody + Schibsted Grotesk
Width-axis display (set Expanded for the hero) with real poster presence; calm body.
```css
@import url('https://fonts.googleapis.com/css2?family=Anybody:wdth,wght@50..150,500;50..150,600;50..150,700&family=Schibsted+Grotesk:wght@400;500&display=swap');
```
Tailwind: `heading: ['Anybody', 'sans-serif'], body: ['Schibsted Grotesk', 'sans-serif']`

### L3. Technical-warm — Geologica + Public Sans
Variable face with an engineered-but-friendly voice; suits dev-adjacent SaaS marketing.
```css
@import url('https://fonts.googleapis.com/css2?family=Geologica:wght@400;500;600;700&family=Public+Sans:wght@400;500&display=swap');
```
Tailwind: `heading: ['Geologica', 'sans-serif'], body: ['Public Sans', 'sans-serif']`

### L4. Editorial SaaS — Spectral (light) + Hanken Grotesk
Contrarian serif-led landing: light-weight serif display over a neutral sans. Calm confidence;
pairs well with the fintech or forest palettes.
```css
@import url('https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,300;0,400;1,300&family=Hanken+Grotesk:wght@400;500;600&display=swap');
```
Tailwind: `heading: ['Spectral', 'serif'], body: ['Hanken Grotesk', 'sans-serif']`

---

## Starter palettes

The table supplies full CSS colors for brand, neutral, and interaction roles. `accent` is a
**subtle hover surface**, not a second solid action. `on-accent` maps to `accent-foreground`.
`primary-hover` preserves the primary action's on-color. `input` is a control boundary; `border`
is a quieter decorative edge. Status roles are in the separate table below.

For collection maintainers, `python3 scripts/verify-palettes.py` from the **marketplace repository
root** checks every row and the following pairs. This repository script is not bundled inside the
installed plugin. It does not certify visual harmony or arbitrary combinations a product adds:

- Foreground on background/card/muted/accent ≥ 7:1 (this collection's body-text target).
- Muted foreground on those four surfaces ≥ 4.5:1.
- On-primary on primary and primary-hover, and on-accent on accent ≥ 4.5:1.
- Primary, primary-hover, ring, and input against background/card/muted/accent ≥ 3:1.
- Accent against background/card/muted ≥ 1.1:1, an internal distinct-fill check for these kits,
  not an accessibility threshold or proof that a selected state is sufficiently clear.
- Border against background/card ≥ 1.2:1, an internal edge-visibility floor, **not** the WCAG
  threshold for an identifying control border. Use `input` for that job.

All kits are light-mode except the developer-tool example. They are starting points, not automatic
light/dark pairs. Derive supported themes with `color-and-surfaces.md`, then verify actual rendered
pairs, including images and opacity. Maintainers re-run the repository verifier after changing
either source table. When adapting values in a target project, re-measure them with that project's
contrast tooling or a browser-based contrast check; the shipped measurements do not carry over.

| Kit | primary | on-primary | primary-hover | accent | on-accent | background | foreground | card | muted | muted-fg | border | input | ring |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SaaS product | `#1D4ED8` | `#FFFFFF` | `#1942B8` | `#DDE4F1` | `#0F172A` | `#F8FAFC` | `#0F172A` | `#FFFFFF` | `#EEF2F7` | `#44546A` | `#DDE3EC` | `#787F8D` | `#1D4ED8` |
| Developer tool (dark) | `#34D399` | `#052E16` | `#39E8A8` | `#21314A` | `#E6EDF6` | `#0B1120` | `#E6EDF6` | `#111A2E` | `#1B2740` | `#93A5BE` | `#2A3A57` | `#7890AD` | `#34D399` |
| E-commerce | `#047857` | `#FFFFFF` | `#03664A` | `#DAE4E0` | `#12291F` | `#F7FBF9` | `#12291F` | `#FFFFFF` | `#E9F2EE` | `#3F5A4E` | `#D4E4DC` | `#6F837A` | `#047857` |
| Fintech / banking | `#0F172A` | `#FFFFFF` | `#0D1424` | `#DCE0E6` | `#0B1120` | `#F8FAFC` | `#0B1120` | `#FFFFFF` | `#E9EDF3` | `#44546A` | `#DBE2EB` | `#757C88` | `#0F172A` |
| Healthcare | `#0E7490` | `#FFFFFF` | `#0C637A` | `#D8E5E9` | `#123B47` | `#F5FBFC` | `#123B47` | `#FFFFFF` | `#E7F2F5` | `#3D5A63` | `#CFE5EB` | `#63848E` | `#0E7490` |
| Premium consumer (forest) | `#1E3D2F` | `#F4EFE6` | `#1A3428` | `#DFDED6` | `#1B2420` | `#F7F5F0` | `#1B2420` | `#FFFFFF` | `#ECEAE2` | `#4E564F` | `#DBD8CC` | `#797C74` | `#1E3D2F` |
| Creative agency | `#BE185D` | `#FFFFFF` | `#A2144F` | `#E9DCE3` | `#3B0A24` | `#FDF6F9` | `#3B0A24` | `#FFFFFF` | `#F4E9EF` | `#6B4658` | `#EED4E1` | `#967184` | `#BE185D` |
| Education / courses | `#0F766E` | `#FFFFFF` | `#0D645E` | `#D9E5E3` | `#113B36` | `#F5FBFA` | `#113B36` | `#FFFFFF` | `#E8F2F0` | `#3E5854` | `#CFE4E0` | `#658581` | `#0F766E` |
| Food / restaurant | `#B91C1C` | `#FFFFFF` | `#9D1818` | `#E9DFD7` | `#3B1212` | `#FDF8F4` | `#3B1212` | `#FFFFFF` | `#F4ECE4` | `#6B4F45` | `#E9DACB` | `#92766E` | `#B91C1C` |
| Wellness / mindfulness | `#0F766E` | `#FFFFFF` | `#0D645E` | `#DDE2DD` | `#1F2A26` | `#F7FAF7` | `#1F2A26` | `#FFFFFF` | `#EBF0EB` | `#4C5A53` | `#D8E1D8` | `#76807A` | `#0F766E` |
| Analytics dashboard | `#1E40AF` | `#FFFFFF` | `#1A3695` | `#DEE2E9` | `#101935` | `#F8FAFC` | `#101935` | `#FFFFFF` | `#EBEFF5` | `#455473` | `#DBE1EC` | `#767D90` | `#1E40AF` |
| Travel / tourism | `#0369A1` | `#FFFFFF` | `#035989` | `#D8E4ED` | `#0E3A54` | `#F5FAFD` | `#0E3A54` | `#FFFFFF` | `#E7F1F8` | `#3D5A6E` | `#CEE3F0` | `#618397` | `#0369A1` |
| Nonprofit | `#0E7490` | `#FFFFFF` | `#0C637A` | `#DAE4E7` | `#143641` | `#F6FAFB` | `#143641` | `#FFFFFF` | `#E9F1F3` | `#41585F` | `#D2E3E7` | `#68828A` | `#0E7490` |
| AI product | `#047857` | `#FFFFFF` | `#03664A` | `#DDE4DF` | `#101915` | `#F7FAF8` | `#101915` | `#FFFFFF` | `#EAF1EC` | `#43554A` | `#D6E2D9` | `#758079` | `#047857` |
| Portfolio / personal | `#18181B` | `#FFFFFF` | `#141417` | `#DFDFE1` | `#09090B` | `#FAFAFA` | `#09090B` | `#FFFFFF` | `#EDEDEF` | `#52525B` | `#E0E0E3` | `#7B7B7D` | `#18181B` |

Instantiation template (full colors, consumed with `var(--token)`):

```css
:root {
  --background: <background>;
  --foreground: <foreground>;
  --primary: <primary>;
  --primary-foreground: <on-primary>;
  --primary-hover: <primary-hover>;
  --accent: <accent>;
  --accent-foreground: <on-accent>;
  --card: <card>;
  --card-foreground: <foreground>;
  --muted: <muted>;
  --muted-foreground: <muted-fg>;
  --border: <border>;
  --input: <input>;
  --ring: <ring>;
  /* Choose the matching theme from Status pairs below; for each used role:
     --<role>: <solid>; --<role>-foreground: <on-solid>; --<role>-hover: <hover>;
     --<role>-surface: <surface>; --<role>-text: <text>; --<role>-boundary: <boundary>;
     Example role: destructive. Complete these before using status/destructive components. */
}
```

Map additional library roles (such as popover/secondary) deliberately to compatible surface/text
pairs; the table is not an exhaustive framework theme. Define pressed and selected states for the
actual components, including non-color cues. Do not assume unlisted states were validated.

## Status pairs

Examples for light and dark surfaces. Map `<role>-surface` + `<role>-text` to inline feedback,
`<role>` + `<role>-foreground` to solid actions, and `<role>-hover` to their hover fill. Each row's
text/surface and on-solid/solid/hover pairs pass 4.5:1; its boundary/surface passes 3:1. These checks
cover the listed pairings only. Measure the boundary and focus ring against the surrounding page too.
When feedback needs a defined container and its fill merges into the surrounding surface, add an
appropriate boundary or adjust the fill. A readable inline status label need not have a box.

| Theme | Role | surface | text | boundary | solid | on-solid | hover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Light | success | `#DCFCE7` | `#166534` | `#15803D` | `#15803D` | `#FFFFFF` | `#166534` |
| Light | warning | `#FEF3C7` | `#78350F` | `#92400E` | `#92400E` | `#FFFFFF` | `#78350F` |
| Light | destructive | `#FEE2E2` | `#991B1B` | `#B91C1C` | `#B91C1C` | `#FFFFFF` | `#991B1B` |
| Light | info | `#DBEAFE` | `#1E40AF` | `#1D4ED8` | `#1D4ED8` | `#FFFFFF` | `#1E40AF` |
| Dark | success | `#112B21` | `#86EFAC` | `#4ADE80` | `#4ADE80` | `#052E16` | `#86EFAC` |
| Dark | warning | `#302414` | `#FCD34D` | `#FBBF24` | `#FBBF24` | `#451A03` | `#FCD34D` |
| Dark | destructive | `#351A22` | `#FDA4AF` | `#FB7185` | `#FB7185` | `#4C0519` | `#FDA4AF` |
| Dark | info | `#162742` | `#93C5FD` | `#60A5FA` | `#60A5FA` | `#172554` | `#93C5FD` |

Use explicit labels/icons alongside status color. When a brand action resembles a status color
(such as a red food brand), distinguish destructive actions through wording, icon, grouping, and
confirmation; adapt the palette if that remains ambiguous. A mechanical hue ban cannot resolve
that context. Never reuse a light theme's status tokens unchanged in dark mode.

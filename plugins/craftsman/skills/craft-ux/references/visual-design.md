# Visual Design — Direction, Composition & Acceptance

Use for new pages, components, visual redesigns, and polish. A token-compliant interface can still
look poor. Judge the rendered result against the brief as well as checking implementation quality.

## Establish a direction before styling

Inspect the current UI, supplied references, logo, imagery, type, and theme. Preserve an established
identity for a refinement; replace it only within a requested redesign. Missing design documentation
does not make an existing site greenfield. When references are available, inspect them and identify
specific relationships worth learning from: proportion, color distribution, type hierarchy, image
treatment, density. Do not claim to have seen a reference you could not open.

State a compact direction, scaled to the task:

- **Surface and purpose:** selling a product, completing a task, reading, or exploring visual work.
- **Visual character:** two or three concrete qualities, tied to the audience and subject.
- **Color composition:** which region carries color, which stays quiet, and which action stands out.
- **Type and hierarchy:** display/body roles, strongest element, reading width, supporting levels.
- **Surfaces and assets:** card treatment, depth, corner language, and real visual content.

For example: “A project dashboard for studio teams: spacious and precise, pale cool canvas, white
project cards, blue action/selection, restrained shadows, compact metadata, project thumbnails as
the main visual interest.” A different brief may call for saturated fields, warm editorial type,
or a sharp monochrome grid. These are decisions, not preset industry mappings.

For an ambiguous new identity, compare two plausible directions briefly and choose from evidence;
ask only if a missing brand decision materially changes the result. A button fix needs no moodboard.
Keep the direction in the project's existing design notes when available, not a new parallel system.

## Compose before decorating

Work from real content and the intended task. Set the main focal point, widths, groupings, and
reading order before polishing borders. At a glance, primary content must outweigh secondary
information. Vary scale and spacing to create that hierarchy; applying the same card, weight, and
gap everywhere flattens it.

- **Color:** use `color-and-surfaces.md`. Assign roles and areas, then test them in components.
- **Cards:** use `cards.md`. Select containment and anatomy from the content and interaction.
- **Typography:** use `layer-1-tokens.md`. Adjust scale, weight, measure, and leading before
  replacing a suitable font. One well-chosen family can be enough.
- **Imagery:** use provided or properly sourced assets with coherent crop, lighting, and aspect
  ratios. A product preview should show actual product content. Label illustrative data; never
  invent customers, testimonials, results, or evidence to make a layout look credible.
- **Rhythm:** keep related items consistent. Change layout when the information changes; do not
  manufacture asymmetry or new layout families to meet a novelty quota.
- **Detail:** align headings, media edges, metadata, prices, and actions. Give labels less weight
  than the content they explain. A bright badge or heavy border should not beat the primary action.

Build one representative section or component family with realistic content before repeating it.
Judge its color, spacing, imagery, and states together. A palette viewed only as swatches does not
show how an entire screen will feel.

## When the brief asks for premium or luxury

Make quality visible in the composition and materials. A luxury brief can be colorful, technical,
editorial, or playful; beige, black-and-gold, thin serif type, and glass are not prerequisites.
Choose a character specific to the product, then carry it through the small details.

- **Proportion:** give the main image, headline, or product room to lead. Balance spacious regions
  with useful density; oversized padding and empty cards do not create value.
- **Material:** select a coherent surface family. Tune the canvas, card fill, edge, contact shadow,
  and ambient shadow together. A highlight or texture should suggest a material or light source,
  not obscure text or cover every surface. Rich color and crisp contrast are welcome.
- **Typography and assets:** use a deliberate scale, optical alignment, careful wrapping, and
  consistent image art direction. Real product detail earns more attention than a decorative orb.
- **Life and response:** give controls clear hover, press, focus, selected, and pending feedback.
  Use quick, interruptible transitions for actions and a more expressive moment where it helps
  explain or introduce the product. Read `layer-5-motion.md`; do not make every section float,
  blur into view, or loop. Essential content must remain available without an animation finishing.
- **Continuity:** carry the finish through navigation, forms, menus, dialogs, empty/error states,
  footer, and mobile. A polished hero above ordinary, unfinished components is an incomplete result.

Restraint means choosing emphasis. It does not mean stripping away color, depth, imagery, or
personality until every website resembles a plain admin panel. Inspect the whole page and its
interactions against the intended character, then refine the weakest visible region.

## Rendered acceptance

For UI builds and visual changes, inspect the actual result whenever rendering tools are available.
Use the smallest relevant surface: a component preview for a component, the page for a page. This
lightweight visual check does **not** require the full authenticated flow audit in `live-audit.md`.

Capture desktop and mobile together (for example 1280–1440 and 375–390 CSS px), plus affected
supported themes and meaningful states. Inspect both the overall composition and detail crops.
Use the project's browser tooling and the lightweight startup rules in `live-audit.md`; inspect
the documented command before starting a local preview. If the app
cannot run, use current screenshots as limited evidence and report what remains unverified.

If no rendered evidence is available, still check the proposed structure: a clear main task,
distinct primary/supporting type roles, explicit surface/text pairs, meaningful content in each
card, intrinsic wrapping at narrow widths, visible interaction states, and no empty filler or
fabricated proof. Record these as source/design checks; visual acceptance remains unverified.
Do not replace missing visual evidence with arbitrary limits on word counts, hue, or layout count.

| Dimension | Evidence of a finished result | Reason to iterate |
| --- | --- | --- |
| Hierarchy | First focal point and next action are obvious; supporting content is quieter | Everything has equal visual weight; oversized labels compete with content |
| Color | Canvas, surfaces, text, actions, and states belong together; brand is recognizable | Muddy neutrals, accidental brown hover, random tints, washed-out text, competing accents |
| Cards | Useful grouping, coherent padding/corners, aligned content/actions, clear affordance | Empty slabs, nested boxes, cramped copy, heavy outlines, every card styled identically regardless of role |
| Type | Readable body, deliberate scale/weight, balanced wrapping, appropriate density | Font swap disguises weak hierarchy; oversized headings or tiny gray labels |
| Composition | Content shapes layout; imagery earns space; rhythm supports scanning | Repeated generic feature tiles, excessive blank space, filler decoration |
| Detail and behavior | Focus, hover, selection, crops, borders, and responsive reflow feel considered | Clipped focus, arbitrary radii, shifting cards, awkward crops, mobile overflow |

Mark each applicable dimension **ready / needs work / unverified**, with a concrete observation.
These are qualitative judgments, not a fabricated numerical beauty score. Correctness and visual
quality are separate: passing contrast, lint, or token scans cannot establish the latter.

Fix the highest-impact problems in one batch, then capture and inspect the changed result. Further
passes need a specific unresolved defect or user feedback; avoid endless speculative micro-edits.
On polish tasks, a clear failure against the visual brief is in scope now, not automatically a
“future opportunity.” A short delivery note states what changed and what was actually rendered.

## Evaluating this skill

A hand-authored specimen can validate recipes, not prove that a skill improves generation. For a
skill revision, use identical briefs, assets, model, and settings against old and new instructions
in fresh contexts. Include a brand-constrained page, a product dashboard, and a colorful consumer
surface. Compare anonymous desktop/mobile renders for the dimensions above, then check behavior
and contrast. Record failures and uncertainty; do not claim broad improvement from a single demo.

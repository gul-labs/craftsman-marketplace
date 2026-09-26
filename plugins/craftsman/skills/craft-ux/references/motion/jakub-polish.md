# 07b — Jakub Krehel's Production Polish

Jakub Krehel (jakub.kr) — subtle motion for shipped products. Apply in: consumer apps, professional/enterprise interfaces, repeat-use contexts where polish matters but flash distracts. Aim: users feel smoothness, never notice animation.

> **See also**
>
> - Motion audit framework + context routing → `../layer-5-motion.md`
> - Emil's restraint for high-frequency UIs → `./emil-craft.md`
> - Jhey's playfulness for creative/learning contexts → `./jhey-experimental.md`
> - Motion timing tokens → `../layer-1-tokens.md`

---

## Contents

- [Lens](#lens)
- [Enter / Exit Recipe](#enter--exit-recipe)
- [Spring Config](#spring-config)
- [Shadows over Borders](#shadows-over-borders)
- [oklch Gradients](#oklch-gradients)
- [Optical Alignment](#optical-alignment)
- [Icon Swap Animation](#icon-swap-animation)
- [Shared Layout (FLIP)](#shared-layout-flip)
- [Performance: will-change and Gradients](#performance-will-change-and-gradients)
- [Common Mistakes](#common-mistakes)
- [Technique Index](#technique-index)
- [Jakub vs Emil vs Jhey](#jakub-vs-emil-vs-jhey)

---

## Lens

Apply Jakub's approach when:

- The animation decision has already passed Emil's gate (something should animate)
- Context is production work — client-facing, repeated daily use
- Failure mode is distraction, not boredom

---

## Enter / Exit Recipe

Optional materializing effect for a suitable brief. Start with opacity/small movement; add blur
only when it improves continuity without obscuring content or causing expensive paint:

```jsx
// Enter
initial={{ opacity: 0, translateY: 8, filter: "blur(4px)" }}
animate={{ opacity: 1, translateY: 0, filter: "blur(0px)" }}
transition={{ type: "spring", duration: 0.45, bounce: 0 }}
```

Blur creates a "materializing" effect (element comes into focus, not just fades in). Used by Family, Linear, Vercel.

For full container slides, replace `translateY: 8` with `translateY: "calc(-100% - 4px)"`.

**Exits often benefit from less movement.** User focus moves to what arrives, not what leaves:

```jsx
// Exit — less movement, same blur signal
exit={{ translateY: "-4px", opacity: 0, filter: "blur(4px)" }}
```

Exceptions: user-initiated dismissal, item deletion, full-page transitions where direction matters.

---

## Spring Config

| Use case            | Config                                            | Notes                       |
| ------------------- | ------------------------------------------------- | --------------------------- |
| Production default  | `{ type: "spring", duration: 0.45, bounce: 0 }`   | Smooth decel, no overshoot  |
| Slightly more life  | `{ type: "spring", duration: 0.55, bounce: 0.1 }` | Still professional          |
| Playful (non-Jakub) | `bounce: 0.3+`                                    | Use Emil/Jhey contexts only |

`bounce: 0` is the production default. Reserve positive bounce for explicitly playful UI moments.

---

## Shadows over Borders

A subtle layered shadow can define a light surface against a varied background. A quiet border
can work too, alone or with shadow; tune both against the actual canvas. See `../cards.md`.

```css
.card {
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.06),
    0 1px 2px -1px rgba(0, 0, 0, 0.06),
    0 2px 4px 0 rgba(0, 0, 0, 0.04);
}

.card--interactive:hover {
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.08),
    0 1px 2px -1px rgba(0, 0, 0, 0.08),
    0 2px 4px 0 rgba(0, 0, 0, 0.06);
}
```

| Context                        | Recommendation                     |
| ------------------------------ | ---------------------------------- |
| Light mode, varied backgrounds | Multi-layer shadow                 |
| Dark mode                      | Border fine (shadows less visible) |
| Hard edges intentional         | Border fine                        |

---

## oklch Gradients

Use `oklch` color space to avoid muddy gray midpoints when blending complementary colors:

```css
.element {
  background: linear-gradient(in oklch, blue, red);
}
```

sRGB interpolation passes through a desaturated gray zone on complementary pairs. `oklch` interpolates through perceptually uniform space — vivid across the entire range.

Use color hints (not just stops) to control blend midpoint position. Layer gradients with `background-blend-mode` for depth.

---

## Optical Alignment

Mathematical centering and visual centering diverge on asymmetric shapes. Trust your eyes.

**Buttons with icons** — icon glyphs have internal whitespace; reduce padding on the icon side:

```
[  Icon Text  ]  ← Geometric (feels off)
[ Icon Text   ]  ← Optical (feels right)
```

**Play buttons** — triangle points right, creating visual weight left. Shift glyph 1–2px right so it reads as centered.

Rule: if it looks wrong and the math says correct, adjust the math.

---

## Icon Swap Animation

When icon changes state (copy → check, loading → done), animate with `AnimatePresence mode="wait"`:

```jsx
<AnimatePresence mode="wait">
  {isCopied ? (
    <motion.div
      key="check"
      initial={{ opacity: 0, scale: 0.8, filter: 'blur(4px)' }}
      animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
      exit={{ opacity: 0, scale: 0.8, filter: 'blur(4px)' }}
      transition={{ type: 'spring', duration: 0.3, bounce: 0 }}
    >
      <CheckIcon />
    </motion.div>
  ) : (
    <motion.div
      key="copy"
      initial={{ opacity: 0, scale: 0.8, filter: 'blur(4px)' }}
      animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
      exit={{ opacity: 0, scale: 0.8, filter: 'blur(4px)' }}
      transition={{ type: 'spring', duration: 0.3, bounce: 0 }}
    >
      <CopyIcon />
    </motion.div>
  )}
</AnimatePresence>
```

A short icon transition can confirm an action; an immediate swap with a clear label/status is
also valid. Avoid queuing rapid actions behind exit timing. Provide a reduced-motion branch.

---

## Shared Layout (FLIP)

Motion's `layoutId` drives FLIP transitions (First, Last, Invert, Play) between any two components:

```jsx
// Small card view:
<motion.div layoutId="card" className="small-card" />

// Expanded view:
<motion.div layoutId="card" className="large-card" />
```

Motion connects the corresponding elements and animates layout using transforms. See the
[official layout guide](https://motion.dev/docs/react-layout-animations) for the installed version.

**Rules:**

- Corresponding source/destination elements share a `layoutId`; unrelated pairs need distinct IDs.
- `AnimatePresence` can retain an exiting shared element until its transition finishes. Coordinate
  initial/exit props deliberately; do not ban this supported composition.
- Works across height, width, position, and element type

---

## Performance: will-change and Gradients

### will-change

Use only when profiling reveals a promotion problem, before the affected animation starts:

```css
/* Correct — specific properties */
.animated-card {
  will-change: transform, opacity;
}

/* Wrong — wastes GPU memory */
.element {
  will-change: all;
}
```

Name only the property that needs the hint. It does not guarantee GPU compositing. Each promoted
layer consumes memory; remove the hint when no longer useful.

### Gradient animation

Animate a pre-rendered gradient layer using transform/opacity when practical. Changing
`background-position`, `background-size`, or color stops can repaint; none is a universal cheap
GPU path. Profile the target size and browser before committing to continuous effects.

---

## Common Mistakes

| Mistake                                   | Fix                                           |
| ----------------------------------------- | --------------------------------------------- |
| Exit as prominent as enter                | Exit at half the movement and duration        |
| Harsh edge on a varied background         | Tune border/shadow together against that canvas    |
| Geometric centering on asymmetric icons   | Adjust padding/position optically             |
| Hover feedback feels abrupt               | Consider a brief transition; instant feedback can be right |
| `will-change: all`                        | Declare specific properties only              |
| Large gradient repaints each frame        | Prefer transformed/opacity layers; profile actual paint         |

---

## Technique Index

| Technique          | Key insight                                            |
| ------------------ | ------------------------------------------------------ |
| Enter animation    | opacity + translateY(8px) + blur(4px) → all to default |
| Exit animation     | Subtler than enter — less movement, same blur signal   |
| Spring config      | `duration: 0.45, bounce: 0` for production             |
| Shadows vs borders | Tune shadow and edge to the actual background            |
| oklch gradients    | Perceptually uniform — no muddy midpoints              |
| Optical alignment  | Trust eyes over math on asymmetric shapes              |
| Icon swap          | AnimatePresence mode="wait" + opacity + scale + blur   |
| Shared layout      | Shared IDs connect pairs; AnimatePresence can retain exits          |
| will-change        | Specific properties only; set before animation         |
| Gradient perf      | Prefer composited layers; profile paint cost                  |

---

## Jakub vs Emil vs Jhey

| Aspect              | Jakub                       | Emil                          | Jhey                      |
| ------------------- | --------------------------- | ----------------------------- | ------------------------- |
| Focus               | Subtle production polish    | Restraint & frequency         | Playful experimentation   |
| Key question        | "Is this subtle enough?"    | "Should this animate at all?" | "What could this become?" |
| Signature technique | blur + opacity + translateY | Frequency-based gate          | CSS custom properties     |
| Ideal context       | Shipped consumer/pro apps   | High-frequency tools          | Learning & creative       |

Use Jakub after Emil's gate passes — when the decision to animate is made and the goal is production-ready feel.

# Tangled-Style Dark UI — Design System & Architecture

A reusable design + architecture spec for building sites in the **Tangled
Discover** house style. Copy the token block and the effect components into any
new React/Vite project and you get a consistent, sibling-compatible look.

The visual language is **Linear's dark marketing/product system** (deep-dark
canvas, four-step surface ladder, hairline borders, negatively-tracked type)
with **one deliberate substitution: the single chromatic accent is Tangled teal
`#1fb8a6`** instead of Linear's lavender. The original Linear source spec this
derives from is preserved alongside this file as
[`DESIGN-linear-reference.md`](DESIGN-linear-reference.md).

---

## 1. Principles (the non-negotiables)

These are what make a sibling site read as "part of the family":

1. **Dark canvas is the whitespace.** Background is `#010102` (never `#000`).
   Sections separate by lifting onto surface-1 panels, not by white gaps.
2. **Hierarchy via the surface ladder + hairlines, not shadows.** Step
   canvas → surface-1 → … → surface-4. No drop shadows, no atmospheric gradients.
3. **One chromatic accent only — Tangled teal.** Used scarcely: brand mark,
   primary CTA, focus ring, links, "reason" pills, active states. Never as a
   large fill or section background.
4. **Single type voice.** Inter everywhere (display→body), JetBrains Mono only
   for code/IDs. Display weight 600, body 400. Aggressive negative tracking on
   large type; eyebrows get *positive* tracking.
5. **Box edges are black by default; hover adds a faint outer halo only.** No
   inner glow, no background-lift on hover for cards.
6. **Motion is calm.** Smooth-scroll easing, a slow globe, a soft cursor glow —
   all subtle, all respect `prefers-reduced-motion`.
7. **Functional color is allowed in small doses.** Language dots (TS/Go/Rust…)
   and `--success` are the only non-teal colors, and only at dot/badge scale.

---

## 2. Tech Stack & Infrastructure

| Layer | Choice | Notes |
|---|---|---|
| Build | **Vite** | `dev` / `build` (`tsc && vite build`) / `preview` |
| Language | **TypeScript** | `strict`, `verbatimModuleSyntax`, `erasableSyntaxOnly`, `noUnused*` |
| UI runtime | **React 19** | `react-jsx` runtime (no `import React`) |
| Icons | **lucide-react** | stroke icons; size via `size={n}` |
| Smooth scroll | **lenis** | window-level momentum scrolling |
| Globe | **cobe** (v2) | WebGL dotted globe, driven by `globe.update({ phi })` |
| Fonts | **Inter** + **JetBrains Mono** | loaded via Google Fonts `<link>` in `index.html` |
| Styling | **Plain CSS** | single `style.css`, CSS custom properties, BEM-ish classes. No CSS framework. |

Runtime dependencies: `react`, `react-dom`, `lucide-react`, `lenis`, `cobe`.
Dev: `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`,
`@types/react-dom`.

**Why plain CSS + tokens?** The entire system is expressed as CSS custom
properties in one `:root`. A sibling site copies that block and is instantly
on-brand; no build-time theme config to keep in sync.

---

## 3. Project Structure

```
frontend/
├── index.html              # root div + Google Fonts (Inter, JetBrains Mono)
├── vite.config.ts          # @vitejs/plugin-react
├── tsconfig.json           # strict, react-jsx
└── src/
    ├── main.tsx            # entry: imports lenis CSS then style.css, mounts <App/>
    ├── App.tsx             # app shell: <CursorGlow/> <Globe/> <TopNav/> <main.layout>
    ├── style.css           # ALL tokens + component styles (single source of truth)
    ├── lib.ts              # presentation helpers: initials(), gradientFor(), formatCount()
    ├── data.ts             # typed mock data; shapes mirror an ATProto/appview response
    └── components/
        ├── TopNav.tsx      # brand + search + actions
        ├── TangledLogo.tsx # inlined official "dolly" mark (currentColor)
        ├── CenterColumn.tsx# the "protagonist" content column
        ├── RecCard.tsx     # primary content card
        ├── RightColumn.tsx # secondary column (sticky, own scroll)
        ├── Avatar.tsx      # gradient + initials avatar
        ├── CursorGlow.tsx  # cursor-trailing radial glow (effect)
        └── Globe.tsx       # cobe background globe (effect)
```

**Architectural conventions**

- **Tokens are the contract.** Components reference `var(--token)`, never raw
  hex. Re-skinning = editing `:root`.
- **Data is typed and decoupled.** `data.ts` exports typed arrays whose shapes
  mirror what an AT Protocol appview / firehose would return, so swapping mock
  data for live data is a drop-in change. Keep this boundary in sibling sites.
- **Effects are self-contained components** (`CursorGlow`, `Globe`) with their
  own `useEffect` lifecycle + cleanup. Drop them into any `App` shell.
- **Helpers in `lib.ts`** are pure and deterministic (no `Date.now`/`Math.random`
  in render paths — `gradientFor` hashes a seed string).

---

## 4. Design Tokens

This is the canonical `:root`. **Copy it verbatim into a sibling site's CSS.**

```css
:root {
  /* Surface ladder (canvas -> 4) */
  --canvas: #010102;          /* page background — never #000 */
  --surface-1: #0d0e10;       /* cards, panels */
  --surface-2: #141519;       /* featured / hovered surfaces */
  --surface-3: #1b1d22;       /* sub-nav, dropdowns, active toggle */
  --surface-4: #23262c;       /* deepest lifted surface */

  /* Hairlines */
  --hairline: #23252a;        /* default 1px borders, dividers */
  --hairline-strong: #2e3138; /* stronger borders, input focus */
  --hairline-tertiary: #1a1c20;/* nested dividers (list rows) */

  /* Box edges + hover halo */
  --edge-dark: #050506;                          /* black box perimeter (default) */
  --glow-hover: 0 0 16px 0 rgba(255,255,255,0.04);/* faint OUTER halo on hover */

  /* Text */
  --ink: #f7f8f8;             /* headlines + emphasized body */
  --ink-muted: #d0d6e0;       /* secondary text */
  --ink-subtle: #8a8f98;      /* tertiary / meta */
  --ink-tertiary: #62666d;    /* quaternary / timestamps */

  /* Accent — Tangled teal (the ONLY chromatic accent) */
  --accent: #1fb8a6;
  --accent-hover: #34d6c3;
  --accent-pressed: #189e8e;
  --accent-focus: #1fb8a6;
  --on-accent: #04130f;       /* dark ink ON teal fills (contrast) */
  --accent-tint: rgba(31,184,166,0.12);
  --accent-tint-border: rgba(31,184,166,0.28);

  /* Semantic */
  --success: #27a644;

  /* Functional language dots (dot/badge scale only) */
  --lang-ts: #3178c6;  --lang-go: #00add8;  --lang-rust: #e0723a;
  --lang-svelte: #ff3e00; --lang-py: #3572a5; --lang-js: #f1e05a; --lang-zig: #f7a41d;

  /* Radii */
  --r-xs: 4px; --r-sm: 6px; --r-md: 8px;   /* md = buttons + inputs */
  --r-lg: 12px;                            /* lg = cards + panels   */
  --r-xl: 16px; --r-xxl: 24px; --r-pill: 9999px;

  /* Spacing (4px base) */
  --s-xxs: 4px; --s-xs: 8px; --s-sm: 12px; --s-md: 16px;
  --s-lg: 24px; --s-xl: 32px; --s-xxl: 48px; --s-section: 96px;

  /* Type families */
  --font-sans: "Inter", "SF Pro Display", -apple-system, system-ui, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;

  /* Layout */
  --nav-h: 56px;
  --container: 1200px;
  --content-shift: 64px;      /* whole-block right nudge (clears the globe) */
}
```

### Base reset (also copy)
- `box-sizing: border-box`, zeroed margins/padding.
- `body`: `--canvas` bg, `--ink`, `--font-sans`, 16px / 1.5 / `-0.05px` tracking / weight 400.
- Antialiased text; thin custom scrollbars (`--hairline-strong` thumb on transparent).
- `::selection` uses `--accent-tint`.

---

## 5. Typography

Families: **Inter** (display + body, one continuous voice), **JetBrains Mono**
(code, IDs, kbd only).

| Role | Size | Weight | Tracking | Notes |
|---|---|---|---|---|
| Page title (`.center-head h1`) | 28px | 600 | -0.6px | section headline |
| Card title (`.rec__name`) | 17px | 600 | -0.2px | repo/entity name |
| Panel title | 14px | 600 | -0.1px | column headers |
| Body | 16px | 400 | -0.05px | default |
| Body-sm / meta | 13–14px | 400 | 0 | card body, rows |
| Caption | 12px | 400 | 0 | timestamps, stats |
| Button | 14px | 500–600 | 0 | labels |
| Eyebrow (`.center-head__eyebrow`) | 13px | 500 | **+0.4px**, uppercase | teal, taxonomy marker |

Rule of thumb: negative tracking grows with size; the eyebrow is the only
positively-tracked, uppercase element, and it's teal.

---

## 6. Layout & App Shell

**App shell** (`App.tsx`): a fragment containing the two fixed effect layers,
the sticky nav, and the grid.

```
<CursorGlow/>            // fixed, z 40
<Globe/>                 // fixed, z 0 (behind content), wide screens only
<TopNav/>                // sticky, z 50, height --nav-h
<main className="layout">// z 1, the content grid
  <CenterColumn/>        // protagonist column (1fr)
  <RightColumn/>         // secondary column (320px, sticky, own scroll)
</main>
```

**The grid** (`.layout`)
- `max-width: var(--container)` (1200px), centered.
- Desktop: `grid-template-columns: minmax(0,1fr) 320px` (protagonist + sidebar).
- Gap `--s-lg`; `align-items: start`.
- Padding `--s-xl` top, `--s-lg` sides, `--s-section` bottom.

**Whole-block right shift** (to clear the background globe) — applied identically
to `.topnav__inner` and `.layout` so nav and content stay aligned, and capped so
it never overflows:

```css
@media (min-width: 1280px) {
  .globe { display: block; }
  .topnav__inner, .layout {
    margin-left: min(
      calc((100% - var(--container)) / 2 + var(--content-shift)),
      calc(100% - var(--container) - var(--s-lg))
    );
    margin-right: var(--s-lg);
  }
}
```

**Sticky secondary column + independent scroll** — the sidebar pins under the
nav and scrolls on its own (so it doesn't ride the page scroll):

```css
.col--right {
  position: sticky;
  top: calc(var(--nav-h) + var(--s-xl));
  max-height: calc(100vh - var(--nav-h) - var(--s-xl) - var(--s-lg));
  overflow-y: auto;
}
```
The sidebar element also carries `data-lenis-prevent` so Lenis leaves its native
scroll alone (see §8).

### Stacking order (z-index map)
```
globe (0)  <  content/.layout (1)  <  cursor-glow (40)  <  top-nav (50)
```
The content layer is lifted to `z-index: 1` (with `position: relative`) so the
opaque cards occlude the globe; the cursor glow sits above content but below the
nav.

### Responsive breakpoints
| Width | Behavior |
|---|---|
| ≥ 1280px | Globe shown, content shifted right, 2-column grid |
| 1025–1279px | No globe/shift, centered, 2-column grid |
| ≤ 1024px | Sidebar (`.col--right`) hidden, single column |
| ≤ 820px | Tighter padding, page title 28→24px, full-width search |
| ≤ 560px | Nav padding tightened; user handle / kbd hidden |

---

## 7. Elevation & Edges

| Level | Treatment |
|---|---|
| 0 (flat) | body text, nav text — no border/shadow |
| 1 (lift) | `--surface-1` bg + `1px var(--edge-dark)` border → cards, panels |
| 2 (hover/featured) | `--surface-2` bg, used for hovered rows / featured surfaces |
| 3 | `--surface-3` bg → active toggle, dropdowns |
| focus | `2px var(--accent-focus)` at 50% (`color-mix`), `outline-offset: 2px` |

**Edge + hover rule (signature):** boxes (`.rec`, `.panel`) have a **black
perimeter by default** (`border: 1px solid var(--edge-dark)`) and on hover add
**only an outer halo** (`box-shadow: var(--glow-hover)`) — no inner glow, no
background change. Cards add a 1px lift (`transform: translateY(-1px)`).

```css
.panel, .rec { border: 1px solid var(--edge-dark); transition: box-shadow .2s ease, transform .2s ease; }
.panel:hover { box-shadow: var(--glow-hover); }
.rec:hover  { box-shadow: var(--glow-hover); transform: translateY(-1px); }
```

---

## 8. Signature Effects

These four are what give the family its feel. Each is reusable as-is.

### 8.1 Smooth scroll — Lenis
Window-level momentum scrolling with a relaxing `easeOutExpo`.
- Init in `App` `useEffect`; drive `lenis.raf(t)` in a `requestAnimationFrame` loop; `destroy()` on cleanup.
- Config: `duration: 1.2`, `easing: t => Math.min(1, 1.001 - 2**(-10*t))`, `smoothWheel: true`, `wheelMultiplier: 0.9`.
- **Guard:** skip entirely if `prefers-reduced-motion`.
- Import `lenis/dist/lenis.css` in `main.tsx`.
- **Nested scroll:** any element with its own scroll region (e.g. the sidebar)
  gets `data-lenis-prevent` so the page doesn't hijack it.

### 8.2 Cursor glow — `CursorGlow.tsx`
A small, faint white radial that trails the cursor with eased lag.
- Fixed `140px` circle, `z-index: 40`, `pointer-events: none`, fades in on first move.
- Gradient: gaussian-like falloff to fully transparent at 100% (no hard ring), center ~`rgba(255,255,255,0.055)`.
- Follows via lerp (`ease = 0.12`) in a RAF loop; `translate3d(x,y,0) translate(-50%,-50%)`.
- **Guards:** only on `(pointer: fine)`; instant (no lag) under reduced motion.
- The native cursor is left untouched.

### 8.3 Background globe — `Globe.tsx` (cobe v2)
A slow, subtle dotted globe peeking from the left edge.
- `createGlobe(canvas, {...})`, then a RAF loop calling `globe.update({ phi })`; `phi += 0.0025` (≈40s/rotation).
- Palette: `dark: 1`, `baseColor: [.16,.18,.2]`, `markerColor: [.12,.72,.65]` (teal), `glowColor: [.08,.09,.1]`, `diffuse: 1.0`, `mapSamples: 14000`, `mapBrightness: 4.2`.
- Markers scaled together via `MARKER_SCALE` to keep proportions.
- Placement: `position: fixed; left: -190px; top: 50%`, `560px`, `z-index: 0` (behind content), `opacity: 0.5`, gentle fade-in. Shown **≥1280px only**.
- **Guard:** rotation stops (static frame) under reduced motion.

### 8.4 Hover halo
See §7 — black perimeter + outer-only `--glow-hover`. This is the interaction
signature; reuse the `.panel` / `.rec` pattern for any new box type.

---

## 9. Component Catalog

All components reference tokens and live in `style.css`.

- **`.topnav` / `.topnav__inner`** — sticky bar (`--nav-h`, translucent `rgba(1,1,2,.72)` + blur, bottom hairline). Brand (logo + wordmark + `.badge`), centered `.search`, right-side actions.
- **`.brand` / `.brand__logo`** — inlined `TangledLogo` (uses `currentColor`, rendered in `--ink`) + wordmark. Swap the logo component per site; keep the layout.
- **Buttons** — `.btn` base (8×14px, `--r-md`, 36px min-height, focus ring). Variants: `.btn--primary` (teal fill, `--on-accent` text), `.btn--secondary` (surface-1 + hairline), `.btn--ghost`, `.btn--icon`, `.btn--sm`.
- **`.search`** — surface-1 input row, `--r-md`, hairline that strengthens on focus-within.
- **`.panel`** — the lifted box: surface-1, black edge, `--r-lg`, hover halo. With `.panel__head` (title + `.panel__action`) and `.panel__body`.
- **`.rec`** — primary content card: reason pill + identity + split "star" control + description + meta row + tags. The reusable "rich item" card.
- **`.rec__reason`** — teal `--accent-tint` pill carrying a tailored reason string.
- **`.row` / `.recent`** — list rows (avatar/icon + text + time), surface-2 on hover, `--hairline-tertiary` dividers.
- **`.profile`** — sidebar entity row (avatar + handle + bio + reason + stats + follow button). Square hover highlight, `--hairline-tertiary` divider between rows.
- **`.avatar`** (`--sm/--md/--lg`) — gradient circle + initials (`Avatar.tsx` + `initials()`); seedable gradient via `gradientFor()`.
- **`.toggle` / `.toggle__btn`** — pill segmented control; active = `--surface-3` lift.
- **`.tag`** — small surface-2 chip, `--r-sm`.
- **`.badge`** — status pill (`--r-pill`, surface-2, ink-muted).
- **`.lang` / `.lang__dot`** — language indicator using the functional `--lang-*` colors.
- **`.kbd`** — mono key hint chip.

---

## 10. Do's & Don'ts

**Do**
- Reserve teal for brand mark, primary CTA, focus, links, reason pills, active state.
- Use the surface ladder + hairlines for depth; black edges on boxes.
- Keep the data layer typed and shaped like an ATProto/appview response.
- Gate motion effects behind `prefers-reduced-motion` and pointer/width checks.
- Keep effect components self-contained with proper `useEffect` cleanup.

**Don't**
- Ship a light theme, or use `#000` for the canvas.
- Introduce a second chromatic accent, or use teal as a fill/section background.
- Add drop shadows, atmospheric gradients, or inner glows on boxes.
- Pill-round CTAs (CTAs use `--r-md` 8px).
- Hardcode hex in components — always go through a token.

---

## 11. Bootstrapping a New Linked Site

To spin up a sibling site that matches this one:

1. **Scaffold:** `npm create vite@latest <site> -- --template react-ts`.
2. **Install:** `npm i lucide-react lenis cobe` (add `cobe` only if you want the globe).
3. **Fonts:** add the Inter + JetBrains Mono Google Fonts `<link>` to `index.html`.
4. **Tokens:** paste the §4 `:root` block + base reset into your `style.css`.
   This alone makes the site on-brand.
5. **Effects:** copy `CursorGlow.tsx`, `Globe.tsx` (and the Lenis `useEffect` +
   `lenis/dist/lenis.css` import) into the new project. Mount them in `App` in
   the §6 stacking order.
6. **Shell:** reuse the `.topnav`, `.layout`, `.panel`, `.btn` patterns. Swap the
   `TangledLogo` for the sibling's mark (keep `currentColor` + `--ink`).
7. **Data boundary:** define typed `data.ts` arrays mirroring your AT Protocol
   records; wire live data behind the same shapes later.
8. **Stay in the contract:** new components reference tokens only; new box types
   follow the black-edge + outer-halo hover rule; keep teal scarce.

**The "family" checklist** — a sibling site is consistent if: canvas is
`#010102`, the only accent is `--accent`, boxes have black edges + outer-halo
hover, type is Inter with the §5 scale, and motion respects reduced-motion.

---

## 12. Known Gaps / Notes

- Surface ladder + accent values are this project's canonical spec; treat §4 as
  the source of truth (the Linear-derived values in
  [`DESIGN-linear-reference.md`](DESIGN-linear-reference.md) are the historical
  inspiration).
- The data layer is currently mock; shapes are intentionally ATProto-compatible.
- Form error/validation styling isn't defined yet — add as a token-driven variant.
- The globe is desktop-only (≥1280px) by design; it's ambient, not essential.

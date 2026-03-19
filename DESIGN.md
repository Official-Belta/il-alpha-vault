# Design System — IL Alpha Vault

## Product Context
- **What this is:** Uniswap V4 hook-based automated LP vault that removes liquidity during high volatility to protect against impermanent loss
- **Who it's for:** DeFi liquidity providers seeking passive IL protection, and token projects needing managed liquidity
- **Space/industry:** DeFi yield management / automated liquidity management (Arrakis, Gamma, Sommelier, Charm)
- **Project type:** Marketing site + performance dashboard (web app)

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian — function-first, data-dense where needed, clean where not
- **Decoration level:** Intentional — subtle grain texture on dark surfaces, no 3D blobs or particle effects. The data is the decoration.
- **Mood:** Precise, quantitative, confident. Bloomberg terminal meets modern fintech. The product is about a clear binary signal (LP on/off) and the design embodies that clarity.
- **Reference sites:** Arrakis (institutional tone), Lido (clean hierarchy), EigenLayer (typographic boldness)

## Typography
- **Display/Hero:** Satoshi (900, 700) — geometric, confident, not overused in crypto. Tight letter-spacing (-0.03em) for density that signals precision.
- **Body:** Geist Sans (400, 500, 600) — purpose-built for interfaces by Vercel. Excellent readability at every size.
- **UI/Labels:** Geist Sans (500, 600)
- **Data/Tables:** Geist Mono — tabular-nums built in, pairs perfectly with Geist Sans. Use for all numerical displays.
- **Code:** Geist Mono
- **Loading:**
  - Satoshi: `https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap`
  - Geist: `https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-sans/style.min.css`
  - Geist Mono: `https://cdn.jsdelivr.net/npm/geist@1.3.1/dist/fonts/geist-mono/style.min.css`
- **Scale:**
  - Hero: clamp(40px, 6vw, 72px) / weight 900 / tracking -0.03em
  - H1: 28px / weight 700 / tracking -0.02em
  - H2: 20px / weight 700 / tracking -0.02em
  - Body: 16px / weight 400 / line-height 1.7
  - Body Small: 14px / weight 400 / line-height 1.6
  - Caption: 13px / weight 500
  - Label (mono): 11px / weight 500 / uppercase / tracking 0.08em

## Color
- **Approach:** Restrained — one distinctive accent + neutrals. Color is rare and meaningful.
- **Primary accent:** `#00E5A0` (mint/emerald) — distinctive teal-green that no competitor uses. Signals "different approach" visually.
- **Accent dim:** `#00B87D` — for hover states and light-mode accent
- **Signal Active (LP on):** `#00E5A0` — same as accent, reinforcing the brand
- **Signal Removed (LP off):** `#F5A623` (amber) — high-vol regime, LP pulled
- **Neutrals (dark mode):**
  - Background: `#0A0E14`
  - Surface 1: `#111620`
  - Surface 2 (cards): `#1A1F2B`
  - Card hover: `#222838`
  - Border: `#2A3040`
  - Border light: `#353D50`
  - Text tertiary: `#6B7280`
  - Text secondary: `#9CA3AF`
  - Text primary: `#F3F4F6`
- **Semantic:** Success `#34D399`, Warning `#FBBF24`, Error `#EF4444`, Info `#60A5FA`
- **Dark mode:** Default. Dark-first design.
- **Light mode strategy:** Swap surface/text values. Accent shifts to `#00B87D` (slightly darker for contrast on white). Reduce background saturation.

## Signal State Design Language
The binary LP on/off mechanic is a core visual identity element:
- **LP Active:** Mint dot (pulsing) + `LP Active` label on `rgba(0,229,160,0.12)` background with `rgba(0,229,160,0.25)` border
- **LP Removed:** Amber dot (pulsing) + `LP Removed` label on `rgba(245,166,35,0.15)` background with `rgba(245,166,35,0.25)` border
- Use pill-shaped indicators (`border-radius: 9999px`) with Geist Mono text
- The vol regime timeline uses these two colors as horizontal blocks to show LP active/removed periods

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable — not as dense as Bloomberg, not as airy as Lido
- **Scale:** 2xs(2px) xs(4px) sm(8px) md(16px) lg(24px) xl(32px) 2xl(48px) 3xl(64px)

## Layout
- **Approach:** Hybrid — grid-disciplined dashboard, slightly more editorial marketing page
- **Grid:** 12 columns on desktop, 6 on tablet, 4 on mobile
- **Max content width:** 1200px
- **Border radius:** sm: 4px, md: 8px, lg: 12px, full: 9999px (signal pills)

## Motion
- **Approach:** Minimal-functional — state transitions only. No scroll-driven theatrics.
- **Easing:** enter(ease-out / `cubic-bezier(0.16, 1, 0.3, 1)`) exit(ease-in) move(ease-in-out)
- **Duration:** micro(80ms) short(180ms) medium(300ms) long(500ms)
- **Signal dot pulse:** 2s ease-in-out infinite (opacity 1 → 0.4 → 1)
- **LP on/off toggle:** Should have a satisfying but quick transition (300ms)

## Anti-patterns (never use)
- Purple/violet gradients
- 3D blobs, particle effects, floating shapes
- Generic hero animations — the live data IS the hero
- Centered-everything layouts with uniform spacing
- Bubbly uniform border-radius on all elements
- Gradient buttons

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-19 | Initial design system created | Created by /design-consultation based on competitive research (Arrakis, Lido, EigenLayer, Sommelier) and product positioning as the only vol-based LP on/off protocol |
| 2026-03-19 | Mint/emerald accent (#00E5A0) | Every competitor uses purple/pink/cyan. Mint provides instant visual differentiation. |
| 2026-03-19 | Signal-state color language | Green=active, Amber=removed maps the binary mechanic directly to visual identity. The UI teaches the product concept. |
| 2026-03-19 | No hero animation — data is the hero | Competitors use particle effects and 3D elements. Leading with live performance data signals credibility and proves the product works. |
| 2026-03-19 | Industrial/Utilitarian aesthetic | Product is quantitative (vol oracles, variance thresholds). Design should signal that rigor, not chase neon-futurism. |

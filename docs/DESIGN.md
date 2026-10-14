# SENTINEL — Visual Design System (for a new project)

This document is the single source of truth for Sentinel's visual identity. Any new screen, component or page must be built FROM these tokens — never from memory of "what Sentinel looks like."

## 1. Brand assets

Two logo files exist and must be used as-is: a white wordmark and an icon-only favicon mark. Never recreate, redraw, recolor or modify them. Place them in `assets/brand/`.

## 2. Color tokens (exactly six colors, nothing else)

```toml
[colors]
navy          = "#0A1A3F"   # app background, sidebar, field fill, text on inverted surfaces
cream         = "#FFEBE8"   # primary text, structural borders, inverted surfaces, primary buttons
white         = "#FFFFFF"   # wordmark, big numerals, detection outlines
cyan          = "#3CC8F0"   # accent only — see the accent rules below
charcoal      = "#1C1F26"   # assistant panel surface only
status_online = "#2ECC71"   # online connection dot only

[opacity]
surface        = 0.12   # white mixed into navy for the opaque panel; also the translucent veil on video
surface_strong = 0.18   # hover / selected veil
line           = 0.35   # structural borders (cream at this opacity)
text_secondary = 0.82   # secondary text opacity — never go lower (contrast floor)
grid           = 0.05   # chart gridlines
dashed         = 0.60   # low-priority dashed outlines
motif          = 0.28   # city-map line opacity
point          = 0.60   # city-map light points, before the soft glow
composer       = 0.78   # navy veil on the Senti composer only
glow           = 0.62   # cyan mixed into navy: the brighter glow blue
glow_deep      = 0.32   # cyan mixed into navy: the deeper glow blue
cream_hint     = 0.18   # cream mixed into navy, only inside the aurora
aurora_idle    = 0.45   # idle aurora strength, about half of full
aurora_pulse   = 0.72   # low point of the thinking pulse
aurora_active  = 1      # full aurora strength while Senti is thinking
```

Rules:
- No red, orange, yellow, purple, gray, or any color outside these six. No gradient fills, except the Senti composer aurora below. Severity and event status are shown through typography weight, borders, opacity, and marker shape.
- `charcoal` is restricted to the assistant chat panel (`.chat-frame`). It is not a sidebar, page, card, button, chart, or text color. Cream, white, and cream at `text_secondary` on charcoal meet WCAG AA for normal text. The panel sets cream as its text color.
- `status_online` is restricted to the filled dot on a connection-status indicator (`.status-online`), such as the sidebar "En línea" mark. It is never used for severity, event status, buttons, charts, or text. The label next to the dot stays cream. An offline connection stays a hollow cream dot.
- Color balance across a screen: navy ~60%, cream ~25%, white ~15%. Cyan is a line, not an area, and stays out of that balance.
- White is reserved for the wordmark, large metric numerals, and detection outlines in any video/graphic. Cream carries text, structural borders, and inverted surfaces.
- Accent (cyan) is allowed only for button outlines, active borders, focus rings, thin lines, and small highlights. Never for large surfaces, never for text blocks, and never as a stroke on a cream fill (cyan against cream fails non-text contrast). Cyan against navy and against the panel meets non-text contrast.
- Text contrast on navy meets WCAG AA for normal text: cream on navy, white on navy, and cream at `text_secondary` on both navy and the panel. The same pairs pass on the panel and on charcoal.
- Inverted surfaces (solid cream background + navy text) are reserved for the highest-priority elements on a screen — an active alert/banner, the most recent/important item in a list, and primary buttons. The active nav item is a cyan border, not an inverted fill. Show at most two inverted blocks at once so hierarchy stays legible.
- Standard panels: an opaque mix of white at `surface` into navy (a slightly lighter navy), 2px cream border at `line` opacity, 16px radius, 24px padding. The panel is opaque so a background motif never shows through the text inside it.
- Fields: navy fill (or transparent, which shows that same navy), with a solid cream border. Focus moves the border and the ring to cyan.
- Glass blur and gradient fills are forbidden on every surface except the Senti composer (`.senti-composer`), which stays pinned to the bottom of the assistant panel. That composer is a translucent navy veil at `composer` opacity with a backdrop blur of `composer_blur` and a 1px cream border at `line` opacity. Its radius is `composer_radius`. The aurora rises from the bottom edge and covers `aurora_height_pct` of the composer, full width. It is a wide elliptical fan, brightest at the bottom center, fading upward and toward both sides: two or three radial gradients in glow blue (cyan mixed into navy at `glow`), cyan, and a hint of cream (cream, then cream mixed into navy at `cream_hint`, then transparent). A thin cyan line sits on the very bottom edge. Idle, the fan is still and centered at `aurora_idle`. While Senti is thinking it reaches `aurora_active`, and the same spring drifts the gradient centers by `aurora_drift_pct` and pulses the strength down to `aurora_pulse`. `prefers-reduced-motion: reduce` keeps the idle fan still. Typed text and the placeholder sit above the fan. The round controls and the site pill use the same navy veil so they stay crisp over the light. Text on the composer is cream, white, or cream at `text_secondary`. Those pairs meet WCAG AA on navy, and the veil stays in that same dark range over the fan, so the same pairs meet WCAG AA on the glass.

## 3. Typography

Font: **Poppins** (weights 500/600/700/800), fallback Inter, then system sans-serif. Bundle font files locally so it works offline. Never use a weight below 500 or a size below 13px anywhere.

| Element | Size | Weight |
|---|---|---|
| Page title | 44px | 800 |
| Page subtitle | 22px | 600 |
| Tagline / supporting text | 17px | 500 |
| Section label (uppercase, letter-spaced) | 14px | 700 |
| Body text | 17px | 500 |
| Alert/banner title | 32px | 700 |
| Alert/banner meta text | 18px | 500 |
| Card/list item title | 20px | 700 (uppercase) |
| Card/list item meta | 16px | 500 |
| Large metric numeral | 64px | 800 |
| Metric label | 13px | 700 uppercase |
| Nav item | 18px | 600 (700 when active) |
| Button label | 16px | 700 |
| Table header | 13px | 700 uppercase |
| Table row | 16px | 500 |
| Badge / status chip | 13px | 700 |

IMPORTANT: if the framework renders icon fonts (Material icons, icon ligatures, etc.), exclude those elements from the global font-family override — otherwise icon glyphs render as literal words (e.g. "arrow_right") instead of symbols. Scope the custom font to text elements only.

## 4. Layout tokens

```toml
[layout_px]
sidebar_width     = 280
content_max_width = 1600
video_or_media_column_pct = 68   # the dominant content area takes ~68% of width
panel_radius      = 16
panel_padding     = 24
border_width      = 2
button_min_height = 48
nav_item_height   = 52

[brand_px]
wordmark_width    = 220
wordmark_margin   = 32    # never let the wordmark touch an edge/crop
icon_tile_size    = 64    # cream tile for the favicon and app icon only; login uses the wordmark with no tile
icon_tile_padding = 12
motif_marker_size = 14    # small "+" coordinate marks / corner ticks, decorative only
composer_radius   = 24    # Senti composer only
composer_blur     = 16    # backdrop blur on the Senti composer only
```

## 5. Status and severity (no extra colors)

- High priority: solid cream fill, navy text, weight 800, plus a 6px solid cream left border.
- Medium priority: 2px cream outline, cream text.
- Low priority: 2px dashed cream outline at 60% opacity, secondary-text color.
- Status markers use shape, not color: ● filled (active), ◐ half (in progress/acknowledged), ○ hollow (resolved/done) — always paired with a text label.
- The connection indicator is the one exception to that color rule. Online is a filled `status_online` dot. Offline is a hollow cream dot. The words beside it stay cream.

## 6. Visual language / brand motif

- Background motif on the public landing, on every slide except the hero: a sparse city plat. Thin cyan streets and a few blocks, drawn as a lightweight inline SVG (no raster), at `motif` opacity. A handful of small cyan points at `point` opacity. A soft glow is allowed only on those points, never on buttons, panels, or type. The hero slide is plain navy, with no streets and no points.
- The motif never appears inside the app. Authenticated pages and the login screen are plain navy. It stays off the sidebar.
- It never sits behind dense text unless that text is on an opaque panel. On the landing, titles may sit on the motif; body copy sits in panels. Page titles inside the app sit on the plain navy canvas; body copy, lists, forms, and the assistant thread sit in panels.
- Small "+" coordinate markers and thin corner ticks (viewfinder-style) at `motif_marker_size`, in cream at `line` opacity, placed at the corners of the main content panel and empty states. These ticks stay on panels inside the app. They are not the city map.
- Overall feel: futuristic, minimal, confident, premium, "deep-tech security infrastructure." Avoid anything that reads as a generic admin template, default framework styling, or corporate-software-circa-2015.

## 7. Layout pattern

- Thin sidebar (fixed width, full height) on a solid navy background, wordmark at the top with generous margin, simple nav list below, system/status indicator pinned to the bottom. The active item uses a cyan border.
- Login: the white wordmark is centered at the top of the panel, with no tile and no background behind it, and generous space (`wordmark_margin`) below it. The title and subtitle are centered. Form fields stay full width.
- Header area: page title + one-line subtitle + short supporting tagline. Avoid repeating the main brand name as giant text if the sidebar wordmark already establishes it — the header should name the current section instead.
- Main content area: one dominant panel (video, main data view, or primary canvas) taking the majority of the width, with a secondary panel (live feed / list / assistant) alongside or below it.
- Any chat/assistant UI: message thread on top, input pinned at the bottom of its own panel — never floating over other content. Senti's composer is that pinned input. The glass blur and the aurora stay inside it.

## 8. Implementation rule

Define every token above ONCE (a config/theme file), generate all CSS variables and any platform-specific color formats (e.g. BGR tuples for OpenCV, if applicable) FROM that single file. No hex code, px size, or font weight may be hardcoded anywhere else in the codebase. Add an automated check that fails the build if a color outside the six tokens appears anywhere, if `charcoal` or `status_online` is used outside the assistant panel or the online connection dot, and if a gradient or a backdrop blur appears outside `.senti-composer`.

## 9. Integration with the SentinelAI MVP (see docs/PRD.md)

- Brand files live in `assets/brand/`: `sentinel-wordmark-white.png` (white wordmark: sidebar top, and the login screen with no tile) and `sentinel-icon.png` (icon mark: favicon and app icon, inside a cream tile). The cream icon tile is required for the favicon and app icon only, not on the login screen.
- Severity mapping (PRD uses 4 levels, design uses 3 styles + one extra):
  - critical → high-priority style (inverted cream fill, navy text, weight 800, 6px left border) + label "CRÍTICO".
  - high → 2px solid cream outline, weight 800, 6px solid cream left border, label "ALTA".
  - medium → 2px cream outline, label "MEDIA".
  - low → 2px dashed outline at 60% opacity, label "BAJA".
- Event status markers: nuevo ●, en revisión ◐, resuelto ○, falso positivo ○ with strikethrough label.
- Snapshots / video overlays: bounding boxes and zone polygons drawn in white (OpenCV BGR (255,255,255)), 2px lines, bold labels. Token values imported from the same theme file.
- Charts (Recharts): bars/lines in cream or white, axes and gridlines in cream at `line`/`grid` opacity, no other colors. Differentiate series with solid vs dashed strokes, not colors.
- shadcn/ui components must be re-themed from the tokens; no default shadcn colors may remain.
- All UI copy in Spanish.

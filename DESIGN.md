---
name: Sentinel
description: Deep-tech security infrastructure — night operations over a city plat
colors:
  navy: "#0A1A3F"
  cream: "#FFEBE8"
  white: "#FFFFFF"
  cyan: "#3CC8F0"
  charcoal: "#1C1F26"
  status-online: "#2ECC71"
  panel: "#273556"
  panel-strong: "#364362"
  line: "color-mix(in srgb, #FFEBE8 35%, transparent)"
  text-secondary: "color-mix(in srgb, #FFEBE8 82%, transparent)"
  dashed-line: "color-mix(in srgb, #FFEBE8 60%, transparent)"
  grid-color: "color-mix(in srgb, #FFEBE8 5%, transparent)"
  composer-fill: "color-mix(in srgb, #0A1A3F 78%, transparent)"
  glow-blue: "#2985AD"
typography:
  display:
    fontFamily: "Poppins, Inter, sans-serif"
    fontSize: "44px"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "normal"
  headline:
    fontFamily: "Poppins, Inter, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "normal"
  title:
    fontFamily: "Poppins, Inter, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0.12em"
  body:
    fontFamily: "Poppins, Inter, sans-serif"
    fontSize: "17px"
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "Poppins, Inter, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.45
    letterSpacing: "0.12em"
rounded:
  panel: "16px"
  composer: "24px"
  pill: "24px"
  icon: "50%"
spacing:
  mark: "12px"
  panel: "24px"
  wordmark: "32px"
  sidebar: "280px"
  content: "1600px"
components:
  button-primary:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.navy}"
    typography: "{typography.label}"
    rounded: "{rounded.panel}"
    padding: "0 24px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.navy}"
    rounded: "{rounded.panel}"
    padding: "0 24px"
    height: "48px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    typography: "{typography.label}"
    rounded: "{rounded.panel}"
    padding: "0 24px"
    height: "48px"
  button-outline-hover:
    backgroundColor: "{colors.panel-strong}"
    textColor: "{colors.cream}"
    rounded: "{rounded.panel}"
    padding: "0 24px"
    height: "48px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label}"
    rounded: "{rounded.panel}"
    padding: "0 24px"
    height: "48px"
  chip-on:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    rounded: "{rounded.panel}"
    padding: "0 24px"
    height: "48px"
  input:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.cream}"
    typography: "{typography.body}"
    rounded: "{rounded.panel}"
    padding: "0 12px"
    height: "48px"
  frame:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.cream}"
    rounded: "{rounded.panel}"
    padding: "24px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    rounded: "{rounded.panel}"
    padding: "0 12px"
    height: "52px"
  nav-item-active:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    rounded: "{rounded.panel}"
    padding: "0 12px"
    height: "52px"
  severity-critical:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.navy}"
    rounded: "{rounded.panel}"
    padding: "24px"
---

# Design System: Sentinel

## Overview

**Creative North Star: "The Night Watch Plat"**

Sentinel is a night operations floor. The canvas is deep navy, the instruments are cream, and cyan is a sightline — never a surface. The public pitch sits on a sparse city plat: thin cyan streets, a few blocks, a handful of glowing points. Inside the app that plat disappears. Authenticated work happens on plain navy, in opaque panels, with viewfinder `+` ticks at the corners.

The system is futuristic, minimal, confident, and premium. It reads as deep-tech security infrastructure, not as a generic admin template. Hierarchy comes from inversion, weight, border style, and marker shape — never from a seventh color. Motion is sparse and mechanical: a spring that settles without bounce, an aurora that lives only inside Senti's composer, and a hero animation that pauses when the visitor prefers reduced motion.

Copy is Spanish. Tokens live once in `theme/tokens.toml` and generate CSS and Python. No hex, pixel, or weight is authored anywhere else.

**Key Characteristics:**
- Exactly six colors. Cyan is a line. Charcoal and link-green are locked to one surface each.
- Cream on navy is the voice. White is reserved for the wordmark, metric numerals, and detection outlines.
- Inverted cream blocks are the highest-priority objects on a screen — at most two at once.
- Flat surfaces. No drop shadows. Depth is tonal: navy, then a 12% white mix, then a cream stroke at 35%.
- Poppins 500–800 only. Nothing below 13px. Section labels and card titles are uppercase and tracked.
- Viewfinder `+` marks on panels. City plat only on the public pitch, never behind dense text, never inside the app.

## Colors

A closed night palette: navy field, cream instruments, white signals, cyan sightlines.

### Primary
- **Night Watch Navy** (`{colors.navy}`): App canvas, sidebar, field fill, and text on inverted cream. About 60% of any screen.
- **Signal Cream** (`{colors.cream}`): Primary text, structural borders, inverted surfaces, and primary buttons. About 25% of any screen.

### Secondary
- **Detection White** (`{colors.white}`): Wordmark, large metric numerals, and detection outlines in video or graphics. About 15% of any screen. Not body text.

### Tertiary
- **Sightline Cyan** (`{colors.cyan}`): Button outlines, active nav borders, focus rings, pitch underlines, and city-plat streets. Never a large fill, never a text block, never a stroke on cream.

### Neutral
- **Senti Charcoal** (`{colors.charcoal}`): Assistant thread surface (`.chat-frame`) only.
- **Link Green** (`{colors.status-online}`): Filled "En línea" dot only. Offline is a hollow cream circle. The words beside it stay cream.
- **Panel Mix** (`{colors.panel}`): Opaque white at 12% into navy. Standard card and frame fill.
- **Hover Mix** (`{colors.panel-strong}`): White at 18% into navy. Hover and selected veils.
- **Instrument Line** (`{colors.line}`): Cream at 35%. Structural 2px borders.
- **Secondary Voice** (`{colors.text-secondary}`): Cream at 82%. The contrast floor — never go lower.
- **Composer Veil** (`{colors.composer-fill}`): Navy at 78%. Senti composer glass only.

**The Six Colors Rule.** No red, orange, yellow, purple, gray, or any color outside these six. Severity is weight, border, inversion, and marker shape.

**The Cyan Is a Line Rule.** Cyan is allowed only for outlines, active borders, focus rings, thin lines, and small highlights. It stays out of the 60/25/15 navy–cream–white balance.

**The Inversion Rule.** Solid cream + navy text is reserved for the highest-priority objects: a critical alert, the most important list item, and primary buttons. The active nav item is a cyan border, not an inverted fill. At most two inverted blocks on a screen.

## Typography

**Display Font:** Poppins (fallback Inter, then system sans-serif)
**Body Font:** Poppins
**Label/Mono Font:** Poppins — no separate mono face. Charts and numerals stay in the same family.

**Character:** A geometric grotesque with enough weight to feel like instrumentation. Medium is the floor. ExtraBold is the alarm.

### Hierarchy
- **Display** (800, 44px, 1.1): Page titles inside the app. Pitch titles clamp from 44px up toward 86px.
- **Headline** (700, 32px, 1.1): Alert and banner titles.
- **Title** (700, 20px, 1.1, 0.12em, uppercase): Card and list item titles.
- **Body** (500, 17px, 1.45): Running copy, form values, table rows. Subtitle is 22px / 600. Tagline is 17px / 500 at secondary cream.
- **Label** (700, 13–14px, 0.12em, uppercase): Section labels, metric labels, table headers, badges. Nav is 18px / 600 (700 active). Buttons are 16px / 700. Metric numerals are 64px / 800 in white.

**The Weight Floor Rule.** Never use a weight below 500 or a size below 13px. Scope Poppins to text so icon fonts do not render as literal words.

## Layout

A 280px sticky sidebar on the left, wordmark 220px wide with 32px clearance from every edge, then a canvas padded 32px and capped at 1600px. Split views give the media column 68% and the secondary panel the rest. Below 1120px the shell stacks and the split becomes one column.

Rhythm is 12 / 24 / 32. Panel padding is 24px. Icon-tile padding (12px) is the micro gap: field labels, card meta, nav item inset. Buttons are 48px tall. Nav items are 52px tall.

The public pitch is a full-viewport snap scroller. The hero is plain navy. Every later slide carries the city plat. Titles may sit on the plat; body copy sits in opaque frames. Authenticated pages and login are plain navy — no streets, no points, no plat on the sidebar.

Page headers name the current section, not the brand: title, one-line subtitle, short tagline. Login centers the white wordmark with 32px below it, then a centered heading and full-width fields.

## Elevation & Depth

The system is flat. There are no drop shadows. Depth is a tonal stack: navy canvas, then an opaque 12% white mix for panels, then a 2px cream stroke at 35%. Hover lifts the mix to 18%. Focus is a 2px cyan outline with a 2px offset. The only glow is the city-plat points, and only there.

Glass and gradient exist in one place: `.senti-composer`. That composer is a 78% navy veil, 16px backdrop blur, 1px cream line, 24px radius, pinned to the bottom of the charcoal assistant panel. An elliptical aurora rises from the bottom edge — glow blue, cyan, a hint of cream — idle at 45% opacity. While Senti is thinking it reaches full strength, drifts 14%, and pulses down to 72%. Reduced motion keeps the idle fan still.

**The Flat Operations Rule.** Surfaces are flat at rest. No shadow on buttons, cards, type, or the sidebar. Glow is a city-plat privilege, not a hover effect.

## Shapes

Gently curved instrument panels (16px). The composer is the one softer radius (24px). Round controls in the composer are true circles. Team photos are circles with a 2px cream ring.

Borders are 2px. Structural lines use cream at 35%. Low-priority chips and low severity use a dashed cream stroke at 60%. Critical and high severity add a 6px cream bar on the left. Detection overlays and zone polygons are 2px white; exclusion zones are dashed white.

The recurring silhouette is the viewfinder: a `+` at each corner of a frame, 14px, cream at line opacity. Those ticks are not the city map.

## Components

### Buttons
- **Shape:** 16px radius, 2px stroke, 48px min height, 24px inline padding, 16px / 700.
- **Primary:** Cream fill, navy text, cream border. Highest-priority action. Hover does not recolor it.
- **Outline:** Transparent, cyan border, cream text. Hover fills the 18% white mix.
- **Focus:** 2px cyan outline, 2px offset.
- **Disabled:** Secondary cream and the structural line. Primary disabled keeps the cream fill.

### Chips
- **Style:** Same height as a button, dashed cream at 60%, secondary cream type, 13px / 700.
- **On:** Solid cyan border, cream text, weight 800. Used for active filters, not as a second primary button.

### Cards / Containers
- **Corner Style:** 16px.
- **Background:** Panel mix. Opaque so the plat never shows through type.
- **Shadow Strategy:** None. See Elevation.
- **Border:** 2px cream at 35%. Camera cards and hoverable frames shift the border to cyan.
- **Internal Padding:** 24px. Corner `+` marks sit 12px in.

### Inputs / Fields
- **Style:** Navy fill, solid cream border, 16px radius, 48px min height. Labels are uppercase section labels above the control.
- **Focus:** Border and ring move to cyan.
- **Error:** A stacked label "Error" plus the message, button weight, no extra color.
- **Placeholder:** Secondary cream.

### Navigation
- **Style:** 280px navy column, 2px cream divider, wordmark on top, list in the middle, org / name / connection / logout pinned to the bottom.
- **Item:** 52px, 18px / 600, transparent border. Hover is the 18% mix. Active is a cyan border and weight 700 — not an inverted fill.
- **Pitch dots:** Hollow cream circles in a fixed right rail. The current slide fills cream.

### Severity
- **Crítico:** Inverted cream, navy type, weight 800, 6px cream left bar, label CRÍTICO.
- **Alta:** Cream outline, 6px cream left bar, weight 800, label ALTA.
- **Media:** 2px cream outline, cream type, label MEDIA.
- **Baja:** Dashed outline at 60%, secondary type, label BAJA.

### Status markers
Shape, not color: ● Nuevo, ◐ En revisión, ○ Resuelto, ○ Falso positivo with a strikethrough label. The connection dot is the one color exception.

### Senti composer
Pinned input at the bottom of the charcoal thread. Navy glass, aurora fan, round icon buttons, site pill. Text stays cream. Confirmation actions use the standard buttons — never a free-floating overlay.

### Charts and overlays
Recharts series in cream or white. Axes and grid in cream at line / grid opacity. Series differ by solid vs dashed stroke. Bounding boxes and zone polygons are white, 2px, bold labels. OpenCV reads the same tokens.

## Do's and Don'ts

### Do:
- **Do** pull every color, size, and weight from `theme/tokens.toml` (or the generated CSS variables).
- **Do** keep cyan as a 2px line: outlines, focus, active nav, plat streets.
- **Do** invert cream for the one or two highest-priority objects on a screen.
- **Do** put body copy, lists, forms, and the assistant thread inside opaque frames.
- **Do** use ● ◐ ○ plus a Spanish label for event status.
- **Do** leave 32px around the wordmark and never tile it on login.
- **Do** honor `prefers-reduced-motion: reduce` — still aurora, no hero loop, instant pitch scroll.

### Don't:
- **Don't** introduce a seventh color, a severity red, or a default shadcn palette.
- **Don't** fill a large surface with cyan, or stroke cyan on cream.
- **Don't** put the city plat inside the app, on login, on the sidebar, or behind unpaneled body copy.
- **Don't** use glass, blur, or a gradient outside `.senti-composer`.
- **Don't** drop-shadow buttons, cards, or type.
- **Don't** recreate, recolor, or redraw the wordmark or the icon mark.
- **Don't** set type below 13px or weight below 500.
- **Don't** invert more than two blocks, or invert the active nav item.
- **Don't** write UI copy in English.

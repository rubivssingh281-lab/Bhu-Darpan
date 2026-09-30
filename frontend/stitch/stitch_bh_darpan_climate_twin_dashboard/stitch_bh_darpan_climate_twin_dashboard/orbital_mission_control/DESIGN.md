---
name: Orbital Mission Control
colors:
  surface: '#051424'
  surface-dim: '#051424'
  surface-bright: '#2c3a4c'
  surface-container-lowest: '#010f1f'
  surface-container-low: '#0d1c2d'
  surface-container: '#122131'
  surface-container-high: '#1c2b3c'
  surface-container-highest: '#273647'
  on-surface: '#d4e4fa'
  on-surface-variant: '#bacac5'
  inverse-surface: '#d4e4fa'
  inverse-on-surface: '#233143'
  outline: '#859490'
  outline-variant: '#3c4a46'
  surface-tint: '#3cddc7'
  primary: '#57f1db'
  on-primary: '#003731'
  primary-container: '#2dd4bf'
  on-primary-container: '#00574d'
  inverse-primary: '#006b5f'
  secondary: '#ffb780'
  on-secondary: '#4e2600'
  secondary-container: '#763c00'
  on-secondary-container: '#fca967'
  tertiary: '#ffcfc3'
  on-tertiary: '#5d1805'
  tertiary-container: '#ffa891'
  on-tertiary-container: '#83331e'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#62fae3'
  primary-fixed-dim: '#3cddc7'
  on-primary-fixed: '#00201c'
  on-primary-fixed-variant: '#005047'
  secondary-fixed: '#ffdcc4'
  secondary-fixed-dim: '#ffb780'
  on-secondary-fixed: '#2f1400'
  on-secondary-fixed-variant: '#6f3800'
  tertiary-fixed: '#ffdbd2'
  tertiary-fixed-dim: '#ffb4a1'
  on-tertiary-fixed: '#3c0800'
  on-tertiary-fixed-variant: '#7c2e19'
  background: '#051424'
  on-background: '#d4e4fa'
  surface-variant: '#273647'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.03em
  display-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '500'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  telemetry-xl:
    fontFamily: JetBrains Mono
    fontSize: 28px
    fontWeight: '500'
    lineHeight: 36px
    letterSpacing: -0.01em
  telemetry-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  telemetry-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.02em
  telemetry-micro:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-lg: 1.5rem
  margin: 1rem
  margin-md: 1.5rem
  margin-lg: 2rem
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-base: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style

This design system embodies the calculated precision, technological majesty, and operational calm of an advanced planetary observatory. Designed for an AI-powered ecological and meteorological digital twin of the subcontinent, the aesthetic balances high-density Earth observation telemetry with serene, distraction-free spatial intelligence.

The target audience encompasses climate scientists, disaster response commanders, aerospace researchers, and policy strategists. The interface evokes rigorous scientific authority, situational clarity under crisis, and the vast perspective of orbital telemetry.

The visual style merges **Mission-Control Brutalism** with **Atmospheric Glassmorphism**:
- Obsidian, void-level dark field surfaces to maximize telemetry readability.
- Hairline structural grids, coordinates, and precision optical markers referencing geostationary sensor arrays.
- Subtle topographic isobars and cartographic reticles layered under translucent telemetry glass.
- High-contrast precision accents that illuminate critical climate anomalies without visual fatigue.

## Colors

The color architecture is optimized for low-light command center environments, focusing on deep absorption and spectral signal emission:

- **Void Background (`#070B10`)**: The foundational canvas, providing maximum dynamic range for spatial data layers and high-resolution Earth imagery.
- **Tonal Tiers (`#0C1218`, `#131B24`)**: Functional elevations for docking telemetry modules, sidebar inspectors, and floating map cards.
- **Precision Teal (`#2DD4BF`)**: The primary vector. Applied to target reticles, orbital vector paths, confirmed active modes, and focal charts.
- **Environmental Alert Matrix**:
  - `Nominal Emerald (#10B981)`: Stable ecological vitals, nominal monsoonal progression, and standard aerosol indices.
  - `Ochre / Amber (#F4A261)`: Moderate deviations, reservoir depletion risks, and heatwave watches.
  - `Terracotta (#E07A5F)` & `Alert Crimson (#EF4444)`: Cyclone track warnings, extreme cloudburst anomalies, and immediate containment thresholds.
- **Typography Neutrals (`#F8FAFC`, `#94A3B8`, `#64748B`)**: Strict hierarchy minimizing optical glare while preserving immediate legibility down to 10px metadata readouts.

## Typography

The typographical structure enforces a strict division of purpose across three specialized type families:

1. **Strategic Titles (`Space Grotesk`)**: Utilized for system titles, sector names, operational headers, and dashboard summaries. Its technical geometric construction provides an advanced aerospace identity.
2. **Operational Prose (`Inter`)**: Deployed for narrative reports, anomaly briefing synopses, procedural checklists, and administrative settings. Engineered for neutral, high-density legibility.
3. **Telemetry & Sensor Data (`JetBrains Mono`)**: Mandatory for all coordinates (lat/long), timestamps (UTC/IST), spectral wavelengths, pressure bars, velocity matrices, and tabular status monitors. Tabular figures prevent layout shifts during live incoming telemetry streams.

All uppercase telemetry labels (`telemetry-micro`) must incorporate positive letter spacing (+0.05em) to guarantee scan-rate fidelity on high-resolution command displays.

## Layout & Spacing

The layout is built upon an 8px base grid, dynamically compressed to a 4px sub-grid for compact, information-dense telemetry modules.

- **Grid System**: A 12-column fluid grid system across desktop views with fixed 320px or 380px contextual HUD toolbars (left telemetry dock, right scenario simulation pane).
- **Responsive Adaptations**:
  - **Desktop (1440px+)**: Multi-viewport layout with full interactive cartographic engine background, overlaid with persistent heads-up diagnostic floating docks.
  - **Tablet (768px - 1439px)**: Toolbars collapse into drawer-anchored glass sheets; telemetry feeds aggregate into tabbed panels.
  - **Mobile (< 768px)**: Single-column priority view with bottom-sheet mission controls, prioritizing primary visual heatmaps and emergency threshold alerts.
- **Rhythm**: Internal card padding uses strictly `space-base` (16px) or `space-md` (12px) to maximize real-estate efficiency for scientific plots and multidimensional geospatial arrays.

## Elevation & Depth

Visual hierarchy does not use diffuse paper shadows; instead, it relies on **Atmospheric Translucency, Tonal Layering, and Emission Glows**:

- **Ground Zero (Canvas)**: `#070B10` void with optional low-opacity (4%) topographic SVG contours and vector grid lines.
- **Tier 1 (Panels & Docks)**: `#0C1218` with a 1px perimeter border of `#1F2E3D`.
- **Tier 2 (Floating Floating Cards & Inspect Overlays)**: `rgba(19, 27, 36, 0.85)` with `backdrop-filter: blur(16px)` and a directional top-hairline highlight of `rgba(45, 212, 191, 0.25)`.
- **Tier 3 (Active Interactivity & Alerts)**: Elements project localized, monochromatic photonic flares:
  - Nominal: `0 0 16px rgba(45, 212, 191, 0.15)`
  - Anomaly Warning: `0 0 16px rgba(244, 162, 97, 0.2)`
  - Critical Alert: `0 0 20px rgba(239, 68, 68, 0.3)`

## Shapes

The design system standardizes on a refined, engineering-grade curvature that avoids both blunt brutalism and overly casual consumer bubbles:

- **Cards & Data Panels**: 12px border-radius (`rounded-lg`), delivering a sleek, high-precision electronic equipment frame.
- **Inspect Tooltips & Flyouts**: 8px border-radius (`rounded-md`).
- **Telemetry Readout Capsules & Sensor Badges**: 4px border-radius for micro technical tags, or full pill radius for operational status indicators.
- **Hairline Precision**: Card edges and visual dividers use a crisp 1px solid stroke (`#1F2E3D` or `border-accent`), emulating laboratory-grade hardware displays.

## Components

### Buttons
- **Primary Telemetry Button**: Background `#2DD4BF`, text `#070B10`, font `Space Grotesk` (Medium 14px), 8px radius. Active state triggers a subtle teal glow (`0 0 12px rgba(45, 212, 191, 0.4)`).
- **Secondary Ghost / Border Button**: Background `rgba(19, 27, 36, 0.6)`, 1px border `#1F2E3D`, text `#F8FAFC`. On hover, border color transitions to `#2DD4BF` with text tint.
- **Terminal Action Button**: Monospaced `JetBrains Mono` 12px with square-bracket bounding indicators (e.g., `[ EXECUTE_SIMULATION ]`).

### Status Pills & Live Beacon Indicators
- Encapsulated pills featuring a live circular beacon (`8px`).
- The beacon contains a central illuminated dot with a concentric CSS pulse ring:
  - **Live Orbital Feed**: Teal `#2DD4BF` with soft outward breathing loop (2.4s period).
  - **Extreme Flash Flood / Cyclone Warning**: Crimson `#EF4444` with rapid flash cycle (1.0s period).

### Telemetry Readout Cards
- Sleek 12px-14px rounded panels featuring a 1px border (`#1F2E3D`).
- Card Header: `telemetry-micro` capitalized metric tag in `#64748B` accompanied by a hex coordinate icon.
- Card Metric: Big numeric value in `JetBrains Mono` (`telemetry-xl`) rendered in `#F8FAFC` alongside unit symbols rendered in `#2DD4BF`.
- Footer: Mini sparkline or isobar SVG gradient showing 24-hour predictive trajectory.

### Inputs & Sensor Sliders
- Background: `#0C1218`, border: 1px `#1F2E3D`, text: `#F8FAFC`. Focus ring: 1px `#2DD4BF` with a 2px outer aura `rgba(45, 212, 191, 0.2)`.
- Temporal & Simulation Sliders: Hairline track (`2px`, `#1F2E3D`) with a glowing circular scrubber thumb (`#2DD4BF`) displaying a live floating timestamp tag in `JetBrains Mono`.

### High-Density Charts & Isobar Overlays
- Background: Minimalist semi-translucent dark slate.
- Grid Lines: Subtle horizontal/vertical rules (`rgba(255, 255, 255, 0.04)`).
- Data Paths: 1.5px anti-aliased vector paths with dual-tone fills (e.g., gradient fill from `rgba(45, 212, 191, 0.25)` to transparent).
- Crosshairs: Hairline dashed reticle tracking cursor position with attached floating coordinates label.
# Bhu Darpan (भू दर्पण) — Frontend

A static, multi-page frontend for **Bhu Darpan**, a digital-twin dashboard for India's
climate — modelled on the 9-screen product brief (landing page + 8 dashboard views).

## Tech stack

| Layer          | Choice                                   | Why |
|----------------|-------------------------------------------|-----|
| Markup         | Plain HTML5, 9 static pages                | No build step required; open any file directly in a browser or drop the folder on any static host (Netlify, GitHub Pages, S3, nginx). |
| Styling        | Plain CSS3, split into 6 files             | No Sass/Tailwind build pipeline needed, but the files are organised the way a preprocessor project would be (tokens → base → layout → components → animations → page-specific), so it's easy to migrate later. |
| Typography     | Google Fonts: **Space Grotesk** (display), **Inter** (UI/body), **IBM Plex Mono** (data/numbers) | Gives the dashboard a technical, instrument-panel feel and makes every number on the page read distinctly from prose. |
| Charts         | **Chart.js 4** via CDN                     | Small, dependency-free, easy to theme for dark mode; used on Forecast, Historical, What-if and Reports pages. |
| Icons          | Hand-written inline SVG (no icon font/library) | Zero extra requests, fully themeable via `currentColor`, crisp at any size. |
| Interactivity  | Vanilla JavaScript (ES5+), no framework     | The UI logic here (nav state, sliders, count-up numbers, scroll reveals) doesn't need React/Vue; keeping it framework-free keeps the deliverable copy-paste simple for any backend you plug in later. |
| Map / geo art  | Hand-built low-poly SVG silhouette of India | Decorative/illustrative, not a georeferenced map — swap for a real topoJSON/Leaflet/Mapbox layer when you wire up live geodata. |

No package manager, bundler or build step is required — every page is self-contained
HTML that pulls in the shared CSS/JS files with plain `<link>`/`<script>` tags.

## Folder structure

```
bhu-darpan/
├── index.html            Landing page (hero, mesh visual, module rail)
├── dashboard.html         India overview (stat cards, layer map, alerts)
├── live-climate.html      Pilot-region drill-down (Jammu & Kashmir)
├── forecast.html          14-day rainfall & temperature outlook (charts)
├── whatif.html            What-if scenario simulator (interactive)
├── sectoral.html          Sectoral impact grid + risk map
├── historical.html        Historical trends (10-year chart + stats)
├── explorer.html          Data explorer (dataset/variable query UI)
├── reports.html           Alerts feed + custom report builder
├── css/
│   ├── variables.css      Design tokens: color, type scale, spacing, shadows
│   ├── base.css           Reset, base typography, focus states, scrollbars
│   ├── layout.css         App shell: sidebar, topbar, content grid, responsive
│   ├── components.css     Cards, buttons, badges, alerts, forms, tables
│   ├── animations.css     Keyframes, used sparingly and deliberately
│   └── landing.css        Landing-page-only styles (hero, mesh, footer)
└── js/
    ├── nav.js             Active-link state, mobile sidebar toggle, live clock, count-up numbers
    ├── charts.js           Chart.js theme + builder functions per page
    ├── whatif.js          What-if slider logic + simulated impact output
    └── landing.js         Scroll reveals + mesh node tooltips (landing page only)
```

Each HTML file is independent — there's no templating engine, so the sidebar/topbar
markup is repeated per page. If you move this into a real framework (Next.js, Vue,
Django templates, etc.), lift that markup into a single `<Sidebar />` / `<Topbar />`
component; everything else (the CSS files, the JS modules) ports over unchanged.

## Design notes

- **Palette**: deep space navy background with a monsoon-teal accent for
  data/signal, and a restrained saffron accent for highlights — a deliberate,
  light nod to the subject rather than a decorative wash.
- **Data typography**: every measured number (temperatures, percentages, table
  figures) is set in IBM Plex Mono so it reads as an instrument readout rather
  than marketing copy.
- **Motion is restrained**: a hero mesh sweep, one page-load reveal sequence,
  hover/focus states, and a live "pulse" dot — no scroll-triggered animation on
  every card. `prefers-reduced-motion` is respected globally.
- **Data shown is illustrative**, not live — every page carries a small note or
  clearly-labelled placeholder wherever a real feed (INSAT-3D, IMD, ERA5, etc.)
  would eventually connect.

## Running it

No install needed:

```bash
# from inside the bhu-darpan/ folder
python3 -m http.server 8000
# then open http://localhost:8000
```

Or just double-click `index.html` — the only pages that need a server (rather
than `file://`) are ones fetching an external font/CDN script, which all work
fine offline too except the Google Fonts and Chart.js CDN calls.

## Where to plug in real data

- `js/charts.js` — replace the hard-coded arrays in each `build*Chart()`
  function with a `fetch()` call to your API.
- `js/whatif.js` — replace the `COEFFICIENTS` table with a call to your actual
  simulation/model endpoint; the DOM update logic (`paintOutputs`,
  `updateImpactChart`) stays the same.
- The inline SVG "maps" (India silhouette, J&K district dots) are placeholders
  for a real geodata layer — swap for Leaflet, Mapbox GL, or ISRO Bhuvan's map
  API once you have tile/vector endpoints to point at.

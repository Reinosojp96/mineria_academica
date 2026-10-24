---
name: Atelier Académique
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#404847'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#707977'
  outline-variant: '#bfc8c6'
  surface-tint: '#316763'
  primary: '#003633'
  on-primary: '#ffffff'
  primary-container: '#134e4a'
  on-primary-container: '#87beb8'
  inverse-primary: '#9ad1cb'
  secondary: '#006a63'
  on-secondary: '#ffffff'
  secondary-container: '#99efe5'
  on-secondary-container: '#006f67'
  tertiary: '#003350'
  on-tertiary: '#ffffff'
  tertiary-container: '#004a72'
  on-tertiary-container: '#64bbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b5ede7'
  primary-fixed-dim: '#9ad1cb'
  on-primary-fixed: '#00201e'
  on-primary-fixed-variant: '#144f4b'
  secondary-fixed: '#9cf2e8'
  secondary-fixed-dim: '#80d5cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#00504a'
  tertiary-fixed: '#cce5ff'
  tertiary-fixed-dim: '#93ccff'
  on-tertiary-fixed: '#001d31'
  on-tertiary-fixed-variant: '#004b73'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  display-lg:
    fontFamily: Newsreader
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Newsreader
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Newsreader
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Newsreader
    fontSize: 22px
    fontWeight: '500'
    lineHeight: 28px
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Newsreader
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-desktop: 1.5rem
  margin: 1rem
  margin-desktop: 2rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system is engineered for dense academic mining, scientific document synthesis, and investigative archival analysis. The aesthetic fuses the discipline of classic peer-reviewed publishing with the precision of high-throughput data science laboratories. 

### Design Philosophy & Aesthetic Movement
- **Movement:** Technical Editorial Minimalist. It draws from archival typography, Swiss modernist grid discipline, and specialized laboratory instrument interfaces.
- **Tone:** Authoritative, clinical, focused, and scannable. It eliminates ornamental distraction to prioritize reading endurance, structural density, and cross-reference velocity.
- **Emotional Response:** Induces cognitive calm, intellectual rigor, and trust in programmatic extraction accuracy. The interface behaves like calibrated analytical glassware: transparent, exact, and structurally robust under high data pressure.

## Colors

The palette is anchored in archival paper substrates and deep petroleum inks. It rejects low-contrast decorative tints in favor of strict legibility ratios exceeding WCAG AAA standards for document examination.

### Palette Architecture
- **Primary Deep Petroleum (`#134E4A`)**: Used for primary brand markers, active navigation structures, and high-priority action targets.
- **Secondary Teal Accent (`#0F766E`)**: Highlights active query filters, selected metadata facets, and confirmed algorithmic associations.
- **Tertiary Cyan/Blue (`#0284C7`)**: Reserved strictly for interactive semantic cross-references, citation hyperlinking, and data-mining graph links.
- **Neutral Dark Ink (`#0F172A`)**: The primary ink token. Body text, table data, and primary values are rendered in this color to prevent retinal fatigue caused by low-contrast gray type.
- **Neutral Secondary Ink (`#1E293B`)**: Applied exclusively to subheadings, column headers, and structural metadata. Never drops below 7:1 contrast on paper backings.
- **Canvas & Substrates**: Crisp technical white (`#FFFFFF`) for research panels and document readers; sterile archival paper (`#F8FAFC`) for base canvas backgrounds.
- **Rule Lines & Divisors**: Structural dividers use crisp slate borders (`#CBD5E1`) for internal partitions and defined boundaries (`#94A3B8`) for active framing.
- **Analytical Semantic States**:
  - Positive/Indexed: Deep Emerald (`#15803D`)
  - Extraction Error/Conflict: Crimson Oxide (`#B91C1C`)
  - Running Extraction/Pending Process: Raw Amber (`#B45309`)

## Typography

The type system is divided across three distinct functional categories:
1. **Academic Authority (`Newsreader`)**: Applied to high-level system views, document titles, synthesized abstracts, and continuous reading panes. Its serif construction facilitates prolonged sustained reading without cognitive exhaustion.
2. **Operational Ergonomics (`Inter`)**: Governs high-density UI interactions, tabular rows, filters, forms, and command structures. Highly legible at microscopic scales.
3. **Analytical Metrics (`JetBrains Mono`)**: Powers confidence scores, BibTeX keys, DOI markers, regex queries, and timestamp telemetry.

### Rules & Formatting
- **Zero Faint Ink**: Gray text lighter than `#475569` is disallowed on light surfaces. Secondary metadata leverages scale reductions and monospace styles instead of opacity fading.
- **Tabular Numerals**: Numeric displays within tables and metrics must always activate `font-variant-numeric: tabular-nums` to maintain vertical alignment across thousands of document rows.

## Layout & Spacing

This design system uses a technical fluid grid optimized for dual- and triple-pane split layouts (e.g., Document Corpus List | Document Viewer | Extraction Inspector).

### Grid & Breakpoints
- **Compact Viewports (<768px)**: 4-column layout with `margin: 1rem` and `gutter: 1rem`. Panels collapse into sequential contextual tabs (Corpus -> Reading -> Data).
- **Tablet & Medium Displays (768px - 1199px)**: 8-column layout. Document tree splits into a collapsable split view with fixed filter shelves.
- **Desktop Workstations (≥1200px)**: 12-column fixed-margin layout with `margin-desktop: 2rem` and `gutter-desktop: 1.5rem`. Enables multi-column split exploration: Facets (250px fixed), Document Workspace (Fluid), and Metadata Graph/Inspector (380px fixed).

### Rhythm & Alignment
Spacing follows strict multi-unit structural steps (`0.25rem`, `0.5rem`, `0.75rem`, `1.25rem`, `2rem`) to maximize visual packing without clutter. Dividers line up precisely with typographical baselines to establish a clinical laboratory notebook feel.

## Elevation & Depth

To simulate physical print research and high-precision instruments, visual stratification relies on structural framing and subtle tonal layering rather than aggressive drop shadows.

### Depth Mechanics
- **Low-Contrast Outlines**: Panels, data tables, and cards prioritize distinct single-pixel rules (`#CBD5E1`) over drop shadows. Borders delineate distinct computational zones.
- **Substrate Tiers**:
  - `Level 0 (Canvas)`: `#F8FAFC` base application background.
  - `Level 1 (Panels & Sheets)`: Pure `#FFFFFF` resting directly on the canvas, bounded by a 1px `#CBD5E1` outline.
  - `Level 2 (Active Inspection & Hover)`: White surfaces with a targeted micro-shadow: `0 1px 3px 0 rgba(15, 23, 42, 0.08), 0 1px 2px -1px rgba(15, 23, 42, 0.08)`.
  - `Level 3 (Modal Extraction / Overlays)`: Pure `#FFFFFF` enclosed with `#94A3B8`, underpinned by a soft, diffused structural shadow: `0 10px 15px -3px rgba(15, 23, 42, 0.12), 0 4px 6px -4px rgba(15, 23, 42, 0.08)`.
- **Print Optimization**: All shadow tokens must resolve to `none` under `@media print`, replacing all elevation with explicit `1px solid #000000` borders.

## Shapes

The design system implements a controlled, soft corner geometry (`roundedness: 1`). 

### Spatial Radii Rules
- **Base Elements (Buttons, Inputs, Badges, Table Rows)**: `0.25rem` (4px). Provides a disciplined, technical silhouette without aggressive brutalism.
- **Surface Containers (Document Panels, Extraction Modals, Code Blocks)**: `0.5rem` (8px). Maintains structure for data containment.
- **Pill Exceptions**: Micro status indicators and count chips can utilize full-radius pills (`9999px`) to create clear morphological contrast against rectangular document blocks.

## Components

### Buttons
- **Primary**: Solid background `#134E4A`, text `#FFFFFF`, border `1px solid #134E4A`. Hover: `#0F766E`. Active: `#115E59`. Focus: ring `2px solid #0F766E` offset by 2px white space.
- **Secondary / Outline**: Surface `#FFFFFF`, text `#0F172A`, border `1px solid #CBD5E1`. Hover: background `#F8FAFC`, border `#94A3B8`.
- **Tertiary / Utility**: Ghost surface, text `#0F766E`, zero border. Hover: `#F1F5F9`.
- **Metrics/Action Compact**: Min-height 28px, monospace label typography (`label-md`), padding `0.25rem 0.5rem`.

### Chips & Metadata Tags
- **Taxonomy Badge**: `#F1F5F9` background, `#1E293B` text, `1px solid #CBD5E1`. Monospace font for indexation codes.
- **Status Chips**:
  - Validated/Extracted: `#DCFCE7` background, `#15803D` text, `#86EFAC` border.
  - Conflict/Missing: `#FEE2E2` background, `#B91C1C` text, `#FCA5A5` border.
  - Queued/Parsing: `#FEF3C7` background, `#B45309` text, `#FCD34D` border.

### Input Fields & Search Bars
- **Search & Regex Inputs**: Background `#FFFFFF`, border `1px solid #CBD5E1`, text `#0F172A`. Inset left icon for query mode (Boolean, Vector, Regex).
- **Focus State**: Border `#0F766E`, box-shadow `0 0 0 1px #0F766E`.
- **Error State**: Border `#B91C1C`, box-shadow `0 0 0 1px #B91C1C`.

### Form Controls (Checkboxes & Radios)
- **Checkboxes**: 16x16px square with 2px radius. Border `1.5px solid #94A3B8`. Checked state: `#134E4A` fill with a crisp white check vector mark.
- **Radio Buttons**: 16x16px circle. Border `1.5px solid #94A3B8`. Selected state: `#134E4A` border with an internal solid 6px `#134E4A` core.

### Cards & Data Panels
- Surface `#FFFFFF`, border `1px solid #CBD5E1`, border-radius `0.5rem`.
- Padding transitions: Header sections use `space-md` with an internal bottom border (`1px solid #E2E8F0`). Body elements use `space-lg`.

### Analytical Data Tables
- **Table Headers (`th`)**: Background `#F8FAFC`, text `#1E293B`, `font-family: JetBrains Mono`, uppercase 11px, letter-spacing 0.05em, border-bottom `2px solid #CBD5E1`.
- **Table Cells (`td`)**: Text `#0F172A`, border-bottom `1px solid #E2E8F0`, padding `0.5rem 0.75rem`. Tabular figures enabled by default.
- **Row States**: Alternating row stripes are prohibited; hover state applies `#F1F5F9`. Selected row activates `#F0FDFA` background with a left accent border of `3px solid #0F766E`.

### Domain-Specific Components
- **BibTeX / Citation Excerpt Box**: Border-left `3px solid #134E4A`, background `#F8FAFC`, monospace text with syntax highlighting for authors, DOIs, and publication years.
- **Document Chunk Inspector**: Highlighting layer using transparent yellow-green tints (`rgba(20, 184, 166, 0.15)`) for matched semantic spans, linked to analytical sidebar annotations with corresponding match confidence percentages.
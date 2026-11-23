---
name: Círculo
description: Calm Spanish workspace for local account review and execution controls.
colors:
  ink: "#24352a"
  muted: "#657268"
  line: "#e2e6de"
  green: "#2d523b"
  lime: "#e0ecb9"
  paper: "#fff"
  work-surface: "#f7f8f4"
  forest-rail: "#24392c"
  rail-text: "#f4f7ed"
  rail-muted: "#c3cec1"
  rail-hover: "#304937"
  rail-active: "#3d5239"
  rail-active-text: "#e3efb5"
  primary-text: "#fbfff7"
  primary-hover: "#1c3d29"
  focus: "#73954f"
  import-surface: "#eef2e7"
  import-border: "#bac9ae"
  selection-surface: "#edf3e4"
  selection-bar: "#edf2e6"
  selected-count: "#dce7ca"
  field-border: "#dce2d4"
  secondary-border: "#d9dfd4"
  secondary-hover: "#f0f4e8"
  relationship-unreturned: "#7c603b"
  relationship-mutual: "#52794c"
  relationship-unknown: "#6b7866"
  protected-surface: "#e2ebd5"
  protected-ink: "#4c6c36"
  example-surface: "#f1eddb"
  example-border: "#ded5b3"
  example-ink: "#74643b"
  error-surface: "#f5eae2"
  error-border: "#dec3ae"
  error-ink: "#7a4831"
  pause-surface: "#e7dfc4"
  pause-ink: "#665329"
  live-action: "#765437"
typography:
  headline:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "31px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-.035em"
  title:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "16px"
    fontWeight: 700
    letterSpacing: "-.025em"
  body:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "12px"
    lineHeight: 1.8
  account:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "12px"
    fontWeight: 650
  label:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "11px"
    fontWeight: 650
  button:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "12px"
    fontWeight: 650
  metric:
    fontFamily: "'Manrope Variable', sans-serif"
    fontSize: "24px"
    fontWeight: 600
    letterSpacing: "-.03em"
rounded:
  count: "4px"
  field: "6px"
  control: "7px"
  navigation: "8px"
  import: "10px"
  panel: "12px"
  dialog: "14px"
  circle: "50%"
spacing:
  icon-gap: "8px"
  field-gap: "12px"
  compact-panel: "18px"
  panel: "20px"
  section: "24px"
  workspace: "28px"
  page-top: "36px"
  page-inline: "42px"
components:
  button-primary:
    backgroundColor: "{colors.green}"
    textColor: "{colors.primary-text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "10px 15px"
  button-secondary-hover:
    backgroundColor: "{colors.secondary-hover}"
  button-live:
    backgroundColor: "{colors.live-action}"
    textColor: "{colors.primary-text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "10px"
  navigation-active:
    backgroundColor: "{colors.rail-active}"
    textColor: "{colors.rail-active-text}"
    rounded: "{rounded.navigation}"
    padding: "13px 12px"
  runner-panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "23px 20px 20px"
    width: "285px"
  example-banner:
    backgroundColor: "{colors.example-surface}"
    textColor: "{colors.example-ink}"
    rounded: "{rounded.field}"
    padding: "9px 11px"
  row-selected:
    backgroundColor: "{colors.selection-surface}"
  confirmation-dialog:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.dialog}"
    padding: "32px"
    width: "460px"
---

# Design System: Círculo

## Overview

**Creative North Star: "Un espacio local y tranquilo"**

Círculo uses a calm, practical workspace for reviewing accounts and controlling a local runner. A forest rail anchors the interface; a warm off-white work surface, pale olive selections, and compact Manrope typography keep long lists legible. This describes the accepted implementation, not an approved brand identity: the product name remains provisional.

The visual emphasis follows the task: import and filter in the central work area, read account relationships in a semantic table, and review execution settings in the adjacent panel. Spanish labels, visible keyboard focus, labeled example data, and an explicit real-action confirmation keep the interface understandable.

The north-star phrase is a descriptive label for the implemented direction, not a newly approved brand concept. Evidence: `web/style.css`, `web/App.tsx`, the local product brief, and the reviewed desktop and mobile screenshots. Tokens describe the final stylesheet cascade, including the accessibility overrides at its end.

**Key Characteristics:**

- Forest navigation and warm off-white surfaces.
- Compact, readable account rows with textual relationship states.
- Pale olive selection and protection treatments.
- Flat borders at rest; depth reserved for the confirmation dialog.
- Responsive stacking and visible keyboard focus.

## Colors

The palette combines forest and olive greens with warm, quiet neutrals. Frontmatter values are normative; the names below explain their application.

### Primary

- **Forest action green** (`green`): simulation and inspection actions, native control accents, and caret color.
- **Forest rail** (`forest-rail`): persistent desktop navigation and the compact mobile navigation bar.
- **Pale lime** (`lime`): brand mark and small rail indicators.
- **Olive selection** (`selection-surface`, `selection-bar`, `selected-count`): selected account rows and the persistent selection summary.
- **Rail olive** (`rail-active`, `rail-active-text`): current navigation item.
- **Focus olive** (`focus`): explicit keyboard focus outline.

### Secondary

- **Muted amber** (`relationship-unreturned`, `example-ink`, `example-surface`): unreturned relationship text and the synthetic-data banner.
- **Warm earth** (`live-action`, `pause-surface`, `pause-ink`): distinguish live execution and pausing from the normal green action.
- **Clay feedback** (`error-surface`, `error-border`, `error-ink`): failures, unavailable runner, and required review.

### Neutral

- **Warm work surface** (`work-surface`): main canvas.
- **White paper** (`paper`): runner panel, inputs, secondary buttons, and dialog.
- **Forest ink** (`ink`): principal text; **muted leaf** (`muted`): supporting copy.
- **Quiet line** (`line`): divisions between navigation, sections, table, and footer.
- **Field stroke** (`field-border`): ordinary controls. The import target uses its own dashed olive stroke.

**The Readable State Rule.** Selection, relationship, protection, example data, and execution mode each retain an explicit text or control state; color supports their meaning.

## Typography

**Display and body font:** Manrope Variable, with sans-serif fallback. It is loaded locally through `@fontsource-variable/manrope` in the frontend entry point. There is no separate display face or icon font.

The variable sans gives the compact interface a soft, practical character. Headings use modest negative tracking; account names and controls remain direct and readable. Main metrics, time values, and numeric limits use tabular numerals.

### Hierarchy

- **Headline:** medium emphasis (650), baseline page heading (31px), line height (1.3), tracking (-.035em). It becomes (35px) on wide screens, (27px) in the intermediate desktop range, (29px) below the workspace-stack breakpoint, and (28px) on phones.
- **Title:** connections heading (16px, 700); runner title (15px, 700), growing to (17px) on phones.
- **Body:** page support (12px, line height 1.8); runner descriptions (11px). Guide prose is (12px, line height 2), growing to (13px) on phones and limited to (70ch).
- **Account:** usernames (12px, 650), secondary platform labels (10px), relationship text (11px). On phones relationships are (12px) and may wrap.
- **Label and controls:** ordinary field labels (11px, 650), standard buttons (12px, 650), small buttons (11px); phone controls and field labels use (12px).
- **Metrics:** (24px, 600) with tracking (-.03em). Table headers use (10px, 600).

Do not infer a modular type scale: the implementation uses role-specific sizes. Later CSS overrides supersede the smaller values in the initial responsive blocks.

## Layout

The desktop shell is a fixed forest navigation rail (230px) plus the main work surface. The top bar is (76px) high. Main content has horizontal padding (42px), top padding (36px), and a maximum width (1680px). The work area and runner form a grid: flexible central column plus runner (285px), separated by (28px).

The central sequence is platform tabs, dashed import target, optional example banner, connection heading and metrics, search and filter, semantic account table, pagination, and selection summary. The runner groups identity/session, mode, limits, timing, selection summary, primary action, and status using thin dividers.

- **Wide, at least 1500px:** runner (305px), workspace gap (36px), main top padding (43px), table rows (68px).
- **At most 1200px:** rail (196px), main inline padding (28px), workspace gap (20px). In the 1001–1200px range, the final override sets runner width (270px), hides avatars, and uses account names (11px).
- **At most 1000px:** rail (178px), workspace becomes one column, runner moves below the table. Runner internals use a two-column grid.
- **At most 650px:** rail becomes a static horizontal header with icon navigation; main margin resets and padding becomes (26px 18px 0). The runner returns to block flow. Search occupies a full row, the filter aligns below it, selection controls wrap, avatars are hidden, account rows grow to (72px), and primary form buttons are at least (41px) high.

Spacing is local and task-led rather than a universal strict grid. Repeated gaps and paddings are recorded in frontmatter.

## Elevation & Depth

Everyday surfaces are flat. Background tone and thin strokes provide grouping; selected rows receive a pale fill. The only cast shadow belongs to the confirmation dialog.

### Shadow Vocabulary

- **Confirmation:** `0 18px 70px #10251924`, beneath the centered confirmation surface.
- **Backdrop:** `#14251e66`, a fixed overlay that dims the workspace without blur.

**The Quiet Surface Rule.** Use tonal fills and thin borders for everyday grouping; reserve a cast shadow for the confirmation dialog.

State motion is restrained: button background (180ms ease), import background (200ms), table-row background (150ms), status reveal (350ms, cubic-bezier(.16,1,.3,1)), and loading spin (1.2s linear). Reduced-motion preferences disable animation and transitions.

## Shapes

Gently rounded rectangles define controls, grouping, and navigation. Inputs use corners (6px), buttons (7px), navigation and selection summary (8px), import target (10px), runner (12px), and dialog (14px). Tiny counts use (4px); avatars, status dots, and the broken-circle mark are circular. Thin solid strokes distinguish ordinary fields; the import target alone uses a dashed border.

## Components

### Buttons

Standard buttons are compact inline-flex controls with icon gap (8px), padding (10px 15px), and minimum height (40px). Primary green buttons use near-white text and a darker hover. Secondary white buttons have a quiet outline and pale hover. The runner action is full width (41px minimum height). Real execution uses warm earth. Disabled controls reduce opacity to (.45) and retain a not-allowed cursor. All keyboard-operable controls retain the global focus outline.

### Inputs / Fields

White fields use thin olive-gray strokes and curved corners. Search is an icon-plus-input wrapper, capped at (270px) on desktop; its input itself has no border. Search and account wrappers receive a focus-within ring (3px) with offset (3px); other controls receive the same focus-visible outline. Mode and relationship filters use native select semantics; mode keeps its visible label. Limits remain visibly labeled numeric inputs.

### Navigation

Desktop navigation uses a fixed dark rail with muted text, icon-and-label rows, and olive active fill. Active text, count, and activity dot remain distinct. On phones the rail becomes a horizontal header and navigation labels visually collapse to icons; accessible names remain supplied by the controls. Platform tabs use a thin active underline; TikTok and Facebook retain their beta markers.

### Cards / Containers

The runner is a white, thin-bordered panel without shadow. The import container is pale olive with a dashed border and a stronger drag-over fill. The example banner uses muted amber, explicit Spanish synthetic-data copy, and an exit control. Selection count and export action sit together in a pale summary container.

### Account Table

Keep the actual table structure with headers for selection, account, relationship, and protection. Account links show username, platform, and optional initials avatar. Hover gives a pale green fill; selected rows use the selection token. Relationship dots accompany text, never replacing it. Protection is a toggle with pressed semantics and a filled green shield treatment. Native checkboxes use the green accent. Pagination and visible-range copy sit below the table.

### Feedback and Activity

Inline notices use icon, text, and a close button; failures use clay feedback. A live-status block includes phase, processed count, optional native progress, and explanatory text. Activity uses textual queue states and a timestamped event log on a pale surface. Empty states use restrained outline icons, a short heading, and an actionable next step.

### Confirmation Dialog

The real-action dialog is centered, white, at most (460px) wide, and padded (32px), reducing to (26px) on phones. It identifies the account and quantity, asks for the username, and presents cancel and execute actions. It has dialog semantics, focus containment, Escape handling, and focus restoration in the implementation. Its shadow and dim backdrop provide the only substantial elevation.

## Do's and Don'ts

### Do:

- Do keep Manrope Variable throughout the interface and preserve the later readability overrides in the stylesheet.
- Do distinguish selection, protection, relationship, example data, and execution mode with text as well as visual state.
- Do retain the forest rail, warm work surface, pale olive selection, and white runner panel.
- Do preserve semantic table structure, labeled controls, visible focus, and the real-action confirmation.
- Do stack the workspace and runner at the established breakpoints.

### Don't:

- Don't turn the application into a marketing layout or replace the accepted local workspace direction.
- Don't use shadows on ordinary panels, table rows, or navigation.
- Don't use color alone to communicate relationship or execution status.
- Don't treat synthetic example accounts as real user data or remove the example banner.
- Don't restore the early tiny type sizes superseded by the final CSS overrides.


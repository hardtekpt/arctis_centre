# Twinkle Tray Style Guide (Extract + Implementation Target)

## Source Basis
- Reference repo: `xanderfrangos/twinkle-tray`
- Retrieved successfully: `package.json` and `package-lock.json` (raw GitHub).
- Direct full-repo clone/file crawl was blocked in this environment, so style rules below combine:
  - available Twinkle Tray metadata
  - observed Windows 10/11 flyout conventions
  - explicit Twinkle Tray-like tokenized SCSS implementation choices

## Stack and Build Profile
From retrieved Twinkle Tray package metadata:
- Electron app shell
- React renderer
- Sass/SCSS pipeline (`@parcel/transformer-sass`, `sass`)
- Parcel bundling in upstream project
- Electron Builder packaging

This implementation mirrors the same architecture pattern:
- Electron main process + preload + tray/flyout window
- React renderer
- SCSS tokenized styling
- Electron Builder for Windows packaging

## Token Table (CSS Variables)
Primary tokens implemented in `renderer/src/styles/tokens.scss`:

| Token | Purpose | Dark Value | Light Value |
|---|---|---|---|
| `--font-ui` | Windows-native typography | Segoe UI Variable stack | Segoe UI Variable stack |
| `--accent` | Interactive accent | dynamic from Windows | dynamic from Windows |
| `--panel-bg` | Flyout shell background | `rgba(24,26,31,.78)` | `rgba(246,249,255,.82)` |
| `--card-bg` | Section surface | `rgba(34,38,45,.62)` | `rgba(255,255,255,.72)` |
| `--line-soft` | Borders/dividers | light alpha white | light alpha dark |
| `--text-primary` | Primary text | bright near-white | dark near-black |
| `--text-muted` | Secondary text | muted gray-blue | muted slate |
| `--radius-*` | Radius scale | 6/8/10/14 px | same |
| `--space-*` | Spacing scale | 4/8/12/16/20 px | same |
| `--shadow-elev` | Flyout elevation | deep shadow | softer shadow |

## Component Styling Notes
1. Buttons:
- Soft bordered ghost buttons.
- Accent-tinted active state.
- Fast 120ms transitions for hover/active.

2. Sliders:
- Thin track with rounded thumb.
- Accent thumb color.
- Border to keep visual parity in both themes.

3. Toggle:
- Compact checkbox + text labeling.
- No oversized custom switch to match dense flyout UI.

4. List rows:
- Dense rounded rows.
- Subtle alpha background and hairline border.
- Truncated app list text.

5. Cards/sections:
- Layered panel + inner cards, each with rounded corners.
- Border + translucency to emulate flyout material.

6. Status/footer:
- Muted neutral copy by default.
- Error status uses red text accent.

## Flyout Window Behavior Notes
Implemented behavior:
- Frameless, transparent, always-on-top panel.
- No taskbar presence (`skipTaskbar`).
- Tray click toggles open/close.
- Opens near tray bounds and clamps to monitor work area.
- Click-away dismiss through `blur` handling.
- Keyboard/mouse interaction remains in focused flyout.
- Close control hides flyout (does not terminate app).

Animation:
- Renderer-level open animation (`flyin` keyframes, ~140ms).

Windows theme integration:
- `nativeTheme.shouldUseDarkColors` for dark/light.
- Accent color from registry query (`HKCU\\Software\\Microsoft\\Windows\\DWM\\ColorizationColor`).

## Implementation Notes
- Accent token is injected at runtime on boot/theme events.
- All components rely on shared variables (no hardcoded one-off colors for interactive states).
- Typography uses Segoe stack to remain consistent with Windows tray utilities.

# arctis-centre-app

## Purpose

Electron + React desktop tray application for Arctis control with a flyout UI and a Python backend bridge.

Location:

- `src/Apps/arctis-centre-app`

## Architecture

Main layers:

- `electron/`: main process, tray integration, windows, IPC, backend process management
- `renderer/`: React UI and SCSS styles
- `shared/`: shared UI state types/settings
- `scripts/backend_bridge.py`: Python bridge to `arctis_nova_api`

Runtime behavior:

- Spawns Python bridge process and exchanges JSON events/commands over stdio
- Persists UI/app state to Electron user data directory
- Provides flyout dashboard, settings, about window, and notification windows

## Key Files

- `electron/main.ts`: app lifecycle, tray/flyout behavior, IPC handlers
- `electron/services/backend.ts`: Python process launch and event protocol
- `scripts/backend_bridge.py`: polls hardware + Sonar and executes write commands
- `renderer/src/App.tsx`: renderer shell and page switching

## Dependencies

- Node.js 20+
- Electron + React + TypeScript + Vite
- Python 3.10+ for bridge runtime

## Development

```powershell
cd src/Apps/arctis-centre-app
npm install
npm run dev
```

Typecheck:

```powershell
npm run typecheck
```

Build:

```powershell
npm run build
```

## Integration with API Module

The app depends on `src/APIs/arctis_nova_api/src` for imports during bridge execution.

State migration fallback checks:

- `src/APIs/arctis_nova_api/tools/tray_dashboard_state.json`

## Migration Assumptions (From Legacy Notes)

- Twinkle Tray full source was not fully crawlable in the constrained environment used during migration work; style extraction relied on available metadata and Windows flyout conventions.
- Hardware/Sonar parity is provided by a Python bridge (`scripts/backend_bridge.py`) reusing `arctis_nova_api`.
- `python` (or `py -3`) must be available on PATH for bridge startup.
- The previous Python tray app had no separate settings window; this app introduces dedicated settings while preserving control flows.
- State migration uses `src/APIs/arctis_nova_api/tools/tray_dashboard_state.json` when available.

## Twinkle-Inspired Style Profile (Merged Legacy Style Guide)

Style direction used for this app:

- Electron + React renderer architecture
- SCSS tokenized styling
- Windows-native typography and tray/flyout behavior

Token intent (implemented under `renderer/src/styles/tokens.scss`):

- `--font-ui`, `--accent`
- `--panel-bg`, `--card-bg`
- `--line-soft`, `--text-primary`, `--text-muted`
- `--radius-*`, `--space-*`, `--shadow-elev`

Component style rules:

- Buttons: soft bordered ghost buttons, accent-tinted active state, short transitions
- Sliders: thin track, rounded accent thumb, high contrast in both themes
- Toggles: compact checkbox-like density aligned with flyout UI
- List rows/cards: dense rounded surfaces with subtle alpha backgrounds and hairline borders
- Status/footer: neutral text by default; explicit error coloring on failures

Window behavior profile:

- Frameless transparent always-on-top flyout
- Tray-click toggle with monitor-bound positioning and blur-dismiss
- Close action hides window (no process termination)
- Renderer-level open animation
- Theme integration via `nativeTheme.shouldUseDarkColors` + Windows accent color query (`HKCU\\Software\\Microsoft\\Windows\\DWM\\ColorizationColor`)

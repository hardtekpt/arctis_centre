# Arctis Centre (Electron + React)

Tray flyout dashboard for Arctis Nova + Sonar with a Twinkle Tray-inspired visual system.

## Requirements
- Windows 10/11
- Node.js 20+
- Python 3.10+ (for hardware bridge)

## Install
```powershell
npm install
```

## Run (Dev)
```powershell
npm run dev
```

## Build
```powershell
npm run build
```

## Project Layout
- `electron/`: main process, tray, window positioning, preload, backend process management
- `renderer/`: React UI and SCSS tokenized styling
- `shared/`: shared types/default schema
- `scripts/backend_bridge.py`: Python hardware backend bridge
- `docs/`: migration spec and style guide

## Persistence
- Settings: `%APPDATA%/<app>/settings.json` (`app.getPath("userData")`)
- Cached state: `%APPDATA%/<app>/state-cache.json`
- Optional migration source: `../tools/tray_dashboard_state.json`

## Parity Checklist
- Tray icon with open/settings/about/quit menu: `electron/tray.ts`
- Tray click toggles flyout: `electron/main.ts`
- Frameless always-on-top flyout near tray: `electron/window.ts`
- Click-away hide behavior: `electron/main.ts`
- Status telemetry panel: `renderer/src/components/StatusCard.tsx`
- Sonar channel volume/mute/preset controls: `renderer/src/components/ChannelRow.tsx`
- Preset loading + state refresh + command dispatch: `scripts/backend_bridge.py`, `electron/services/backend.ts`
- Persisted state fallback: `electron/main.ts`, `shared/settings.ts`
- Accent/dark-light theme application: `electron/main.ts`, `renderer/src/state/store.ts`, `renderer/src/styles/tokens.scss`

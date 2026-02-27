# Functional Spec: Legacy Python Tray Dashboard

## Scope
Source audited from `src/Apps/tray_dashboard`:
- `main.py`
- `app/ui/window.py`
- `app/ui/widgets.py`
- `app/backend/service.py`
- `app/constants.py`
- `app/models.py`

## User-Facing Features
1. Tray app bootstrap:
- Starts a tray app and immediately opens a floating control window.
- If tray is unavailable, app throws and exits.

2. Tray behavior:
- Tray icon with context menu actions: `Open`, `Quit`.
- Single-click/double-click tray icon opens flyout.
- Closing the window does not quit; it hides to tray.
- `Quit` stops worker thread and exits app.

3. Flyout window shell:
- Frameless, translucent, always-on-top tool window.
- Rounded corners and DWM backdrop effect on Windows.
- Positioned near bottom-right of primary display when shown.
- Click-away behavior: on window deactivation, hides (if cursor on same monitor).

4. Status panel (read-only telemetry):
- Connection labels: `connected`, `wireless`, `bluetooth`.
- Mode labels: `anc_mode`, `mic_mute`, `sidetone`.
- Live labels: `chat_mix_balance`, `oled_brightness`.
- Battery line widget showing headset + base percentages.
- Headset volume progress bar.
- Last-updated timestamp.

5. Sonar channels panel (interactive):
- Channels: `master`, `game`, `chatRender`, `media`, `aux`, `chatCapture`.
- Per channel controls:
  - Volume slider (0-100).
  - Mute checkbox.
  - Preset dropdown.
  - Routed apps readout.

6. Command actions:
- `set_channel_volume`: applies to classic + streamer modes (streaming + monitoring).
- `set_channel_mute`: applies to classic + streamer modes.
- `set_preset`: selects by preset name if known; otherwise by id.

7. Status/error line:
- Neutral status text for successful operations.
- Red error styling for exceptions.

## User Flows
1. Launch:
- App starts, backend thread starts, presets load, full state refresh emits.

2. Adjust channel volume:
- User drags slider, release sends `set_channel_volume`.
- UI locks channel controls temporarily to avoid refresh jitter.
- Backend verifies and emits status + updated state.

3. Toggle mute:
- Checkbox change sends `set_channel_mute`.
- UI channel lock applied briefly.

4. Change preset:
- Preset combo change sends `set_preset`.
- UI channel lock applied briefly.

5. Hide/show:
- Lose focus -> hide.
- Tray click/open action -> show + reposition.

6. Exit:
- Tray `Quit` -> stop backend service, quit thread, terminate app.

## Data Model and Persistence
State schema (`DEFAULT_STATE`):
- `headset_battery_percent: number | null`
- `base_battery_percent: number | null`
- `headset_volume_percent: number | null`
- `anc_mode: string | null`
- `mic_mute: boolean | null`
- `sidetone_level: number | null`
- `connected: boolean | null`
- `wireless: boolean | null`
- `bluetooth: boolean | null`
- `chat_mix_balance: number | null`
- `oled_brightness: number | null`
- `channel_volume: Record<string, number>`
- `channel_mute: Record<string, boolean>`
- `channel_preset: Record<string, string | null>`
- `channel_apps: Record<string, string[]>`
- `updated_at: string | null`

Persistence file:
- Path: `src/APIs/arctis_nova_api/tools/tray_dashboard_state.json`
- Atomic save via temp file + replace.
- Used as fallback when live data unavailable.

## Background Tasks / Timers
Backend worker loop frequencies:
- Fast events poll: every ~120 ms.
- Sonar poll: every ~600 ms.
- Hardware poll: every ~800 ms.
- Loop sleep: 20 ms.

Update trigger:
- Emit state only when changed (or forced refresh).

## Integrations / OS Features
1. Hardware/API integration:
- Uses `arctis_nova_api.ArctisNovaProApi`.
- Base station USB connect + event stream.
- Sonar channel read/write operations.
- Preset discovery + selection.

2. Experimental command profile:
- ANC, mic, sidetone command ids and value indexes are custom configured.

3. Windows-specific shell integration:
- System tray icon/menu.
- Always-on-top frameless tool window.
- DWM corner preference and backdrop attributes.

## Constraints for Rebuild
Must preserve:
- Same channel set and command operations.
- Same telemetry fields and fallback behavior.
- Same tray/flyout lifecycle semantics.
- Same state shape, update cadence, and error tolerance.

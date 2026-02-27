# tray_dashboard

## Purpose

Compact Python/PySide6 tray application for live Arctis telemetry and Sonar channel controls.

Location:

- `src/Apps/tray_dashboard`

## Architecture

- `main.py`: Qt bootstrap and tray availability check
- `app/ui/window.py`: tray menu and floating flyout window
- `app/ui/widgets.py`: custom widgets
- `app/backend/service.py`: threaded polling/event/write service
- `app/constants.py`: channel and preset mappings
- `app/models.py`: command models shared between UI and backend thread

## Features

- Tray icon with open/quit actions
- Floating always-on-top control panel
- Live status:
  - battery
  - connection
  - ANC/mic/sidetone/chat mix
  - channel volume/mute/preset/routed apps
- Control actions:
  - set channel volume
  - set channel mute
  - set channel preset

Detailed behavior preserved from legacy spec:

- Tray bootstrap:
  - app opens a floating window on startup
  - app exits when system tray is unavailable
- Tray interaction:
  - tray menu: `Open`, `Quit`
  - single/double click opens flyout
  - window close hides to tray (no process exit)
- Flyout shell:
  - frameless, translucent, always-on-top tool window
  - Windows DWM backdrop/rounded corner usage
  - bottom-right placement on show
  - click-away hide behavior
- Status panel fields:
  - `connected`, `wireless`, `bluetooth`
  - `anc_mode`, `mic_mute`, `sidetone`
  - `chat_mix_balance`, `oled_brightness`
  - headset/base battery and headset volume progress
  - `updated_at` timestamp
- Channel controls:
  - channels: `master`, `game`, `chatRender`, `media`, `aux`, `chatCapture`
  - per-channel volume, mute, preset, routed apps
- Command semantics:
  - volume/mute writes are attempted for classic + streamer modes
  - preset set uses preset name when available, fallback to preset id
- Status/error line:
  - neutral success status text
  - error text styling for exceptions

## User Flows

1. Launch:
   - backend worker starts, presets load, full refresh emits state.
2. Change channel volume:
   - slider release dispatches `set_channel_volume`, UI briefly locks row, state refreshes.
3. Toggle channel mute:
   - checkbox dispatches `set_channel_mute`, UI briefly locks row.
4. Change preset:
   - dropdown dispatches `set_preset`, UI briefly locks row.
5. Hide/show:
   - window blur hides; tray action shows/repositions.
6. Exit:
   - `Quit` stops backend service and exits app.

## Persistence

- State file: `src/APIs/arctis_nova_api/tools/tray_dashboard_state.json`
- Atomic save via temp file + replace
- Fallback source when live data is temporarily unavailable

State shape:

- `headset_battery_percent`
- `base_battery_percent`
- `headset_volume_percent`
- `anc_mode`
- `mic_mute`
- `sidetone_level`
- `connected`
- `wireless`
- `bluetooth`
- `chat_mix_balance`
- `oled_brightness`
- `channel_volume`
- `channel_mute`
- `channel_preset`
- `channel_apps`
- `updated_at`

## Backend Cadence

- Fast event poll: ~120 ms
- Sonar poll: ~600 ms
- Hardware poll: ~800 ms
- Main loop sleep: ~20 ms
- State emits only on changes (or forced refresh)

## Run

```powershell
python -m pip install -r src/Apps/tray_dashboard/requirements.txt
python src/Apps/tray_dashboard/main.py
```

## Integration with API Module

`app/backend/service.py` instantiates `ArctisNovaProApi` and continuously merges event-driven updates with polled Sonar/hardware state.

Integration details:

- base station USB event stream
- Sonar read/write operations
- preset discovery/selection
- experimental command profile mappings for ANC/mic/sidetone

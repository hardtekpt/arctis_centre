# Arctis Tray Dashboard

Windows system tray application for monitoring and controlling Arctis Nova + Sonar in a compact floating window.

## Features

- Tray icon with `Open` and `Quit` actions
- Floating compact window near bottom-right of the screen
- Live monitor:
  - headset/base battery
  - connection state
  - ANC mode, mic mute, sidetone
  - chat mix
  - active USB input
  - OLED brightness
  - per-channel volume, mute, selected preset, routed apps
- Live controls:
  - channel volume/mute/preset

## Architecture

The app is split into clear layers:

- `main.py`: startup/bootstrap only
- `app/backend/service.py`: always-on backend listener/action service
  - listens for base station events continuously
  - polls Sonar state
  - executes queued UI actions
- `app/ui/window.py`: tray + floating window UI
- `app/ui/widgets.py`: custom UI widgets (battery line icon)
- `app/constants.py`: channel/preset mappings
- `app/models.py`: shared command models

## Install

From repository root (inside your virtual environment):

```powershell
python -m pip install -r applications/tray_dashboard/requirements.txt
```

Also ensure project dependencies are installed (`requests`, optional `hidapi` for base station USB).

## Run

```powershell
python applications/tray_dashboard/main.py
```

## Notes

- ANC/USB/sidetone write operations depend on available experimental commands and firmware behavior.
- If a control is unsupported, the app keeps running and shows the error in the status line.
- Closing the window hides it to tray. Use tray menu `Quit` to fully exit.
- The app persists last known state to `tools/tray_dashboard_state.json` and uses it as fallback when live data is temporarily unavailable.

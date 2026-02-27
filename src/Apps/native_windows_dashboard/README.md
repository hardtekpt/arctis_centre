# Native Windows Dashboard (Tray + Backend Service)

Native Windows tray application with a WPF frontend and a Python backend service.

## What this app does

- Always-running local backend service (Python/FastAPI) that:
  - listens for Arctis base station events
  - polls Sonar state
  - persists state to `src/APIs/arctis_nova_api/tools/native_windows_dashboard_state.json`
  - executes actions (channel volume/mute/preset)
- Native Windows frontend (WPF) that:
  - runs as a tray app
  - opens a compact floating window from tray click
  - supports global hotkey `Ctrl+Alt+F10`
  - shows live status + per-channel controls

## Project structure

```text
src/Apps/native_windows_dashboard/
  backend/
    main.py
    requirements.txt
    native_dashboard_backend/
      app.py
      runtime.py
      models.py
  frontend/
    NativeDashboard/
      NativeDashboard.csproj
      App.xaml
      App.xaml.cs
      MainWindow.xaml
      MainWindow.xaml.cs
      Services/
      Models/
```

## Dependencies

1. Python 3.10+
2. .NET 8 SDK (Windows Desktop workload)
3. Existing project dependencies from repo root:
   - `requests`
   - `hidapi` (for USB base station features)
4. Backend dependencies:
   - `fastapi`
   - `uvicorn[standard]`

## Installation

1. Create/activate venv at repo root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

2. Install this repo package + USB extras:

```powershell
python -m pip install -e ".[usb,test]"
```

3. Install backend service deps:

```powershell
python -m pip install -r src/Apps/native_windows_dashboard/backend/requirements.txt
```

4. Install .NET SDK 8:

```text
https://dotnet.microsoft.com/en-us/download/dotnet/8.0
```

Verify:

```powershell
dotnet --version
```

## Run in development

From repo root:

```powershell
dotnet build src/Apps/native_windows_dashboard/frontend/NativeDashboard/NativeDashboard.csproj
dotnet run --project src/Apps/native_windows_dashboard/frontend/NativeDashboard/NativeDashboard.csproj
```

The frontend auto-starts the Python backend process (`src/Apps/native_windows_dashboard/backend/main.py`).

## Usage

1. App starts in tray.
2. Left-click tray icon to open the window.
3. Use `Ctrl+Alt+F10` to open/focus the window.
4. Adjust Sonar channel volume/mute/preset from channel rows.
5. Use tray context menu `Quit` to stop frontend + backend.

## Packaging goal (executable)

Recommended production packaging:

1. Backend:
   - package with `pyinstaller` into a single executable
2. Frontend:
   - publish WPF app as self-contained
   - optionally create MSIX installer
3. Update `BackendProcessManager` to launch packaged backend executable instead of `python main.py`

## Notes

- Preset dropdowns use favorite presets only (from Sonar DB favorite flags).
- If Sonar/GG is unavailable, backend health/status fields report error details.
- State file fallback path:
  - `src/APIs/arctis_nova_api/tools/native_windows_dashboard_state.json`

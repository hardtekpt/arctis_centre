# native_windows_dashboard

## Purpose

Native Windows dashboard composed of:

- WPF tray frontend (`.NET`)
- Python FastAPI backend service

Location:

- `src/Apps/native_windows_dashboard`

## Architecture

Backend (`backend/`):

- `main.py`: launches Uvicorn
- `native_dashboard_backend/app.py`: FastAPI app factory and API routes
- `native_dashboard_backend/runtime.py`: polling/event runtime over `arctis_nova_api`
- `native_dashboard_backend/models.py`: request/response schemas

Frontend (`frontend/NativeDashboard/`):

- WPF tray app and floating window UI
- HTTP client to backend endpoints
- Backend process bootstrap and lifecycle management

## Backend API Endpoints

- `GET /health`
- `GET /state`
- `GET /presets`
- `POST /actions/channel-volume`
- `POST /actions/channel-mute`
- `POST /actions/channel-preset`

## Persistence

- State file: `src/APIs/arctis_nova_api/tools/native_windows_dashboard_state.json`

## Development

Python backend dependencies:

```powershell
python -m pip install -r src/Apps/native_windows_dashboard/backend/requirements.txt
```

Frontend run:

```powershell
dotnet build src/Apps/native_windows_dashboard/frontend/NativeDashboard/NativeDashboard.csproj
dotnet run --project src/Apps/native_windows_dashboard/frontend/NativeDashboard/NativeDashboard.csproj
```

## Integration with API Module

Backend runtime uses `ArctisNovaProApi` for Sonar and base station operations and mirrors the same channel model as other apps.

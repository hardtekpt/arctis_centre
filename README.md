# Arctis Centre

Arctis Centre is a multi-module workspace for SteelSeries Arctis Nova Pro Wireless integration. It combines a reusable Python API with multiple desktop application frontends.

## Repository Layout

```text
src/
  APIs/
    arctis_nova_api/
      pyproject.toml
      src/
      tests/
      tools/
      examples/
  Apps/
    arctis-centre-app/
    native_windows_dashboard/
    tray_dashboard/
    twinkle_tray/
docs/
```

## Module Documentation

- Docs index: `docs/README.md`
- API module:
  - `arctis_nova_api`: `docs/apis/arctis_nova_api.md`
- App modules:
  - `arctis-centre-app`: `docs/apps/arctis-centre-app.md`
  - `native_windows_dashboard`: `docs/apps/native_windows_dashboard.md`
  - `tray_dashboard`: `docs/apps/tray_dashboard.md`
  - `twinkle_tray`: `docs/apps/twinkle_tray.md`

## Quick Start

1. Create and activate a virtual environment.
2. Install the API package:

```powershell
python -m pip install -e src/APIs/arctis_nova_api
```

3. For API tests:

```powershell
python -m pip install -e "src/APIs/arctis_nova_api[test]"
python -m pytest src/APIs/arctis_nova_api/tests
```

4. For Electron app development:

```powershell
cd src/Apps/arctis-centre-app
npm install
npm run dev
```

## Notes

- Windows is the primary target platform for hardware and tray integrations.
- State and helper artifacts are stored under `src/APIs/arctis_nova_api/tools`.
- Detailed module documentation is centralized under `docs/`.

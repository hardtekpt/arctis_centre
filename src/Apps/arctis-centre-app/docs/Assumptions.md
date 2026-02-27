# Assumptions

1. Twinkle Tray full source was not cloneable from this environment due outbound network restrictions; style extraction uses available raw metadata + Windows flyout conventions.
2. Hardware/Sonar control parity is provided through a Python bridge (`scripts/backend_bridge.py`) that reuses existing `arctis_nova_api` integration logic.
3. `python` (or `py -3`) is available on PATH on the target Windows machine.
4. Current Python app does not expose separate settings screens; the new app adds minimal flyout settings for theme and blur-dismiss behavior without removing existing flows.
5. State migration reads `../../APIs/arctis_nova_api/tools/tray_dashboard_state.json` when accessible from dev layout.

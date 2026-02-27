# arctis_nova_api

## Purpose

`arctis_nova_api` is the core Python integration layer for Arctis Nova Pro Wireless features:

- Sonar local API and Sonar config data access
- GameSense OLED endpoint integration
- USB base station communication and event decoding

Location:

- Package root: `src/APIs/arctis_nova_api`
- Python sources: `src/APIs/arctis_nova_api/src/arctis_nova_api`
- Tests: `src/APIs/arctis_nova_api/tests`
- Tools: `src/APIs/arctis_nova_api/tools`
- Examples: `src/APIs/arctis_nova_api/examples`

## Public API Surface

Primary facade:

- `ArctisNovaProApi` (`client.py`) with:
  - `sonar: SonarClient`
  - `gamesense: GameSenseClient`
  - `base_station: BaseStationClient`

Core clients:

- `SonarClient` (`sonar.py`)
- `GameSenseClient` (`gamesense.py`)
- `BaseStationClient` (`base_station.py`)

Models/enums:

- `SonarChannel`, `PresetChannel`, `StreamerSlider`
- `AncMode`, `UsbInput`
- `BatteryStatus`, `VolumeKnobEvent`, `HeadsetConnectionStatus`
- `SidetoneStatus`, `AncStatus`, `MicStatus`, `OledBrightnessStatus`
- `OledLine`, `OledFrame`

Errors:

- `ArctisNovaError` and derived exceptions in `errors.py`

## Internal Module Map

- `client.py`: top-level API composition
- `core.py`: discovery and HTTP helper logic
- `sonar.py`: Sonar control/read operations (volume, mute, presets, routing, chat mix)
- `gamesense.py`: GameSense screen/event payload operations
- `base_station.py`: HID transport and device command/event methods
- `sniffer.py`: incoming HID report decode helper
- `capture_parser.py`: analysis helpers for captured HID logs
- `models.py`: typed enums/dataclasses

## Tooling and Examples

Tools (`tools/`):

- `hid_sniffer.py`
- `parse_hid_capture.py`
- `capture_usb_commands.py`
- `replay_hid_command.py`
- Command profile JSON files and persisted state JSON files

Examples (`examples/`):

- `read_only_example.py`
- `full_api_example.py`
- `live_event_listener.py`
- `live_state_dashboard.py`

## Installation and Test

From repo root:

```powershell
python -m pip install -e src/APIs/arctis_nova_api
python -m pip install -e "src/APIs/arctis_nova_api[test]"
python -m pytest src/APIs/arctis_nova_api/tests
```

Optional USB extras:

```powershell
python -m pip install -e "src/APIs/arctis_nova_api[usb]"
```

## Used By

- `src/Apps/arctis-centre-app` via Python bridge script
- `src/Apps/tray_dashboard` directly in Python runtime
- `src/Apps/native_windows_dashboard` backend service runtime

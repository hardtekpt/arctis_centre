# Arctis Nova Pro Wireless Python API

Python package for controlling SteelSeries Arctis Nova Pro Wireless features through:

- Sonar local API (`ggEncryptedAddress` -> `subApps.sonar.metadata.webServerAddress`)
- Sonar SQLite config DB (`%PROGRAMDATA%/SteelSeries/GG/apps/sonar/db/database.db`)
- GameSense SDK HTTP endpoints (OLED screen handlers and text)
- Direct USB HID base-station communication (brightness, return to UI, event polling)

## Features

- GG Sonar presets
  - List available presets per channel (`configs.vad`)
  - List favorite presets only per channel (when favorite flag exists in Sonar DB schema)
  - Read selected preset per channel
  - Select preset by id or by name
- GG Sonar channel volume
  - Get full volume payload
  - Set per-channel volume
  - Set per-channel mute
  - Read/set streamer mode and chat mix
- OLED text and behavior
  - Register/bind GameSense screen handlers
  - Send 1-3 line text payloads with timing/repeat/icon behavior
- Additional headset/base-station controls
  - Base-station brightness
  - Return display to default SteelSeries UI
  - Parse base-station events: knob volume, battery, connection state
  - Read current headset battery and charging-station battery
  - Mic sidetone status and control via experimental command profile
  - ANC + USB input API surface via experimental command profile (firmware-dependent)

## Install (Virtual Environment)

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

macOS/Linux (bash/zsh):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For USB HID features:

```bash
python -m pip install -e ".[usb]"
```

For tests:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

## Project Structure

```text
src/arctis_nova_api/
  __init__.py
  client.py
  core.py
  errors.py
  models.py
  sonar.py
  gamesense.py
  base_station.py
examples/
  full_api_example.py
tests/
  test_sonar.py
  test_gamesense.py
  test_base_station.py
```

## Example

See `examples/full_api_example.py` for a full walkthrough of all API methods.

For a non-mutating script that only reads current state, use:

`examples/read_only_example.py`

## Notes on ANC and USB Input

ANC mode and USB input switching are exposed as methods in `BaseStationClient`, but those commands vary by firmware and are not documented in the official SDK. This implementation supports these controls through `ExperimentalCommandProfile` so command bytes can be injected once discovered for your specific device firmware.

## HID Sniffer (for ANC and USB Input Reverse Engineering)

A helper sniffer script is included at `tools/hid_sniffer.py`.

Install USB dependency first:

```bash
python -m pip install -e ".[usb]"
```

Capture live reports while toggling ANC mode and USB input in SteelSeries GG:

```bash
python tools/hid_sniffer.py --jsonl anc_usb_capture.jsonl
```

Optional filters:

```bash
python tools/hid_sniffer.py --product-id 0x12e0 --interface 4 --duration 60 --jsonl anc_usb_capture.jsonl
```

Parse capture windows and unknown report patterns:

```bash
python tools/parse_hid_capture.py anc_usb_capture.jsonl --gap-seconds 2.5 --top 12 --min-unknown 1
```

How to use captured data:

1. Start capture.
2. Toggle one setting (for example ANC Off -> ANC -> Transparency) in GG.
3. Toggle USB input (USB1 -> USB2 -> USB1).
4. Stop capture and inspect repeated unknown report patterns around each action.
5. Add discovered write commands into `ExperimentalCommandProfile` and test through `BaseStationClient`.

### Hardcoded Event Decoding From Your Captures

The API now has hardcoded defaults (from your provided sniffer captures):

- ANC event command id: `0xBD` with value map:
  - `0 -> off`
  - `1 -> transparency`
  - `2 -> anc`
- MIC event command id: `0xBB` with value map:
  - `1 -> mic enabled` (`muted=False`)
  - `0 -> mic disabled` (`muted=True`)
- Sidetone event command id: `0x39` with value map:
  - `0 -> off`
  - `1 -> low`
  - `2 -> med`
  - `3 -> high`

No profile loader is required for this decoding.

### Live Event Listener Example

Run:

```bash
python examples/live_event_listener.py
```

This prints decoded updates for:

- headset volume
- ANC / transparency mode
- MIC mute state
- sidetone level
- battery (headset and base station)

## Optional Utilities

The helper scripts `tools/capture_usb_commands.py` and `tools/replay_hid_command.py` are kept in this project as optional, experimental utilities. They are not part of the core supported workflow.

### Active Query Commands (Battery / Sidetone)

Passive battery updates are decoded from incoming `0xB7` reports (both `0x06` and `0x07` report headers).
If your firmware supports active query commands, configure them in `ExperimentalCommandProfile`:

```python
from arctis_nova_api import BaseStationClient, ExperimentalCommandProfile

profile = ExperimentalCommandProfile(
    battery_query_command=[0x06, 0x??],     # discovered command bytes
    sidetone_get_command=[0x06, 0x??],      # discovered command bytes
    sidetone_set_commands={
        0: [0x06, 0x??, 0x00],
        5: [0x06, 0x??, 0x05],
        10: [0x06, 0x??, 0x0A],
    },
    sidetone_event_command_id=0x??,         # command id in responses
    sidetone_value_index=2,                 # byte index containing sidetone level
)

client = BaseStationClient(command_profile=profile)
```

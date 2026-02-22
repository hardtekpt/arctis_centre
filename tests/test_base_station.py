from __future__ import annotations

import pytest

from arctis_nova_api.base_station import BaseStationClient, ExperimentalCommandProfile
from arctis_nova_api.errors import UnsupportedFeatureError
from arctis_nova_api.models import AncMode


class _FakeDevice:
    def __init__(self, read_queue=None):
        self.path = None
        self.writes = []
        self.feature_reports = []
        self.read_queue = read_queue or []

    def open_path(self, path):
        self.path = path

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def send_feature_report(self, data):
        self.feature_reports.append(data)
        return len(data)

    def read(self, length, timeout_ms=0):
        if self.read_queue:
            return self.read_queue.pop(0)
        return []

    def close(self):
        return None


class _FakeHidBackend:
    def __init__(self):
        self.devices = [
            {"interface_number": 4, "path": b"dev-a"},
            {"interface_number": 4, "path": b"dev-b"},
        ]
        self._created = []

    def enumerate(self, vendor_id, product_id):
        return list(self.devices)

    def device(self):
        dev = _FakeDevice(read_queue=[[0x07, 0xB7, 80, 30, 0], []])
        self._created.append(dev)
        return dev


def test_connect_brightness_and_events():
    hid = _FakeHidBackend()
    client = BaseStationClient(hid_backend=hid)
    client.connect()
    client.set_brightness(5)
    events = client.get_pending_events()
    assert events
    assert events[0].headset == 80
    assert client.get_headset_battery() == 80
    assert client.get_charging_station_battery() == 30


def test_anc_requires_profile():
    hid = _FakeHidBackend()
    client = BaseStationClient(hid_backend=hid)
    client.connect()
    with pytest.raises(UnsupportedFeatureError):
        client.set_anc_mode(AncMode.ANC)


def test_refresh_battery_status():
    hid = _FakeHidBackend()
    client = BaseStationClient(hid_backend=hid)
    client.connect()
    assert client.get_battery_status() is None
    status = client.get_battery_status(refresh_timeout_seconds=0.05)
    assert status is not None
    assert status.headset == 80
    assert status.charging == 30


def test_request_battery_and_sidetone_with_profile():
    hid = _FakeHidBackend()
    profile = ExperimentalCommandProfile(
        battery_query_command=[0x06, 0xA1],
        sidetone_get_command=[0x06, 0xA2],
        sidetone_set_commands={5: [0x06, 0xA3, 0x05]},
        sidetone_event_command_id=0xC1,
        sidetone_value_index=3,
    )
    client = BaseStationClient(hid_backend=hid, command_profile=profile)
    client.connect()

    # Seed info device queue with battery + sidetone responses.
    info_dev = hid._created[1]
    info_dev.read_queue = [
        [0x06, 0xB7, 2, 8, 0, 0],
        [0x07, 0xC1, 0, 7, 0, 0],
        [],
    ]

    battery = client.request_battery_status(timeout_seconds=0.05)
    assert battery is not None
    assert battery.headset == 2
    assert battery.charging == 8

    sidetone = client.request_sidetone_status(timeout_seconds=0.05)
    assert sidetone is not None
    assert sidetone.level == 7

    client.set_sidetone_level(5)
    oled_dev = hid._created[0]
    assert oled_dev.writes


def test_decode_anc_and_mic_status_with_profile():
    hid = _FakeHidBackend()
    profile = ExperimentalCommandProfile(
        anc_event_command_id=0xBD,
        anc_value_index=2,
        anc_value_map={0: AncMode.OFF, 1: AncMode.TRANSPARENCY, 2: AncMode.ANC},
        mic_event_command_id=0xBB,
        mic_value_index=2,
        mic_on_values={1},
        sidetone_event_command_id=0x39,
        sidetone_value_index=2,
        sidetone_label_map={"off": 0, "low": 1, "med": 2, "high": 3},
    )
    client = BaseStationClient(hid_backend=hid, command_profile=profile)
    client.connect()

    info_dev = hid._created[1]
    info_dev.read_queue = [
        [0x07, 0xBD, 2, 0, 0],  # ANC
        [0x07, 0xBB, 1, 0, 0],  # MIC
        [0x07, 0x39, 3, 0, 0],  # sidetone
        [],
    ]
    client.get_pending_events()

    anc = client.get_anc_status()
    assert anc is not None
    assert anc.mode == AncMode.ANC
    mic = client.get_mic_status()
    assert mic is not None
    assert mic.enabled is True
    sidetone = client.get_sidetone_status()
    assert sidetone is not None
    assert sidetone.level == 3
    assert client.get_sidetone_label() == "high"

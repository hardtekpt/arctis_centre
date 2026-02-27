from __future__ import annotations

from arctis_nova_api.sniffer import decode_input_report


def test_decode_volume_report():
    parsed = decode_input_report(bytes([0x07, 0x25, 0x10, 0x00, 0x00]))
    assert parsed is not None
    assert parsed.report_type == "volume"
    assert parsed.details["volume"] == 40


def test_decode_battery_report():
    parsed = decode_input_report(bytes([0x07, 0xB7, 80, 25, 0x00]))
    assert parsed is not None
    assert parsed.report_type == "battery"
    assert parsed.details["headset"] == 80
    assert parsed.details["charging"] == 25


def test_decode_battery_report_from_06_header():
    parsed = decode_input_report(bytes([0x06, 0xB7, 2, 8, 0x00]))
    assert parsed is not None
    assert parsed.report_type == "battery"
    assert parsed.details["headset"] == 2
    assert parsed.details["charging"] == 8

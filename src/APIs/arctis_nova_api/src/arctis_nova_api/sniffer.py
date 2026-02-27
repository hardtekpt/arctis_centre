from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedInputReport:
    report_type: str
    details: dict[str, int | bool]


def decode_input_report(data: bytes | list[int]) -> ParsedInputReport | None:
    raw = bytes(data)
    if len(raw) < 5 or raw[0] not in (0x06, 0x07):
        return None

    command = raw[1]
    if command == 0x25:
        return ParsedInputReport(
            report_type="volume",
            details={"volume": max(0, 0x38 - raw[2])},
        )
    if command == 0xB5:
        return ParsedInputReport(
            report_type="headset_connection",
            details={
                "wireless": raw[4] == 8,
                "bluetooth": raw[3] == 1,
                "bluetooth_on": raw[2] == 4,
            },
        )
    if command == 0xB7:
        return ParsedInputReport(
            report_type="battery",
            details={"headset": raw[2], "charging": raw[3]},
        )

    return ParsedInputReport(report_type=f"unknown_0x{command:02x}", details={"b2": raw[2], "b3": raw[3], "b4": raw[4]})

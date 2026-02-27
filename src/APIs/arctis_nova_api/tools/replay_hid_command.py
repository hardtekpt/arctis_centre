#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

STEELSERIES_VENDOR_ID = 0x1038
DEFAULT_PRODUCT_ID = 0x12E0
DEFAULT_INTERFACE = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a candidate HID command to the SteelSeries base station.")
    parser.add_argument("--hex", dest="hex_payload", help="Hex bytes, e.g. 06a001 or 06 a0 01")
    parser.add_argument("--bytes", dest="bytes_payload", help="Comma-separated decimal bytes, e.g. 6,160,1")
    parser.add_argument("--vendor-id", default="0x1038", help="Vendor ID (hex)")
    parser.add_argument("--product-id", default="0x12e0", help="Product ID (hex)")
    parser.add_argument("--interface", type=int, default=DEFAULT_INTERFACE, help="HID interface number")
    parser.add_argument("--path", help="Optional exact HID path to open")
    parser.add_argument("--repeat", type=int, default=1, help="How many times to send")
    parser.add_argument("--feature-report", action="store_true", help="Use send_feature_report instead of write")
    parser.add_argument("--pad-64", action="store_true", help="Pad payload to 64 bytes")
    return parser.parse_args()


def parse_payload(args: argparse.Namespace) -> list[int]:
    if args.hex_payload:
        raw = "".join(ch for ch in args.hex_payload if ch in "0123456789abcdefABCDEF")
        if len(raw) % 2 != 0:
            raise ValueError("Hex payload must contain an even number of hex digits")
        return [int(raw[i : i + 2], 16) for i in range(0, len(raw), 2)]
    if args.bytes_payload:
        return [int(part.strip()) & 0xFF for part in args.bytes_payload.split(",") if part.strip()]
    raise ValueError("Provide either --hex or --bytes")


def discover_device(hid: Any, vendor_id: int, product_id: int, interface: int, path: str | None) -> Any:
    dev = hid.device()
    if path:
        dev.open_path(path.encode() if isinstance(path, str) else path)
        return dev

    matches = []
    for item in hid.enumerate(vendor_id, product_id):
        if int(item.get("interface_number", -1)) == interface:
            matches.append(item)
    if not matches:
        raise RuntimeError("No matching HID interface found")
    dev.open_path(matches[0]["path"])
    return dev


def main() -> int:
    args = parse_args()
    payload = parse_payload(args)
    if args.pad_64 and len(payload) < 64:
        payload = payload + [0] * (64 - len(payload))

    vendor_id = int(args.vendor_id, 16)
    product_id = int(args.product_id, 16)

    import hid  # type: ignore

    dev = discover_device(hid, vendor_id, product_id, args.interface, args.path)
    try:
        for _ in range(max(1, args.repeat)):
            if args.feature_report:
                sent = dev.send_feature_report(payload)
            else:
                sent = dev.write(payload)
            print(f"sent={sent} payload={bytes(payload).hex()}")
    finally:
        dev.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


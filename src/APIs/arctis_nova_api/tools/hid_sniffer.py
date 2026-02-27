#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arctis_nova_api.base_station import INTERFACE_NUMBER, STEELSERIES_VENDOR_ID, SUPPORTED_PRODUCT_IDS
from arctis_nova_api.sniffer import decode_input_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture SteelSeries HID input reports to reverse-engineer ANC/USB-input commands."
    )
    parser.add_argument("--product-id", type=lambda x: int(x, 0), help="Filter by product ID (e.g., 0x12e0)")
    parser.add_argument("--interface", type=int, default=INTERFACE_NUMBER, help="HID interface number to monitor")
    parser.add_argument("--duration", type=float, default=0.0, help="Stop after N seconds (0 = run until Ctrl+C)")
    parser.add_argument("--timeout-ms", type=int, default=25, help="Per-read timeout in milliseconds")
    parser.add_argument("--jsonl", type=Path, help="Optional output file for JSONL report logs")
    parser.add_argument("--raw-only", action="store_true", help="Disable decoded summaries")
    return parser.parse_args()


def discover_devices(hid: Any, product_id: int | None, interface: int) -> list[dict[str, Any]]:
    product_ids = [product_id] if product_id is not None else list(SUPPORTED_PRODUCT_IDS)
    found: list[dict[str, Any]] = []
    for pid in product_ids:
        for dev in hid.enumerate(STEELSERIES_VENDOR_ID, pid):
            if int(dev.get("interface_number", -1)) == interface:
                found.append(dev)
    return found


def make_record(path: Any, raw: bytes, raw_only: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "path": _path_to_str(path),
        "raw_hex": raw.hex(),
    }
    if not raw_only:
        parsed = decode_input_report(raw)
        if parsed:
            record["decoded"] = {"type": parsed.report_type, "details": parsed.details}
    return record


def main() -> int:
    args = parse_args()

    try:
        import hid  # type: ignore
    except ImportError:
        print("Missing dependency: pip install hidapi", file=sys.stderr)
        return 2

    devices = discover_devices(hid, product_id=args.product_id, interface=args.interface)
    if not devices:
        print("No matching SteelSeries HID devices found.", file=sys.stderr)
        return 1

    print(f"Found {len(devices)} device(s).")
    print("Start capture. Toggle ANC mode and USB input in SteelSeries GG now. Press Ctrl+C to stop.")

    opened = []
    for dev_info in devices:
        d = hid.device()
        d.open_path(dev_info["path"])
        opened.append((dev_info, d))

    start = time.time()
    out_fp = args.jsonl.open("a", encoding="utf-8") if args.jsonl else None
    seen = 0
    try:
        while True:
            if args.duration > 0 and (time.time() - start) >= args.duration:
                break
            for dev_info, dev in opened:
                raw = bytes(dev.read(64, timeout_ms=args.timeout_ms))
                if not raw:
                    continue
                record = make_record(dev_info["path"], raw, raw_only=args.raw_only)
                seen += 1
                print(format_console(record))
                if out_fp:
                    out_fp.write(json.dumps(record) + "\n")
                    out_fp.flush()
    except KeyboardInterrupt:
        pass
    finally:
        for _, dev in opened:
            dev.close()
        if out_fp:
            out_fp.close()

    print(f"Stopped. Captured {seen} report(s).")
    return 0


def format_console(record: dict[str, Any]) -> str:
    base = f"[{record['ts']}] path={record['path']} raw={record['raw_hex']}"
    decoded = record.get("decoded")
    if decoded:
        return f"{base} decoded={decoded['type']} {decoded['details']}"
    return base


def _path_to_str(path: Any) -> str:
    if isinstance(path, (bytes, bytearray)):
        return bytes(path).decode("utf-8", errors="ignore")
    return str(path)


if __name__ == "__main__":
    raise SystemExit(main())


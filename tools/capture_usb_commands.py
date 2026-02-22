#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


HEX_RE = re.compile(r"^[0-9a-fA-F]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture and analyze USB HID traffic with tshark to discover candidate write commands."
    )
    parser.add_argument("--tshark", default="tshark", help="Path to tshark executable")
    parser.add_argument("--interface", help="Capture interface (for Windows USBPcap use names like USBPcap1)")
    parser.add_argument("--duration", type=int, default=20, help="Capture duration in seconds")
    parser.add_argument("--output", type=Path, default=Path("usb_capture.pcapng"), help="Output pcapng path")
    parser.add_argument("--analyze-only", action="store_true", help="Skip capture and only analyze --output")
    parser.add_argument("--vendor-id", default="1038", help="Hex vendor id without 0x (default SteelSeries=1038)")
    parser.add_argument("--product-id", default="12e0", help="Hex product id without 0x (default ANPW=12e0)")
    parser.add_argument("--include-in", action="store_true", help="Include IN endpoint packets (default OUT only)")
    parser.add_argument("--top", type=int, default=20, help="Top N payloads to print")
    parser.add_argument("--csv", type=Path, help="Optional CSV output for extracted packets")
    return parser.parse_args()


def run_capture(args: argparse.Namespace) -> None:
    if not args.interface:
        raise ValueError("--interface is required unless --analyze-only is used")
    cmd = [
        args.tshark,
        "-i",
        args.interface,
        "-a",
        f"duration:{args.duration}",
        "-w",
        str(args.output),
    ]
    print("Running capture:", " ".join(cmd))
    _run(cmd)


def extract_packets(args: argparse.Namespace) -> list[dict[str, str]]:
    vendor_filter = f'usb.idVendor == 0x{args.vendor_id.lower()}'
    product_filter = f'usb.idProduct == 0x{args.product_id.lower()}'
    display_filter = f"({vendor_filter} and {product_filter}) and (usbhid.data or usb.capdata)"
    cmd = [
        args.tshark,
        "-r",
        str(args.output),
        "-Y",
        display_filter,
        "-T",
        "fields",
        "-E",
        "separator=,",
        "-e",
        "frame.time_epoch",
        "-e",
        "usb.endpoint_address",
        "-e",
        "usbhid.data",
        "-e",
        "usb.capdata",
    ]
    result = _run(cmd, capture_output=True)
    rows: list[dict[str, str]] = []
    reader = csv.reader(result.stdout.splitlines())
    for row in reader:
        if len(row) < 4:
            continue
        ts, endpoint, hid_data, cap_data = row[0], row[1], row[2], row[3]
        payload = normalize_hex(hid_data) or normalize_hex(cap_data)
        if not payload:
            continue
        if not args.include_in and endpoint:
            if is_in_endpoint(endpoint):
                continue
        rows.append({"ts": ts, "endpoint": endpoint, "payload": payload})
    return rows


def is_in_endpoint(endpoint: str) -> bool:
    endpoint = endpoint.strip().lower().replace("0x", "")
    if not endpoint:
        return False
    try:
        value = int(endpoint, 16)
    except ValueError:
        return False
    return (value & 0x80) != 0


def normalize_hex(value: str) -> str | None:
    if not value:
        return None
    raw = value.strip().replace(":", "").replace(" ", "")
    if not raw:
        return None
    if not HEX_RE.match(raw):
        return None
    if len(raw) % 2 != 0:
        return None
    return raw.lower()


def summarize(rows: list[dict[str, str]], top: int) -> None:
    if not rows:
        print("No HID payload rows extracted.")
        return
    payload_counts = Counter(r["payload"] for r in rows)
    prefix2_counts = Counter(p[:4] for p in payload_counts.keys() if len(p) >= 4)
    print(f"Extracted {len(rows)} packets, {len(payload_counts)} unique payloads.")
    print("\nTop payloads:")
    for payload, count in payload_counts.most_common(top):
        print(f"  count={count:3d} payload={payload}")
    print("\nTop 2-byte prefixes (often report+command):")
    for prefix, count in prefix2_counts.most_common(top):
        print(f"  count={count:3d} prefix={prefix}")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["ts", "endpoint", "payload"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote CSV: {path}")


def _run(cmd: list[str], capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            check=True,
            capture_output=capture_output,
            text=True,
        )
    except FileNotFoundError:
        print(f"Command not found: {cmd[0]}", file=sys.stderr)
        print("Install Wireshark/tshark and ensure tshark is on PATH.", file=sys.stderr)
        raise
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        raise


def main() -> int:
    args = parse_args()
    if not args.analyze_only:
        run_capture(args)
    rows = extract_packets(args)
    summarize(rows, top=args.top)
    if args.csv:
        write_csv(args.csv, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


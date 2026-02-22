#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from arctis_nova_api.capture_parser import load_capture, split_time_windows, summarize_windows, top_unknown_types


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse HID sniffer JSONL logs and group unknown reports into likely action windows."
    )
    parser.add_argument("capture", type=Path, help="Path to JSONL capture file from tools/hid_sniffer.py")
    parser.add_argument("--gap-seconds", type=float, default=2.0, help="New window starts after this inactivity gap")
    parser.add_argument("--top", type=int, default=10, help="Top N unknown report types to print")
    parser.add_argument("--min-unknown", type=int, default=1, help="Only print windows with at least this many unknown reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_capture(args.capture)
    if not records:
        print("No records found in capture.")
        return 1

    print(f"Loaded {len(records)} records from {args.capture}")
    print(f"Capture span: {records[0].ts.isoformat()} -> {records[-1].ts.isoformat()}")

    unknowns = top_unknown_types(records)
    print("\nTop unknown report types:")
    if not unknowns:
        print("  none")
    else:
        for report_type, count, sample_hex in unknowns[: args.top]:
            print(f"  {report_type}: count={count}, sample={sample_hex[:20]}...")

    windows = split_time_windows(records, gap_seconds=args.gap_seconds)
    summaries = summarize_windows(windows)

    print(f"\nWindows (gap > {args.gap_seconds}s): {len(summaries)}")
    printed = 0
    for idx, summary in enumerate(summaries, start=1):
        if summary.unknown_records < args.min_unknown:
            continue
        printed += 1
        duration = (summary.end - summary.start).total_seconds()
        print(
            f"\nWindow {idx}: {summary.start.isoformat()} -> {summary.end.isoformat()} "
            f"({duration:.2f}s), total={summary.total_records}, unknown={summary.unknown_records}"
        )
        for report_type, count in summary.unknown_by_type.items():
            sample = summary.sample_hex_by_type.get(report_type, "")
            print(f"  {report_type}: count={count}, sample={sample[:20]}...")

    if printed == 0:
        print("\nNo windows matched the unknown-report filter.")

    print(
        "\nTip: Start capture, toggle one control, wait 3-5 seconds, toggle next control. "
        "This creates clean windows for ANC/USB mapping."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


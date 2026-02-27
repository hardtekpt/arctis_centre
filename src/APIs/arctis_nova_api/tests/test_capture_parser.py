from __future__ import annotations

from datetime import datetime, timedelta, timezone

from arctis_nova_api.capture_parser import CaptureRecord, split_time_windows, summarize_windows, top_unknown_types


def _rec(base: datetime, offset: float, raw_hex: str, decoded_type: str | None) -> CaptureRecord:
    return CaptureRecord(ts=base + timedelta(seconds=offset), path="dev", raw_hex=raw_hex, decoded_type=decoded_type)


def test_split_and_summarize_unknown_windows():
    base = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
    records = [
        _rec(base, 0.0, "07b1000000", "unknown_0xb1"),
        _rec(base, 0.2, "07b1000001", "unknown_0xb1"),
        _rec(base, 3.0, "07b2000000", "unknown_0xb2"),
        _rec(base, 3.2, "0725000000", "volume"),
    ]

    windows = split_time_windows(records, gap_seconds=1.0)
    assert len(windows) == 2

    summaries = summarize_windows(windows)
    assert summaries[0].unknown_records == 2
    assert summaries[0].unknown_by_type["unknown_0xb1"] == 2
    assert summaries[1].unknown_records == 1
    assert summaries[1].unknown_by_type["unknown_0xb2"] == 1

    top = top_unknown_types(records)
    assert top[0][0] == "unknown_0xb1"
    assert top[0][1] == 2


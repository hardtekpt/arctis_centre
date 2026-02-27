from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CaptureRecord:
    ts: datetime
    path: str
    raw_hex: str
    decoded_type: str | None

    @property
    def report_id(self) -> int | None:
        if len(self.raw_hex) < 4:
            return None
        try:
            return int(self.raw_hex[2:4], 16)
        except ValueError:
            return None

    @property
    def is_unknown(self) -> bool:
        return bool(self.decoded_type and self.decoded_type.startswith("unknown_0x"))


@dataclass(frozen=True)
class WindowSummary:
    start: datetime
    end: datetime
    total_records: int
    unknown_records: int
    unknown_by_type: dict[str, int]
    sample_hex_by_type: dict[str, str]


def load_capture(path: Path) -> list[CaptureRecord]:
    records: list[CaptureRecord] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        ts = datetime.fromisoformat(obj["ts"])
        decoded = obj.get("decoded", {})
        decoded_type = decoded.get("type") if isinstance(decoded, dict) else None
        records.append(
            CaptureRecord(
                ts=ts,
                path=str(obj.get("path", "")),
                raw_hex=str(obj.get("raw_hex", "")),
                decoded_type=decoded_type,
            )
        )
    records.sort(key=lambda r: r.ts)
    return records


def split_time_windows(records: list[CaptureRecord], gap_seconds: float = 2.0) -> list[list[CaptureRecord]]:
    if not records:
        return []
    windows: list[list[CaptureRecord]] = [[records[0]]]
    for rec in records[1:]:
        prev = windows[-1][-1]
        delta = (rec.ts - prev.ts).total_seconds()
        if delta > gap_seconds:
            windows.append([rec])
        else:
            windows[-1].append(rec)
    return windows


def summarize_windows(windows: list[list[CaptureRecord]]) -> list[WindowSummary]:
    summaries: list[WindowSummary] = []
    for window in windows:
        unknown_by_type: dict[str, int] = {}
        sample_hex_by_type: dict[str, str] = {}
        unknown_count = 0
        for rec in window:
            if rec.is_unknown and rec.decoded_type:
                unknown_count += 1
                unknown_by_type[rec.decoded_type] = unknown_by_type.get(rec.decoded_type, 0) + 1
                sample_hex_by_type.setdefault(rec.decoded_type, rec.raw_hex)
        summaries.append(
            WindowSummary(
                start=window[0].ts,
                end=window[-1].ts,
                total_records=len(window),
                unknown_records=unknown_count,
                unknown_by_type=dict(sorted(unknown_by_type.items(), key=lambda kv: kv[1], reverse=True)),
                sample_hex_by_type=sample_hex_by_type,
            )
        )
    return summaries


def top_unknown_types(records: list[CaptureRecord]) -> list[tuple[str, int, str]]:
    counts: dict[str, int] = {}
    samples: dict[str, str] = {}
    for rec in records:
        if rec.is_unknown and rec.decoded_type:
            counts[rec.decoded_type] = counts.get(rec.decoded_type, 0) + 1
            samples.setdefault(rec.decoded_type, rec.raw_hex)
    items = [(t, c, samples[t]) for t, c in counts.items()]
    return sorted(items, key=lambda item: item[1], reverse=True)


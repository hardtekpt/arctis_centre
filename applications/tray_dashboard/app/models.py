from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WorkerCommand:
    name: str
    payload: dict[str, Any]

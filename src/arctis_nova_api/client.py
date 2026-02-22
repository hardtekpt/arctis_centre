from __future__ import annotations

from pathlib import Path

from .base_station import BaseStationClient, ExperimentalCommandProfile
from .gamesense import GameSenseClient
from .sonar import SonarClient


class ArctisNovaProApi:
    """High-level facade over Sonar, GameSense, and USB base-station control."""

    def __init__(
        self,
        core_props_path: Path | None = None,
        sonar_db_path: Path | None = None,
        timeout: float = 5.0,
        command_profile: ExperimentalCommandProfile | None = None,
    ) -> None:
        self.sonar = SonarClient(core_props_path=core_props_path, sonar_db_path=sonar_db_path, timeout=timeout)
        self.gamesense = GameSenseClient(core_props_path=core_props_path, timeout=timeout)
        self.base_station = BaseStationClient(command_profile=command_profile)


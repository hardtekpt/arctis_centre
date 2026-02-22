from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import HttpClient, get_gamesense_address, read_core_props
from .models import OledFrame, OledLine


class GameSenseClient:
    """GameSense API client with OLED screen-handler helpers."""

    def __init__(self, core_props_path: Path | None = None, timeout: float = 5.0) -> None:
        core_props = read_core_props(core_props_path) if core_props_path else read_core_props()
        self.base_url = get_gamesense_address(core_props)
        self._http = HttpClient(timeout=timeout, verify_tls=False)

    def register_game(
        self,
        game: str,
        game_display_name: str,
        developer: str,
        deinitialize_timer_length_ms: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "game": _sanitize_token(game),
            "game_display_name": game_display_name,
            "developer": developer,
        }
        if deinitialize_timer_length_ms is not None:
            payload["deinitialize_timer_length_ms"] = deinitialize_timer_length_ms
        self._http.request("POST", f"{self.base_url}/game_metadata", json=payload)

    def register_event(
        self,
        game: str,
        event: str,
        min_value: int = 0,
        max_value: int = 100,
        icon_id: int = 0,
        value_optional: bool = False,
    ) -> None:
        payload = {
            "game": _sanitize_token(game),
            "event": _sanitize_token(event),
            "min_value": min_value,
            "max_value": max_value,
            "icon_id": icon_id,
            "value_optional": value_optional,
        }
        self._http.request("POST", f"{self.base_url}/register_game_event", json=payload)

    def bind_screen_event(
        self,
        game: str,
        event: str,
        frames: list[OledFrame],
        icon_id: int = 0,
        value_optional: bool = True,
    ) -> None:
        handlers = [
            {
                "device-type": "screened",
                "zone": "one",
                "mode": "screen",
                "datas": [_frame_to_handler_data(frame) for frame in frames],
            }
        ]
        payload = {
            "game": _sanitize_token(game),
            "event": _sanitize_token(event),
            "min_value": 0,
            "max_value": 100,
            "icon_id": icon_id,
            "value_optional": value_optional,
            "handlers": handlers,
        }
        self._http.request("POST", f"{self.base_url}/bind_game_event", json=payload)

    def send_event(
        self,
        game: str,
        event: str,
        value: int,
        frame: dict[str, Any] | None = None,
    ) -> None:
        data: dict[str, Any] = {"value": int(value)}
        if frame is not None:
            data["frame"] = frame
        payload = {"game": _sanitize_token(game), "event": _sanitize_token(event), "data": data}
        self._http.request("POST", f"{self.base_url}/game_event", json=payload)

    def send_multiple_events(self, game: str, events: list[dict[str, Any]]) -> None:
        payload = {"game": _sanitize_token(game), "events": events}
        self._http.request("POST", f"{self.base_url}/multiple_game_events", json=payload)

    def heartbeat(self, game: str) -> None:
        self._http.request("POST", f"{self.base_url}/game_heartbeat", json={"game": _sanitize_token(game)})

    def remove_event(self, game: str, event: str) -> None:
        payload = {"game": _sanitize_token(game), "event": _sanitize_token(event)}
        self._http.request("POST", f"{self.base_url}/remove_game_event", json=payload)

    def remove_game(self, game: str) -> None:
        self._http.request("POST", f"{self.base_url}/remove_game", json={"game": _sanitize_token(game)})

    def show_oled_text(
        self,
        game: str,
        event: str,
        lines: list[str],
        icon_id: int = 0,
        length_millis: int = 2000,
    ) -> None:
        oled_lines = [OledLine(text=line, context_frame_key=f"line{i+1}") for i, line in enumerate(lines)]
        frame = OledFrame(lines=oled_lines, icon_id=icon_id, length_millis=length_millis)
        self.bind_screen_event(game=game, event=event, frames=[frame], icon_id=icon_id, value_optional=True)
        payload_frame = {f"line{i+1}": text for i, text in enumerate(lines)}
        self.send_event(game=game, event=event, value=1, frame=payload_frame)


def _frame_to_handler_data(frame: OledFrame) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    for line in frame.lines:
        line_data: dict[str, Any] = {
            "has-text": True,
            "prefix": "",
            "suffix": "",
            "bold": line.bold,
            "wrap": line.wrap,
        }
        if line.context_frame_key:
            line_data["context-frame-key"] = line.context_frame_key
        lines.append(line_data)

    return {
        "length-millis": frame.length_millis,
        "icon-id": frame.icon_id,
        "repeats": frame.repeats,
        "lines": lines,
    }


def _sanitize_token(value: str) -> str:
    safe = "".join(ch if (ch.isupper() or ch.isdigit() or ch in "-_") else "_" for ch in value.upper())
    return safe


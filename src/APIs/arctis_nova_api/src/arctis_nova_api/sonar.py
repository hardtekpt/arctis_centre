from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .core import DEFAULT_SONAR_DB_PATH, HttpClient, get_gg_encrypted_address, read_core_props
from .errors import ApiRequestError, ConfigDatabaseError, DiscoveryError, InvalidArgumentError
from .models import PresetChannel, SonarChannel, SonarPreset, StreamerSlider


class SonarClient:
    """Control Sonar channels and Sonar EQ preset selection."""

    def __init__(
        self,
        core_props_path: Path | None = None,
        sonar_db_path: Path | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._core_props_path = core_props_path
        self._sonar_db_path = sonar_db_path or DEFAULT_SONAR_DB_PATH
        self._http = HttpClient(timeout=timeout, verify_tls=False)
        self.gg_base_url: str = ""
        self.sonar_server_url: str = ""
        self.refresh_discovery()

    def refresh_discovery(self) -> None:
        core_props = read_core_props(self._core_props_path) if self._core_props_path else read_core_props()
        self.gg_base_url = get_gg_encrypted_address(core_props)

        sub_apps = self._http.request("GET", f"{self.gg_base_url}/subApps").json()
        sonar = sub_apps.get("subApps", {}).get("sonar")
        if not sonar:
            raise DiscoveryError("Sonar metadata not found in /subApps response")
        if not sonar.get("isEnabled"):
            raise DiscoveryError("Sonar is disabled in SteelSeries GG")
        if not sonar.get("isReady"):
            raise DiscoveryError("Sonar is not ready")
        if not sonar.get("isRunning"):
            raise DiscoveryError("Sonar is not running")

        web_server = sonar.get("metadata", {}).get("webServerAddress")
        if not web_server:
            raise DiscoveryError("Sonar web server address missing in subApps metadata")
        self.sonar_server_url = web_server.rstrip("/")

    def is_streamer_mode(self) -> bool:
        mode = self._http.request("GET", f"{self.sonar_server_url}/mode/").json()
        return mode == "stream"

    def set_streamer_mode(self, enabled: bool) -> bool:
        target = "stream" if enabled else "classic"
        current = self._http.request("PUT", f"{self.sonar_server_url}/mode/{target}").json()
        return current == "stream"

    def get_volume_data(self, streamer: bool | None = None) -> dict[str, Any]:
        paths = self._volume_get_paths(streamer)
        last_error: ApiRequestError | None = None
        fallback_empty_payload: dict[str, Any] | None = None
        for path in paths:
            try:
                payload = self._http.request("GET", f"{self.sonar_server_url}{path}").json()
                if self._looks_like_volume_payload(payload):
                    return payload
                if isinstance(payload, dict) and not payload:
                    fallback_empty_payload = payload
                    continue
                return payload
            except ApiRequestError as exc:
                last_error = exc
                continue
        if fallback_empty_payload is not None:
            return fallback_empty_payload
        if last_error:
            raise last_error
        raise InvalidArgumentError("Could not resolve Sonar volume endpoint")

    def get_channel_volume(
        self,
        channel: SonarChannel,
        streamer_slider: StreamerSlider = StreamerSlider.STREAMING,
        streamer: bool | None = None,
    ) -> float:
        volume_data = self.get_volume_data(streamer=streamer)
        mode = self._resolve_mode_key(streamer)

        # New payload style:
        # {
        #   "masters": {"classic": {"volume": ...}, "stream": {...}},
        #   "devices": {"game": {"classic": {"volume": ...}, "stream": {...}}, ...}
        # }
        new_style_value = self._extract_channel_volume_from_mode_payload(volume_data, channel, mode)
        if new_style_value is not None:
            return new_style_value

        # Legacy payload style fallbacks.
        if mode == "stream":
            channel_data = volume_data.get(streamer_slider.value, {}).get(channel.value, {})
            volume = self._extract_volume_value(channel_data)
            if volume is not None:
                return self._normalize_volume(volume)
        else:
            channel_data = volume_data.get(channel.value, {})
            volume = self._extract_volume_value(channel_data)
            if volume is not None:
                return self._normalize_volume(volume)

        # Newer Sonar payloads can be shaped like {"masters": [...], "devices": [...]}.
        mapped = self._extract_channel_volume_from_collections(volume_data, channel)
        if mapped is not None:
            return mapped

        raise InvalidArgumentError(
            f"Could not read volume for channel '{channel.value}'. Response keys: {list(volume_data.keys())}"
        )

    def set_channel_volume(
        self,
        channel: SonarChannel,
        volume: float,
        streamer_slider: StreamerSlider = StreamerSlider.STREAMING,
        streamer: bool | None = None,
    ) -> dict[str, Any]:
        if not 0 <= volume <= 1:
            raise InvalidArgumentError("volume must be between 0.0 and 1.0")
        mode = self._resolve_mode_key(streamer)
        candidates = self._volume_set_paths(
            channel=channel,
            mode=mode,
            key="volume",
            value=volume,
            streamer_slider=streamer_slider,
        )
        return self._put_first_success(candidates)

    def set_channel_mute(
        self,
        channel: SonarChannel,
        muted: bool,
        streamer_slider: StreamerSlider = StreamerSlider.STREAMING,
        streamer: bool | None = None,
    ) -> dict[str, Any]:
        mode = self._resolve_mode_key(streamer)
        candidates = self._volume_set_paths(
            channel=channel,
            mode=mode,
            key="muted",
            value=str(muted).lower(),
            streamer_slider=streamer_slider,
        )
        return self._put_first_success(candidates)

    def get_channel_mute(
        self,
        channel: SonarChannel,
        streamer_slider: StreamerSlider = StreamerSlider.STREAMING,
        streamer: bool | None = None,
    ) -> bool:
        volume_data = self.get_volume_data(streamer=streamer)
        mode = self._resolve_mode_key(streamer)

        new_style_value = self._extract_channel_mute_from_mode_payload(volume_data, channel, mode)
        if new_style_value is not None:
            return new_style_value

        if mode == "stream":
            channel_data = volume_data.get(streamer_slider.value, {}).get(channel.value, {})
            muted = self._extract_mute_value(channel_data)
            if muted is not None:
                return muted
        else:
            channel_data = volume_data.get(channel.value, {})
            muted = self._extract_mute_value(channel_data)
            if muted is not None:
                return muted

        mapped = self._extract_channel_mute_from_collections(volume_data, channel)
        if mapped is not None:
            return mapped

        raise InvalidArgumentError(
            f"Could not read mute state for channel '{channel.value}'. Response keys: {list(volume_data.keys())}"
        )

    def get_chat_mix(self) -> dict[str, Any]:
        return self._http.request("GET", f"{self.sonar_server_url}/chatMix").json()

    def set_chat_mix(self, balance: float) -> dict[str, Any]:
        if balance < -1 or balance > 1:
            raise InvalidArgumentError("balance must be between -1.0 and 1.0")
        return self._http.request("PUT", f"{self.sonar_server_url}/chatMix?balance={balance}").json()

    def get_routing_data(self) -> dict[str, Any] | list[Any]:
        """
        Return raw app routing data from Sonar.

        Sonar endpoint shape varies across GG versions, so this probes multiple
        known/observed routes and returns the first payload that looks usable.
        """
        paths = [
            "/AudioDeviceRouting",
            "/AudioDeviceRouting/",
            "/audioDeviceRouting",
            "/audioDeviceRouting/",
            "/Applications",
            "/Applications/",
            "/routing",
            "/routing/",
            "/routingSettings",
            "/routingSettings/",
            "/appRouting",
            "/appRouting/",
            "/audioRouting",
            "/audioRouting/",
            "/applications",
            "/applications/",
            "/sessions",
            "/sessions/",
            "/audioSessions",
            "/audioSessions/",
        ]
        last_error: ApiRequestError | None = None
        fallback_empty_payload: dict[str, Any] | list[Any] | None = None
        for path in paths:
            try:
                response = self._http.request("GET", f"{self.sonar_server_url}{path}")
                try:
                    payload = response.json()
                except ValueError:
                    # Some candidates can return non-JSON bodies; try the next path.
                    continue
                if isinstance(payload, (dict, list)):
                    if payload:
                        return payload
                    fallback_empty_payload = payload
            except ApiRequestError as exc:
                last_error = exc
                continue
        if fallback_empty_payload is not None:
            return fallback_empty_payload
        if last_error:
            raise last_error
        raise InvalidArgumentError("Could not resolve Sonar routing endpoint")

    def get_routed_apps_by_channel(self) -> dict[str, list[str]]:
        """
        Return app names routed to each Sonar channel.

        Keys are: master, game, chatRender, media, aux, chatCapture.
        """
        payload = self.get_routing_data()
        return self._extract_routed_apps_by_channel(payload)

    def list_presets(self, channel: PresetChannel) -> list[SonarPreset]:
        sql = "select id, name, vad from configs where vad = ? order by name collate nocase"
        rows = self._query_db(sql, (channel.value,))
        return [SonarPreset(preset_id=row[0], name=row[1], channel=PresetChannel(row[2])) for row in rows]

    def list_favorite_presets(self, channel: PresetChannel) -> list[SonarPreset]:
        favorite_col = self._detect_favorite_column()
        if favorite_col is None:
            return []

        sql = (
            f"select id, name, vad from configs "
            f"where vad = ? and {favorite_col} in (1, '1', true, 'true') "
            f"order by name collate nocase"
        )
        rows = self._query_db(sql, (channel.value,))
        return [SonarPreset(preset_id=row[0], name=row[1], channel=PresetChannel(row[2])) for row in rows]

    def list_favorite_presets_by_channel(self) -> dict[PresetChannel, list[SonarPreset]]:
        return {channel: self.list_favorite_presets(channel) for channel in PresetChannel}

    def get_selected_preset(self, channel: PresetChannel) -> SonarPreset | None:
        selected_rows = self._query_db(
            "select config_id from selected_config where vad = ?",
            (channel.value,),
        )
        if not selected_rows:
            return None
        selected_id = selected_rows[0][0]
        match_rows = self._query_db("select id, name, vad from configs where id = ?", (selected_id,))
        if not match_rows:
            return None
        row = match_rows[0]
        return SonarPreset(preset_id=row[0], name=row[1], channel=PresetChannel(row[2]))

    def select_preset(self, preset_id: str) -> None:
        self._http.request("PUT", f"{self._get_sonar_local_url()}/configs/{preset_id}/select", data="")

    def select_preset_for_channel(self, channel: PresetChannel, preset_name: str) -> SonarPreset:
        normalized_name = preset_name.strip().lower()
        for preset in self.list_presets(channel):
            if preset.name.lower() == normalized_name:
                self.select_preset(preset.preset_id)
                return preset
        raise InvalidArgumentError(f"Preset '{preset_name}' not found for {channel.name}")

    def _volume_path(
        self,
        streamer: bool | None,
        streamer_slider: StreamerSlider = StreamerSlider.STREAMING,
    ) -> str:
        if streamer is None:
            streamer = self.is_streamer_mode()
        base = "/volumeSettings/streamer" if streamer else "/volumeSettings/classic"
        if streamer:
            return f"{base}/{streamer_slider.value}"
        return base

    def _volume_get_paths(self, streamer: bool | None) -> list[str]:
        if streamer is None:
            return [
                "/volumeSettings",
                "/VolumeSettings",
                "/volumeSettings/classic",
                "/VolumeSettings/classic",
                "/volumeSettings/streamer",
                "/VolumeSettings/streamer",
            ]
        if streamer:
            return ["/volumeSettings/streamer", "/VolumeSettings/streamer", "/volumeSettings", "/VolumeSettings"]
        return ["/volumeSettings/classic", "/VolumeSettings/classic", "/volumeSettings", "/VolumeSettings"]

    def _resolve_mode_key(self, streamer: bool | None) -> str:
        active_stream = self.is_streamer_mode() if streamer is None else streamer
        return "stream" if active_stream else "classic"

    def _volume_set_paths(
        self,
        channel: SonarChannel,
        mode: str,
        key: str,
        value: float | str,
        streamer_slider: StreamerSlider,
    ) -> list[str]:
        section = "masters" if channel is SonarChannel.MASTER else f"devices/{channel.value}"
        candidates = [
            f"/volumeSettings/{section}/{mode}/{key}/{value}",
            f"/volumeSettings/{section}/{mode}/{key.capitalize()}/{value}",
            f"/VolumeSettings/{section}/{mode}/{key}/{value}",
            f"/VolumeSettings/{section}/{mode}/{key.capitalize()}/{value}",
        ]

        # Legacy endpoints.
        if mode == "stream":
            if key == "volume":
                candidates.append(
                    f"/volumeSettings/streamer/{streamer_slider.value}/{channel.value}/Volume/{value}"
                )
                candidates.append(
                    f"/VolumeSettings/streamer/{streamer_slider.value}/{channel.value}/Volume/{value}"
                )
            else:
                candidates.append(
                    f"/volumeSettings/streamer/{streamer_slider.value}/{channel.value}/isMuted/{value}"
                )
                candidates.append(
                    f"/VolumeSettings/streamer/{streamer_slider.value}/{channel.value}/isMuted/{value}"
                )
        else:
            if key == "volume":
                candidates.append(f"/volumeSettings/classic/{channel.value}/Volume/{value}")
                candidates.append(f"/VolumeSettings/classic/{channel.value}/Volume/{value}")
            else:
                candidates.append(f"/volumeSettings/classic/{channel.value}/Mute/{value}")
                candidates.append(f"/volumeSettings/classic/{channel.value}/muted/{value}")
                candidates.append(f"/VolumeSettings/classic/{channel.value}/Mute/{value}")
                candidates.append(f"/VolumeSettings/classic/{channel.value}/muted/{value}")
        return candidates

    def _put_first_success(self, paths: list[str]) -> dict[str, Any]:
        last_error: ApiRequestError | None = None
        fallback_empty_payload: dict[str, Any] | None = None
        for path in paths:
            try:
                payload = self._http.request("PUT", f"{self.sonar_server_url}{path}", data="").json()
                if isinstance(payload, dict) and not payload:
                    fallback_empty_payload = payload
                    continue
                return payload
            except ApiRequestError as exc:
                last_error = exc
                continue
        if fallback_empty_payload is not None:
            return fallback_empty_payload
        if last_error:
            raise last_error
        raise InvalidArgumentError("No volume endpoint candidates were generated")

    def _query_db(self, sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        if not self._sonar_db_path.exists():
            raise ConfigDatabaseError(f"Sonar database not found: {self._sonar_db_path}")
        try:
            with sqlite3.connect(self._sonar_db_path) as conn:
                return conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise ConfigDatabaseError(f"Failed querying Sonar DB: {exc}") from exc

    def _extract_routed_apps_by_channel(self, payload: Any) -> dict[str, list[str]]:
        channels = ("master", "game", "chatRender", "media", "aux", "chatCapture")
        routed: dict[str, list[str]] = {channel: [] for channel in channels}

        aliases: dict[str, set[str]] = {
            "master": {"master", "main"},
            "game": {"game", "gaming"},
            "chatRender": {"chatrender", "chat_render", "chat render", "render"},
            "media": {"media", "music"},
            "aux": {"aux", "auxiliary"},
            "chatCapture": {"chatcapture", "chat_capture", "mic", "microphone", "capture"},
        }

        def normalize_channel(value: Any) -> str | None:
            if not isinstance(value, str):
                return None
            normalized = value.lower().replace("-", "_")
            for channel, channel_aliases in aliases.items():
                if any(
                    alias in normalized
                    or alias in normalized.replace("_", "")
                    for alias in channel_aliases
                ):
                    return channel
            return None

        def app_name_from(item: dict[str, Any]) -> str | None:
            for key in ("name", "appName", "processName", "displayName", "title", "application", "exe", "executable"):
                value = item.get(key)
                if isinstance(value, str):
                    cleaned = value.strip()
                    if cleaned:
                        return cleaned
                if isinstance(value, dict):
                    nested = value.get("name")
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
            return None

        def channel_from(item: dict[str, Any]) -> str | None:
            for key in ("role", "channel", "deviceRole", "output", "route", "routedTo", "dest", "destination", "assignedTo"):
                value = item.get(key)
                if isinstance(value, str):
                    channel = normalize_channel(value)
                    if channel:
                        return channel
                if isinstance(value, dict):
                    for nested_key in ("role", "channel", "name", "id", "value"):
                        nested_value = value.get(nested_key)
                        channel = normalize_channel(nested_value)
                        if channel:
                            return channel
            return None

        def collect_entries(node: Any) -> list[dict[str, Any]]:
            entries: list[dict[str, Any]] = []
            if isinstance(node, dict):
                for key in ("applications", "apps", "sessions", "processes", "items", "routes"):
                    value = node.get(key)
                    if isinstance(value, list):
                        entries.extend([entry for entry in value if isinstance(entry, dict)])
                # Some payloads map channels directly to app lists.
                for key, value in node.items():
                    mapped_channel = normalize_channel(key)
                    if mapped_channel and isinstance(value, list):
                        for app in value:
                            if isinstance(app, str):
                                routed[mapped_channel].append(app)
                            elif isinstance(app, dict):
                                named = app_name_from(app)
                                if named:
                                    routed[mapped_channel].append(named)
                    if isinstance(value, (dict, list)):
                        entries.extend(collect_entries(value))
            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, dict):
                        entries.append(item)
                        entries.extend(collect_entries(item))
            return entries

        for entry in collect_entries(payload):
            app_name = app_name_from(entry)
            channel = channel_from(entry)
            if app_name and channel:
                routed[channel].append(app_name)
                continue
            # Newer payload style from /AudioDeviceRouting:
            # [{"role": "game", "audioSessions": [{"processName": "..."}]}]
            sessions = entry.get("audioSessions")
            if channel and isinstance(sessions, list):
                session_names: list[str] = []
                for session in sessions:
                    if not isinstance(session, dict):
                        continue
                    # Prefer truly active app sessions for near real-time updates.
                    state = session.get("state")
                    if isinstance(state, str) and state.strip().lower() not in {"active", "running"}:
                        continue
                    if session.get("isSystemSound") is True:
                        continue
                    process_id = session.get("processId")
                    if isinstance(process_id, int) and process_id <= 0:
                        continue
                    name = app_name_from(session)
                    if name:
                        session_names.append(name)
                routed[channel].extend(session_names)

        for channel in routed:
            seen: set[str] = set()
            unique: list[str] = []
            for app in routed[channel]:
                if app not in seen:
                    seen.add(app)
                    unique.append(app)
            routed[channel] = unique
        return routed

    def _detect_favorite_column(self) -> str | None:
        rows = self._query_db("pragma table_info(configs)", ())
        column_names = {str(row[1]).lower(): str(row[1]) for row in rows if len(row) > 1}
        for candidate in ("is_favorite", "favorite", "starred", "is_starred", "isfavorite"):
            if candidate in column_names:
                return column_names[candidate]
        return None

    def _extract_channel_volume_from_mode_payload(
        self,
        payload: dict[str, Any],
        channel: SonarChannel,
        mode: str,
    ) -> float | None:
        if channel is SonarChannel.MASTER:
            masters = payload.get("masters")
            if isinstance(masters, dict):
                mode_entry = masters.get(mode, {})
                if isinstance(mode_entry, dict):
                    volume = self._extract_volume_value(mode_entry)
                    if volume is not None:
                        return self._normalize_volume(volume)
            return None

        devices = payload.get("devices")
        if isinstance(devices, dict):
            device_entry = devices.get(channel.value)
            if isinstance(device_entry, dict):
                mode_entry = device_entry.get(mode, {})
                if isinstance(mode_entry, dict):
                    volume = self._extract_volume_value(mode_entry)
                    if volume is not None:
                        return self._normalize_volume(volume)
        return None

    def _extract_channel_mute_from_mode_payload(
        self,
        payload: dict[str, Any],
        channel: SonarChannel,
        mode: str,
    ) -> bool | None:
        if channel is SonarChannel.MASTER:
            masters = payload.get("masters")
            if isinstance(masters, dict):
                mode_entry = masters.get(mode, {})
                if isinstance(mode_entry, dict):
                    muted = self._extract_mute_value(mode_entry)
                    if muted is not None:
                        return muted
            return None

        devices = payload.get("devices")
        if isinstance(devices, dict):
            device_entry = devices.get(channel.value)
            if isinstance(device_entry, dict):
                mode_entry = device_entry.get(mode, {})
                if isinstance(mode_entry, dict):
                    muted = self._extract_mute_value(mode_entry)
                    if muted is not None:
                        return muted
        return None

    def _extract_channel_volume_from_collections(self, payload: dict[str, Any], channel: SonarChannel) -> float | None:
        aliases_by_channel: dict[SonarChannel, set[str]] = {
            SonarChannel.MASTER: {"master", "main"},
            SonarChannel.GAME: {"game", "gaming"},
            SonarChannel.CHAT_RENDER: {"chatrender", "chat_render", "chat"},
            SonarChannel.MEDIA: {"media", "music"},
            SonarChannel.AUX: {"aux", "auxiliary"},
            SonarChannel.CHAT_CAPTURE: {"chatcapture", "chat_capture", "mic", "microphone", "capture"},
        }

        collections: list[Any] = []
        for key in ("devices", "masters"):
            value = payload.get(key)
            if isinstance(value, list):
                collections.append(value)

        for collection in collections:
            for item in collection:
                if not isinstance(item, dict):
                    continue
                if self._item_matches_channel(item, aliases_by_channel[channel]):
                    volume = self._extract_volume_value(item)
                    if volume is not None:
                        return self._normalize_volume(volume)

        # Fallback for some payloads where "masters" contains only a single global master item.
        if channel is SonarChannel.MASTER and isinstance(payload.get("masters"), list) and payload["masters"]:
            first = payload["masters"][0]
            if isinstance(first, dict):
                volume = self._extract_volume_value(first)
                if volume is not None:
                    return self._normalize_volume(volume)
        return None

    def _extract_channel_mute_from_collections(self, payload: dict[str, Any], channel: SonarChannel) -> bool | None:
        aliases_by_channel: dict[SonarChannel, set[str]] = {
            SonarChannel.MASTER: {"master", "main"},
            SonarChannel.GAME: {"game", "gaming"},
            SonarChannel.CHAT_RENDER: {"chatrender", "chat_render", "chat"},
            SonarChannel.MEDIA: {"media", "music"},
            SonarChannel.AUX: {"aux", "auxiliary"},
            SonarChannel.CHAT_CAPTURE: {"chatcapture", "chat_capture", "mic", "microphone", "capture"},
        }

        collections: list[Any] = []
        for key in ("devices", "masters"):
            value = payload.get(key)
            if isinstance(value, list):
                collections.append(value)

        for collection in collections:
            for item in collection:
                if not isinstance(item, dict):
                    continue
                if self._item_matches_channel(item, aliases_by_channel[channel]):
                    muted = self._extract_mute_value(item)
                    if muted is not None:
                        return muted

        if channel is SonarChannel.MASTER and isinstance(payload.get("masters"), list) and payload["masters"]:
            first = payload["masters"][0]
            if isinstance(first, dict):
                muted = self._extract_mute_value(first)
                if muted is not None:
                    return muted
        return None

    @staticmethod
    def _item_matches_channel(item: dict[str, Any], aliases: set[str]) -> bool:
        searchable_values: list[str] = []
        for key, value in item.items():
            if isinstance(value, str):
                searchable_values.append(value)
            if isinstance(key, str):
                searchable_values.append(key)
        normalized = " ".join(searchable_values).lower().replace("-", "_")
        tokens = {
            token.strip("_")
            for part in normalized.split()
            for token in part.replace("/", "_").split("_")
            if token.strip("_")
        }
        return any(alias in tokens or alias in normalized for alias in aliases)

    @staticmethod
    def _extract_volume_value(item: dict[str, Any]) -> float | None:
        for key in ("Volume", "volume", "value", "level", "gain", "slider"):
            if key in item:
                value = item[key]
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, dict):
                    nested = value.get("value")
                    if isinstance(nested, (int, float)):
                        return float(nested)
        return None

    @staticmethod
    def _extract_mute_value(item: dict[str, Any]) -> bool | None:
        for key in ("muted", "isMuted", "Mute", "mute"):
            if key not in item:
                continue
            value = item[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
        return None

    @staticmethod
    def _normalize_volume(volume: float) -> float:
        # API variants return either 0..1 or 0..100.
        if 1 < volume <= 100:
            return volume / 100.0
        return volume

    @staticmethod
    def _looks_like_volume_payload(payload: Any) -> bool:
        if not isinstance(payload, dict):
            return False
        if "masters" in payload or "devices" in payload:
            return True
        known = {"master", "game", "chatRender", "chatCapture", "media", "aux", "streaming", "monitoring"}
        return any(k in payload for k in known)

    def _get_sonar_local_url(self) -> str:
        parsed = urlparse(self.sonar_server_url)
        if not parsed.hostname or not parsed.port:
            raise DiscoveryError(f"Could not parse Sonar server URL: {self.sonar_server_url}")
        return f"http://{parsed.hostname}:{parsed.port}"

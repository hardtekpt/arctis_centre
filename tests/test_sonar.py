from __future__ import annotations

import sqlite3

from arctis_nova_api.models import PresetChannel, SonarChannel
from arctis_nova_api.sonar import SonarClient


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.text = ""

    def json(self):
        return self.payload


class _FakeHttpClient:
    def __init__(self, *args, **kwargs):
        self.calls = []
        self.subapps_payload = {
            "subApps": {
                "sonar": {
                    "isEnabled": True,
                    "isReady": True,
                    "isRunning": True,
                    "metadata": {"webServerAddress": "http://localhost:5566"},
                }
            }
        }

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/subApps"):
            return _FakeResponse(self.subapps_payload)
        if url.endswith("/mode/"):
            return _FakeResponse("classic")
        return _FakeResponse({})


def test_list_and_select_presets(monkeypatch, tmp_path):
    import arctis_nova_api.sonar as sonar_module

    monkeypatch.setattr(
        sonar_module,
        "read_core_props",
        lambda *args, **kwargs: {"ggEncryptedAddress": "127.0.0.1:9999"},
    )
    fake_http = _FakeHttpClient()
    monkeypatch.setattr(sonar_module, "HttpClient", lambda *args, **kwargs: fake_http)

    db = tmp_path / "database.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            create table configs (id text, name text, vad integer, is_favorite integer);
            create table selected_config (config_id text, vad integer);
            insert into configs values ('id_1', 'Flat', 1, 0);
            insert into configs values ('id_2', 'Footsteps', 1, 1);
            insert into selected_config values ('id_1', 1);
            """
        )

    client = SonarClient(sonar_db_path=db)
    presets = client.list_presets(PresetChannel.GAMING)
    assert len(presets) == 2
    favorites = client.list_favorite_presets(PresetChannel.GAMING)
    assert len(favorites) == 1
    assert favorites[0].name == "Footsteps"
    assert client.get_selected_preset(PresetChannel.GAMING).preset_id == "id_1"
    client.select_preset("id_2")
    assert any(call[1].endswith("/configs/id_2/select") for call in fake_http.calls)


def test_get_channel_volume_from_devices_payload(monkeypatch, tmp_path):
    import arctis_nova_api.sonar as sonar_module

    monkeypatch.setattr(
        sonar_module,
        "read_core_props",
        lambda *args, **kwargs: {"ggEncryptedAddress": "127.0.0.1:9999"},
    )

    class _DevicesPayloadHttp(_FakeHttpClient):
        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            if url.endswith("/subApps"):
                return _FakeResponse(self.subapps_payload)
            if url.endswith("/mode/"):
                return _FakeResponse("classic")
            if "/volumeSettings/classic" in url:
                return _FakeResponse(
                    {
                        "masters": [{"name": "master", "volume": 76}],
                        "devices": [
                            {"role": "game", "volume": 65},
                            {"role": "chatRender", "volume": 44},
                            {"role": "media", "volume": 31},
                            {"role": "aux", "volume": 55},
                            {"role": "chatCapture", "volume": 82},
                        ],
                    }
                )
            return _FakeResponse({})

    fake_http = _DevicesPayloadHttp()
    monkeypatch.setattr(sonar_module, "HttpClient", lambda *args, **kwargs: fake_http)

    db = tmp_path / "database.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            create table configs (id text, name text, vad integer);
            create table selected_config (config_id text, vad integer);
            """
        )

    client = SonarClient(sonar_db_path=db)
    assert client.get_channel_volume(SonarChannel.MASTER) == 0.76
    assert client.get_channel_volume(SonarChannel.GAME) == 0.65
    assert client.get_channel_volume(SonarChannel.CHAT_RENDER) == 0.44
    assert client.get_channel_volume(SonarChannel.MEDIA) == 0.31
    assert client.get_channel_volume(SonarChannel.AUX) == 0.55
    assert client.get_channel_volume(SonarChannel.CHAT_CAPTURE) == 0.82


def test_get_channel_volume_from_mode_payload_dict(monkeypatch, tmp_path):
    import arctis_nova_api.sonar as sonar_module

    monkeypatch.setattr(
        sonar_module,
        "read_core_props",
        lambda *args, **kwargs: {"ggEncryptedAddress": "127.0.0.1:9999"},
    )

    class _ModePayloadHttp(_FakeHttpClient):
        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            if url.endswith("/subApps"):
                return _FakeResponse(self.subapps_payload)
            if url.endswith("/mode/"):
                return _FakeResponse("classic")
            if url.endswith("/volumeSettings/classic") or url.endswith("/volumeSettings"):
                return _FakeResponse(
                    {
                        "masters": {"stream": {}, "classic": {"volume": 1.0, "muted": False}},
                        "devices": {
                            "game": {"stream": {}, "classic": {"volume": 0.72, "muted": False}},
                            "chatRender": {"stream": {}, "classic": {"volume": 0.68571436, "muted": False}},
                            "chatCapture": {"stream": {}, "classic": {"volume": 1.0, "muted": False}},
                            "media": {"stream": {}, "classic": {"volume": 1.0, "muted": False}},
                            "aux": {"stream": {}, "classic": {"volume": 0.016926112, "muted": False}},
                        },
                    }
                )
            return _FakeResponse({})

    fake_http = _ModePayloadHttp()
    monkeypatch.setattr(sonar_module, "HttpClient", lambda *args, **kwargs: fake_http)

    db = tmp_path / "database.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            create table configs (id text, name text, vad integer);
            create table selected_config (config_id text, vad integer);
            """
        )

    client = SonarClient(sonar_db_path=db)
    assert client.get_channel_volume(SonarChannel.MASTER) == 1.0
    assert client.get_channel_volume(SonarChannel.GAME) == 0.72
    assert client.get_channel_volume(SonarChannel.CHAT_RENDER) == 0.68571436
    assert client.get_channel_volume(SonarChannel.CHAT_CAPTURE) == 1.0
    assert client.get_channel_volume(SonarChannel.MEDIA) == 1.0
    assert client.get_channel_volume(SonarChannel.AUX) == 0.016926112


def test_set_volume_endpoint_fallback(monkeypatch, tmp_path):
    import arctis_nova_api.sonar as sonar_module

    monkeypatch.setattr(
        sonar_module,
        "read_core_props",
        lambda *args, **kwargs: {"ggEncryptedAddress": "127.0.0.1:9999"},
    )

    class _PutFallbackHttp(_FakeHttpClient):
        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            if url.endswith("/subApps"):
                return _FakeResponse(self.subapps_payload)
            if url.endswith("/mode/"):
                return _FakeResponse("classic")
            if method == "PUT" and "/volumeSettings/devices/game/classic/volume/" in url:
                raise sonar_module.ApiRequestError("not found", status_code=404)
            if method == "PUT" and "/volumeSettings/classic/game/Volume/" in url:
                return _FakeResponse({"ok": True})
            return _FakeResponse({})

    fake_http = _PutFallbackHttp()
    monkeypatch.setattr(sonar_module, "HttpClient", lambda *args, **kwargs: fake_http)

    db = tmp_path / "database.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(
            """
            create table configs (id text, name text, vad integer);
            create table selected_config (config_id text, vad integer);
            """
        )

    client = SonarClient(sonar_db_path=db)
    result = client.set_channel_volume(SonarChannel.GAME, 0.5)
    assert result["ok"] is True
    assert any("/volumeSettings/devices/game/classic/volume/0.5" in call[1] for call in fake_http.calls)
    assert any("/volumeSettings/classic/game/Volume/0.5" in call[1] for call in fake_http.calls)

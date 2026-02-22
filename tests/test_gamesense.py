from __future__ import annotations

from arctis_nova_api.gamesense import GameSenseClient
from arctis_nova_api.models import OledFrame, OledLine


class _FakeResponse:
    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {}
        self.status_code = 200
        self.text = ""

    def json(self):
        return self._payload


class _FakeHttpClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return _FakeResponse()


def test_bind_and_send_oled_text(monkeypatch):
    import arctis_nova_api.gamesense as gs

    monkeypatch.setattr(gs, "read_core_props", lambda *args, **kwargs: {"address": "127.0.0.1:1111"})
    fake_http = _FakeHttpClient()
    monkeypatch.setattr(gs, "HttpClient", lambda *args, **kwargs: fake_http)

    client = GameSenseClient()
    frame = OledFrame(lines=[OledLine(text="A", context_frame_key="line1")], length_millis=1000)
    client.bind_screen_event("demo app", "my event", [frame])
    client.send_event("demo app", "my event", value=7, frame={"line1": "Hello"})

    assert len(fake_http.calls) == 2
    bind_call = fake_http.calls[0]
    assert bind_call[0] == "POST"
    assert bind_call[1].endswith("/bind_game_event")
    payload = bind_call[2]["json"]
    assert payload["game"] == "DEMO_APP"
    assert payload["event"] == "MY_EVENT"
    assert payload["handlers"][0]["mode"] == "screen"


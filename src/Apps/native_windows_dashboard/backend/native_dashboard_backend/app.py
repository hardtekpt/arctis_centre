from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .models import ChannelMuteRequest, ChannelPresetRequest, ChannelVolumeRequest, ServiceStatus
from .runtime import CHANNELS, DashboardRuntime


def create_app(runtime: DashboardRuntime | None = None) -> FastAPI:
    app = FastAPI(title="Native Dashboard Backend", version="1.0.0")
    app_runtime = runtime or DashboardRuntime()

    @app.on_event("startup")
    def _startup() -> None:
        app_runtime.start()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        app_runtime.stop()

    @app.get("/health", response_model=ServiceStatus)
    def health() -> ServiceStatus:
        state = app_runtime.get_state()
        return ServiceStatus(ok=state.get("status") == "running", detail=state.get("last_error", ""))

    @app.get("/state")
    def get_state() -> dict:
        return app_runtime.get_state()

    @app.get("/presets")
    def get_presets() -> dict:
        return app_runtime.get_presets()

    @app.post("/actions/channel-volume", response_model=ServiceStatus)
    def set_channel_volume(body: ChannelVolumeRequest) -> ServiceStatus:
        if body.channel not in CHANNELS:
            raise HTTPException(status_code=400, detail=f"Unsupported channel: {body.channel}")
        app_runtime.set_channel_volume(body.channel, body.value)
        return ServiceStatus(ok=True, detail="volume updated")

    @app.post("/actions/channel-mute", response_model=ServiceStatus)
    def set_channel_mute(body: ChannelMuteRequest) -> ServiceStatus:
        if body.channel not in CHANNELS:
            raise HTTPException(status_code=400, detail=f"Unsupported channel: {body.channel}")
        app_runtime.set_channel_mute(body.channel, body.muted)
        return ServiceStatus(ok=True, detail="mute updated")

    @app.post("/actions/channel-preset", response_model=ServiceStatus)
    def set_channel_preset(body: ChannelPresetRequest) -> ServiceStatus:
        if body.channel not in CHANNELS:
            raise HTTPException(status_code=400, detail=f"Unsupported channel: {body.channel}")
        app_runtime.set_channel_preset(body.channel, body.preset_id)
        return ServiceStatus(ok=True, detail="preset updated")

    return app

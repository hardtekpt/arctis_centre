from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelVolumeRequest(BaseModel):
    channel: str
    value: int = Field(ge=0, le=100)


class ChannelMuteRequest(BaseModel):
    channel: str
    muted: bool


class ChannelPresetRequest(BaseModel):
    channel: str
    preset_id: str


class ServiceStatus(BaseModel):
    ok: bool
    detail: str = ""

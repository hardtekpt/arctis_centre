from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from .errors import ApiRequestError, DiscoveryError

DEFAULT_CORE_PROPS_PATH = (
    Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    / "SteelSeries"
    / "SteelSeries Engine 3"
    / "coreProps.json"
)
DEFAULT_SONAR_DB_PATH = (
    Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    / "SteelSeries"
    / "GG"
    / "apps"
    / "sonar"
    / "db"
    / "database.db"
)


def read_core_props(path: Path = DEFAULT_CORE_PROPS_PATH) -> dict[str, Any]:
    if not path.exists():
        raise DiscoveryError(f"SteelSeries coreProps.json not found at: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiscoveryError(f"Invalid JSON in coreProps file: {path}") from exc


def get_gamesense_address(core_props: dict[str, Any]) -> str:
    address = core_props.get("address")
    if not address:
        raise DiscoveryError("coreProps.json does not include 'address'")
    return f"http://{address}"


def get_gg_encrypted_address(core_props: dict[str, Any]) -> str:
    address = core_props.get("ggEncryptedAddress")
    if not address:
        raise DiscoveryError("coreProps.json does not include 'ggEncryptedAddress'")
    return f"https://{address}"


class HttpClient:
    """Small helper around requests with consistent error handling."""

    def __init__(self, timeout: float = 5.0, verify_tls: bool = False) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.verify_tls = verify_tls

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify_tls)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise ApiRequestError(f"Request failed for {method} {url}") from exc

        if response.status_code >= 400:
            raise ApiRequestError(
                f"{method} {url} returned HTTP {response.status_code}: {response.text}",
                status_code=response.status_code,
            )
        return response


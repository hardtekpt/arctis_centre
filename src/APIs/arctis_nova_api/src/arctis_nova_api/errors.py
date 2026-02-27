class ArctisNovaError(Exception):
    """Base exception for this package."""


class DiscoveryError(ArctisNovaError):
    """Raised when SteelSeries services cannot be discovered."""


class ApiRequestError(ArctisNovaError):
    """Raised when an HTTP request to SteelSeries services fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class ConfigDatabaseError(ArctisNovaError):
    """Raised when Sonar's SQLite database cannot be queried."""


class InvalidArgumentError(ArctisNovaError):
    """Raised for invalid method arguments."""


class UnsupportedFeatureError(ArctisNovaError):
    """Raised when a feature is unavailable on a specific firmware/device."""


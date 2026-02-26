from __future__ import annotations

import uvicorn

from native_dashboard_backend import create_app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=59231, log_level="info")


if __name__ == "__main__":
    main()

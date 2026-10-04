from __future__ import annotations

import uvicorn

from .api import create_control_plane


def serve(host: str = "127.0.0.1", port: int = 8766) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("control plane must bind to localhost")
    uvicorn.run(create_control_plane(), host=host, port=port, log_level="info")

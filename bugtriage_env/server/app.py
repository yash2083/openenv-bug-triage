# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Bugtriage Env Environment.

This module creates an HTTP server that exposes the BugtriageEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import BugtriageAction, BugtriageObservation
    from .bugtriage_env_environment import BugtriageEnvironment
except (ImportError, ModuleNotFoundError):
    from models import BugtriageAction, BugtriageObservation
    from server.bugtriage_env_environment import BugtriageEnvironment


# Create the app with web interface and README integration
app = create_app(
    BugtriageEnvironment,
    BugtriageAction,
    BugtriageObservation,
    env_name="bugtriage_env",
    max_concurrent_envs=1,  # increase this number to allow more concurrent WebSocket sessions
)


def main(host: str = "0.0.0.0", port: int = 8000):
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run --project . server --port 8001
        python -m bugtriage_env.server.app

    Args:
        host: Host address to bind to (default: "0.0.0.0")
        port: Port number to listen on (default: 8000)

    For production deployments, consider using uvicorn directly with
    multiple workers:
        uvicorn bugtriage_env.server.app:app --workers 4
    """
    import sys
    import uvicorn

    # Support --port CLI arg when invoked as a script entry point.
    # openenv validate requires main() to be callable with no arguments;
    # defaults above (host="0.0.0.0", port=8000) satisfy that requirement.
    _port = port
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default=host)
        parser.add_argument("--port", type=int, default=port)
        args, _ = parser.parse_known_args()
        _port = args.port
        host = args.host

    uvicorn.run(app, host=host, port=_port)


if __name__ == "__main__":
    main()  # all CLI arg parsing happens inside main()

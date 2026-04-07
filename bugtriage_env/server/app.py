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


# Add a welcome page at the root path
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def root():
    """Welcome page for the Bug Triage OpenEnv environment."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bug Triage OpenEnv</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                line-height: 1.6;
                color: #333;
            }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; margin-top: 30px; }
            .endpoint { background: #f8f9fa; padding: 10px; border-left: 4px solid #3498db; margin: 10px 0; }
            .endpoint code { color: #e74c3c; font-weight: bold; }
            a { color: #3498db; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .badge { background: #27ae60; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <h1>🐛 Bug Triage OpenEnv</h1>
        <p><span class="badge">✓ Running</span></p>

        <p>This is an <strong>OpenEnv-compatible environment</strong> for evaluating AI agents on bug/issue triage tasks.</p>

        <h2>📚 API Documentation</h2>
        <p>View the interactive API documentation: <a href="/docs">/docs</a></p>

        <h2>🔌 Available Endpoints</h2>

        <div class="endpoint">
            <code>GET /health</code><br>
            Health check endpoint
        </div>

        <div class="endpoint">
            <code>POST /reset</code><br>
            Initialize a new episode with a random issue from the task set
        </div>

        <div class="endpoint">
            <code>POST /step</code><br>
            Execute an action and receive the next observation
        </div>

        <div class="endpoint">
            <code>GET /state</code><br>
            Get the current environment state
        </div>

        <h2>🚀 Quick Test</h2>
        <p>Try these commands:</p>
        <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto;">
# Health check
curl https://Mohit2EZ-bugtriage-openenv.hf.space/health

# Start a new episode
curl -X POST https://Mohit2EZ-bugtriage-openenv.hf.space/reset

# Take an action
curl -X POST https://Mohit2EZ-bugtriage-openenv.hf.space/step \\
  -H "Content-Type: application/json" \\
  -d '{"action_type": "SetSeverity", "severity": "S1_major"}'
        </pre>

        <h2>📖 Learn More</h2>
        <p>
            <a href="https://huggingface.co/spaces/Mohit2EZ/bugtriage-openenv">View on Hugging Face</a> •
            <a href="/docs">API Documentation</a>
        </p>
    </body>
    </html>
    """


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

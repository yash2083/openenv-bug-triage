# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
FastAPI application for the Bugtriage Env Environment with session management.

This module creates an HTTP server that exposes the BugtriageEnvironment
over HTTP endpoints with proper session state management.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /health: Health check

Usage:
    uvicorn server.app:app --host 0.0.0.0 --port 8000
"""

try:
    from ..models import BugtriageAction, BugtriageObservation
    from .bugtriage_env_environment import BugtriageEnvironment
except (ImportError, ModuleNotFoundError):
    from models import BugtriageAction, BugtriageObservation
    from server.bugtriage_env_environment import BugtriageEnvironment

from fastapi import FastAPI, Response, Header, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import uuid

# Session management
class SessionManager:
    """Manages environment sessions for HTTP REST endpoints."""

    def __init__(self, session_timeout_minutes: int = 30):
        self._sessions: Dict[str, tuple[BugtriageEnvironment, datetime]] = {}
        self._timeout = timedelta(minutes=session_timeout_minutes)

    def create_session(self) -> tuple[str, BugtriageEnvironment]:
        """Create a new session and return session ID and environment."""
        session_id = str(uuid.uuid4())
        env = BugtriageEnvironment()
        self._sessions[session_id] = (env, datetime.now())
        return session_id, env

    def get_session(self, session_id: Optional[str]) -> tuple[str, BugtriageEnvironment]:
        """Get existing session or create new one if not found."""
        if session_id and session_id in self._sessions:
            env, last_access = self._sessions[session_id]
            if datetime.now() - last_access < self._timeout:
                self._sessions[session_id] = (env, datetime.now())
                return session_id, env
            else:
                env.close()
                del self._sessions[session_id]
        return self.create_session()

    def close_session(self, session_id: str):
        """Close and remove a session."""
        if session_id in self._sessions:
            env, _ = self._sessions[session_id]
            env.close()
            del self._sessions[session_id]

session_manager = SessionManager()

# Create FastAPI app
app = FastAPI(
    title="Bug Triage OpenEnv",
    description="OpenEnv environment for bug/issue triage tasks with session management",
    version="1.0.0"
)

# Helper to serialize observation
def serialize_obs(obs: BugtriageObservation) -> dict:
    """Serialize observation to dict."""
    return obs.model_dump(mode='json')

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/reset")
async def reset(response: Response, x_session_id: Optional[str] = Header(None)):
    """Reset environment and return initial observation."""
    sid, env = session_manager.get_session(x_session_id)
    obs = env.reset()
    response.headers["X-Session-ID"] = sid
    return {
        "observation": serialize_obs(obs),
        "reward": 0.0,
        "done": False
    }

@app.post("/step")
async def step(
    request: dict,
    response: Response,
    x_session_id: Optional[str] = Header(None)
):
    """Execute action and return observation."""
    sid, env = session_manager.get_session(x_session_id)
    response.headers["X-Session-ID"] = sid

    # Parse action
    action_data = request.get("action", request)
    try:
        action = BugtriageAction(**action_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Execute step
    obs = env.step(action)
    return serialize_obs(obs)

@app.get("/state")
async def get_state(response: Response, x_session_id: Optional[str] = Header(None)):
    """Get current environment state."""
    sid, env = session_manager.get_session(x_session_id)
    response.headers["X-Session-ID"] = sid
    # Access _state directly since state() returns State object
    return {
        "episode_id": env._state.episode_id,
        "step_count": env._state.step_count,
        "done": env._done,
        "cumulative_reward": env._cumulative_reward,
        "agent_decisions": env._agent_decisions
    }

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
            .note { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🐛 Bug Triage OpenEnv</h1>
        <p><span class="badge">✓ Running</span></p>

        <p>This is an <strong>OpenEnv-compatible environment</strong> for evaluating AI agents on bug/issue triage tasks.</p>

        <div class="note">
            <strong>Session Management:</strong> This environment uses session-based state management.
            Include the <code>X-Session-ID</code> header in your requests to maintain state across calls.
            The server will return a session ID in the response headers.
        </div>

        <h2>📚 API Documentation</h2>
        <p>View the interactive API documentation: <a href="/docs">/docs</a></p>

        <h2>🔌 Available Endpoints</h2>

        <div class="endpoint">
            <code>GET /health</code><br>
            Health check endpoint
        </div>

        <div class="endpoint">
            <code>POST /reset</code><br>
            Initialize a new episode. Returns session ID in <code>X-Session-ID</code> header.
        </div>

        <div class="endpoint">
            <code>POST /step</code><br>
            Execute an action. Include <code>X-Session-ID</code> header to maintain state.
        </div>

        <div class="endpoint">
            <code>GET /state</code><br>
            Get current environment state. Include <code>X-Session-ID</code> header.
        </div>

        <h2>🚀 Quick Test</h2>
        <p>Try these commands:</p>
        <pre style="background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto;">
# Reset and capture session ID
SESSION_ID=$(curl -s -X POST https://Mohit2EZ-bugtriage-openenv.hf.space/reset -D - | grep -i x-session-id | cut -d' ' -f2 | tr -d '\\r')

# Take an action with session ID
curl -X POST https://Mohit2EZ-bugtriage-openenv.hf.space/step \\
  -H "Content-Type: application/json" \\
  -H "X-Session-ID: $SESSION_ID" \\
  -d '{"action": {"action_type": "SetSeverity", "severity": "S1_major"}}'

# Check state
curl https://Mohit2EZ-bugtriage-openenv.hf.space/state \\
  -H "X-Session-ID: $SESSION_ID"
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
    """Entry point for direct execution."""
    import sys
    import uvicorn

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
    main()

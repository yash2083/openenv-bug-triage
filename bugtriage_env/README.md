# bugtriage_env: OpenEnv Environment Package

This directory contains the core implementation of the **Bug/Issue Triage OpenEnv** environment.

---

## 🏗 Package Structure

```text
bugtriage_env/
├── openenv.yaml         # OpenEnv manifest
├── pyproject.toml       # Dependencies (uv/pip)
├── client.py            # Typed client for agent integration
├── models.py            # Pydantic Action and Observation schemas
└── server/
    ├── app.py           # FastAPI server with WebSocket support
    ├── bugtriage_env_environment.py # Core logic and state management
    └── Dockerfile       # Container definition (build context: /app/env)
```

---

## 🚀 Getting Started

For full project documentation, setup guides, and "golden commands," please refer to the **[Root README](../README.md)**.

### Core Endpoints
- **`GET /health`**: Health monitor.
- **`POST /reset`**: Initializes a new episode based on `TASK_SET`.
- **`POST /step`**: Processes the agent's action and returns an observation.
- **`GET /state`**: (Internal/Debug) Returns full environment status.

---

## 📜 Development & Testing

The environment logic is located in `server/bugtriage_env_environment.py`. It is designed to be **fully deterministic** and contains no external LLM dependencies.

### Environment Schema
| Type | Detail |
| :--- | :--- |
| **Action** | `BugtriageAction` (Discriminator: `action_type`) |
| **Observation** | `BugtriageObservation` (Typed Pydantic model) |

Full schema details are available in [docs/ACTIONS_OBS_SCHEMA.md](../docs/ACTIONS_OBS_SCHEMA.md).

### Local Execution (Manual)
To start just the environment server:
```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

To run logic-specific unit tests:
```bash
pytest ../tests/ -v
```

---

## 🐳 Docker Build

When building the Docker image, ensure the context is the `bugtriage_env/` directory:

```bash
docker build -f server/Dockerfile -t bugtriage-openenv .
```

---

## ✅ OpenEnv Validation

This package is designed to pass the official OpenEnv validation suite:

```bash
openenv validate
```

> [!IMPORTANT]
> The environment expects access to `tasks/` and `examples/` directories at runtime. These are searched relative to the environment file and the current working directory for maximum flexibility across local and containerized deployments.

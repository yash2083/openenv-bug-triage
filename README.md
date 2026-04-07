# Bug/Issue Triage OpenEnv

[![OpenEnv Compatible](https://img.shields.io/badge/OpenEnv-Compatible-green.svg)](https://github.com/meta-pytorch/openenv)
[![License](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](CONTRIBUTING.md)

**Bug/Issue Triage OpenEnv** is a high-fidelity [OpenEnv](https://github.com/meta-pytorch/openenv) compatible environment designed to evaluate AI agents on the real-world task of **Bug and Issue Triage**.

In modern software engineering, triaging incoming reports is a critical but time-consuming process. This system provides a deterministic, structured environment where agents must analyze issue reports (like Jira/GitHub issues), ask for clarifications, classify problems, and assign them to the correct teams with appropriate severity.

---

## 🚀 Quick Summary

- **What it is**: A simulated bug triage environment for AI agents.
- **Why it matters**: Automating triage reduces developer toil and ensures critical issues are prioritized immediately.
- **Core Technology**: Built on the OpenEnv standard with deterministic grading, shaped rewards, and a robust action/observation space.
- **Status**: `openenv validate` is **PASSING** locally.

---

## ✨ Key Features

- **OpenEnv Standards**: Full support for `/reset`, `/step`, and `/state` endpoints.
- **Difficulty Progression**: Three distinct task sets (`easy`, `medium`, `hard`) controlled via the `TASK_SET` environment variable.
- **Deterministic Grading**: 100% reproducible scoring (0.0 to 1.0) based on a weighted rubric.
- **Security-First**: Built-in **Security Cap Rule**—if an agent fails to escalate a security-sensitive issue, its final score is capped at **0.2**.
- **Real-World Utility**: Simulates reporter behavior with deterministic clarification responses.
- **Docker-Ready**: Fully containerized and ready for deployment to Hugging Face Spaces.

---

## 🛠️ Environment Interface

The environment uses a structured JSON-based communication protocol.

### Action Space (7 Types)

1. **`AskClarification`**: Request missing info (repro steps, logs, etc.) from the reporter.
2. **`SetClassification`**: Categorize as `bug`, `feature_request`, or `question`.
3. **`SetSeverity`**: Assign priority from `S0_critical` to `S3_cosmetic`.
4. **`AssignComponent`**: Route to specific teams (e.g., `backend`, `auth`, `payments`).
5. **`ProposeNextAction`**: Recommend workflow steps (e.g., `fix_immediately`, `backlog`).
6. **`SubmitTriage`**: Terminal action to complete the episode.
7. **`EscalateToHuman`**: Terminal action for security issues or extreme ambiguity.

### Observation Space

Agents receive a rich context including:

- **`issue_id` / `title` / `description`**: Core issue data.
- **`environment`**: OS, Browser, App Version, and Device details.
- **`logs_excerpt`**: Raw system logs if available.
- **`conversation_history`**: The full thread of interactions between the agent and reporter.

> [!TIP]
> See [docs/ACTIONS_OBS_SCHEMA.md](docs/ACTIONS_OBS_SCHEMA.md) for the full technical schema.

---

## 📊 Tasks & Scoring

### Difficulty Levels

#### Easy — Complete Information

Fully-documented reports with clear repro steps, environment info, and error logs.
The correct classification, component routing, and severity are unambiguous from context.

> Example: An international payment processing failure traced via logs to a Stripe gateway
> configuration error introduced in v3.1.0.

#### Medium — Missing Information

Reports arrive with one critical piece missing — repro steps, log output, or environment
details. The agent must identify the gap and ask one targeted clarification question
before completing triage. Unnecessary questions are penalized.

> Example: A mobile app crash report with no reproduction steps, where the agent must
> ask for steps before correctly classifying and routing.

#### Hard — Complex & Security-Critical

Multi-symptom scenarios with misleading red-herrings, or clear security red-flags
(unauthorized data access, authentication bypass). The agent must recognize security
risks and call EscalateToHuman. Treating a security issue as a normal bug caps the
score at 0.2 regardless of other correct decisions.

> Example: A user reports seeing another customer's personal data and order history —
> the agent must escalate immediately, not just classify as a backend bug.

### Scoring Rubric (Weighted 0..1)

| Criterion          | Weight | Description                                       |
| :----------------- | :----- | :------------------------------------------------ |
| **Classification** | 0.25   | Correct issue type identification.                |
| **Component**      | 0.30   | Correct team assignment.                          |
| **Severity**       | 0.20   | Proper priority leveling (partial credit for ±1). |
| **Clarification**  | 0.15   | Asking for _required_ info vs. unnecessary spam.  |
| **Next Action**    | 0.10   | Correct workflow recommendation.                  |

**Shaped Rewards**: The agent receives incremental rewards/penalties during the episode to guide behavior (e.g., bonus for required questions, penalty for excessive steps).

---

## 💻 Installation & Usage

### Local Setup (No Docker)

Requires `uv` or `pip`.

```bash
# Clone and setup
git clone <repo-url> bugtriage-openenv
cd bugtriage-openenv
make setup
source .venv/bin/activate

# Start the environment server
cd bugtriage_env
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Golden Commands (curl)

```bash
# Health check
curl http://localhost:8000/health

# Reset (starts episode)
curl -X POST http://localhost:8000/reset

# Step (example: set severity)
curl -X POST http://localhost:8000/step -H "Content-Type: application/json" \
     -d '{"action_type": "SetSeverity", "severity": "S1_major"}'
```

---

## 🐳 Docker Deployment

The environment is designed to run in a container.

**Build:**

```bash
docker build -f bugtriage_env/server/Dockerfile -t bugtriage-openenv bugtriage_env/
```

**Run:**

```bash
docker run -p 8000:8000 -e TASK_SET=medium bugtriage-openenv
```

> [!NOTE]
> If running with external datasets not baked into the image, use a bind mount:
> `-v $(pwd)/tasks:/app/env/tasks:ro`

---

## ✅ Validation

We ensure the environment adheres to the OpenEnv specification using the official validator.

```bash
cd bugtriage_env
openenv validate
```

**Status: PASSING** — Checks for endpoint compliance, model schema, and state consistency.

---

## 🤖 Baseline Runner

The baseline uses the **OpenAI client** against the Hugging Face Router OpenAI-compatible endpoint to call a language model and perform triage.

**Environment Variables:**

- `HF_TOKEN`: Your Hugging Face token for Router access.
- `ENV_BASE_URL`: (Optional) Defaults to `http://localhost:8000`.
- `API_BASE_URL`: (Optional) Defaults to `https://router.huggingface.co/v1`.
- `MODEL_NAME`: (Optional) Model identifier for Router inference.
- `BASELINE_EPISODES_PER_SET`: (Optional) Defaults to `5`.

**Run Baseline:**

```bash
make baseline
```

The runner executes `easy`, `medium`, and `hard` sets in one run and prints:

- strict `[START]`, `[STEP]`, and `[END]` logs per episode
- per-episode score and reward breakdown in the terminal output

### Baseline Score Report

Latest validated baseline run with `Qwen/Qwen2.5-7B-Instruct` and 5 episodes per set:

| Task Set | Episodes | Avg Score |
| :------- | :------: | :-------: |
| easy     |    5     |  1.0000   |
| medium   |    5     |  0.6500   |
| hard     |    5     |  0.1420   |
| overall  |    15    |  0.5973   |

---

## 📁 Repository Map

- `bugtriage_env/`: Core implementation package.
- `openenv.yaml`: Root OpenEnv submission manifest.
- `docs/`: In-depth documentation (Architecture, Rubric, Task Specs).
- `scripts/`: Verification and utility scripts.
- `tasks/`: Dataset files for evaluation.
- `tests/`: Pytest suite for environment logic.

---

## 🚀 Deployment (HF Spaces)

Final submission deployment:
**HF Space URL**: [https://huggingface.co/spaces/Mohit2EZ/bugtriage-openenv](https://huggingface.co/spaces/Mohit2EZ/bugtriage-openenv)

**Live Endpoints**:
- Health: `https://Mohit2EZ-bugtriage-openenv.hf.space/health`
- Reset: `https://Mohit2EZ-bugtriage-openenv.hf.space/reset`
- Step: `https://Mohit2EZ-bugtriage-openenv.hf.space/step`

---

## 📄 License & Contributing

Licensed under the **BSD-3-Clause License**. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

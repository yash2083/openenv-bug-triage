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

## 🎯 Environment Goal

**What is the agent trying to achieve?**

The agent's objective is to **accurately triage incoming bug/issue reports** by:

1. **Gathering Information**: Identify missing critical details and ask targeted clarification questions
2. **Classification**: Correctly categorize the issue type (bug, feature request, or question)
3. **Prioritization**: Assign appropriate severity level based on impact and urgency
4. **Routing**: Direct the issue to the correct engineering team/component
5. **Action Planning**: Recommend the next workflow step (immediate fix, sprint planning, backlog, etc.)
6. **Decision Making**: Either submit a complete triage or escalate to human experts when necessary (especially for security issues)

**Success Criteria**: The agent receives a score from 0.0 to 1.0 based on how closely its decisions match the ground truth for each scenario. Perfect triage across all fields yields a score of 1.0.

---

## 🛠️ Environment Interface

The environment uses a structured JSON-based communication protocol.

### Action Space (7 Types)

The agent can take the following actions during an episode:

#### 1. **`AskClarification`**
**Purpose**: Request missing information from the issue reporter.

**When to use**:
- When reproduction steps are unclear or missing
- When environment details (OS, browser, version) are not provided
- When logs or error messages are absent
- When expected vs. actual behavior is ambiguous

**Parameters**:
- `question_type`: One of `missing_repro_steps`, `missing_environment`, `missing_logs`, `missing_expected_behavior`, `missing_frequency`, or `other`
- `question_text`: The actual question to ask

**Reward Impact**: +0.15 for asking required clarifications, -0.10 for unnecessary questions

---

#### 2. **`SetClassification`**
**Purpose**: Categorize the issue type.

**When to use**: After understanding the core nature of the report.

**Options**:
- `bug`: Something is broken or not working as intended
- `feature_request`: User wants new functionality
- `question`: User needs help or clarification

**Reward Impact**: +0.15 for correct classification, 0.0 for incorrect

---

#### 3. **`SetSeverity`**
**Purpose**: Assign priority level based on impact and urgency.

**When to use**: After understanding the scope and consequences of the issue.

**Options** (from highest to lowest priority):
- `S0_critical`: Complete service outage, data loss, security breach
- `S1_major`: Core functionality broken, affects many users
- `S2_minor`: Non-critical feature broken, workaround exists
- `S3_cosmetic`: UI/UX polish, minor visual issues

**Reward Impact**: +0.20 for exact match, +0.10 for off-by-one (e.g., S1 instead of S2), 0.0 otherwise

---

#### 4. **`AssignComponent`**
**Purpose**: Route the issue to the appropriate engineering team.

**When to use**: After identifying which system/service is affected.

**Options**: `backend`, `frontend`, `database`, `auth`, `payments`, `notifications`, `infrastructure`, `mobile`, `api`, `unknown`

**Reward Impact**: +0.20 for exact match, +0.10 for same component family (e.g., `auth` and `backend` are both service_core), 0.0 otherwise

---

#### 5. **`ProposeNextAction`**
**Purpose**: Recommend the workflow step after triage.

**When to use**: After completing classification, severity, and component assignment.

**Options**:
- `fix_immediately`: Critical issues requiring immediate attention
- `needs_investigation`: Requires deeper analysis before fixing
- `schedule_next_sprint`: Plan for upcoming sprint
- `add_to_backlog`: Lower priority, queue for future work
- `close_as_duplicate`: Already reported elsewhere
- `close_as_wontfix`: Not a bug or out of scope

**Reward Impact**: +0.15 for exact match, +0.075 for same policy family, 0.0 otherwise

---

#### 6. **`SubmitTriage`** (Terminal Action)
**Purpose**: Complete the triage process and end the episode.

**When to use**: When all required fields are set and you're confident in your decisions.

**Parameters**:
- `summary`: Brief explanation of your triage decision

**Reward Impact**: +0.15 if all required fields are present, -0.20 if submitting with missing information

---

#### 7. **`EscalateToHuman`** (Terminal Action)
**Purpose**: Escalate to human experts for manual review.

**When to use**:
- **Security issues**: Unauthorized data access, authentication bypass, credential exposure
- **Extreme ambiguity**: Cannot determine correct classification even after clarifications
- **High-stakes decisions**: When wrong triage could have severe consequences

**Parameters**:
- `reason`: Explanation for why escalation is needed

**Reward Impact**: +1.0 for security issues (required), -0.50 for unnecessary escalation

**⚠️ Critical Rule**: Failing to escalate a security-flagged issue caps your final score at 0.2, regardless of other correct decisions.

---

### Observation Space

Agents receive a rich context including:

- **`issue_id` / `title` / `description`**: Core issue data
- **`reporter_type`**: Whether reporter is `customer`, `internal`, or `qa`
- **`environment`**: OS, Browser, App Version, and Device details
- **`logs_excerpt`**: Raw system logs if available
- **`conversation_history`**: The full thread of interactions between agent and reporter
- **`step_count` / `max_steps`**: Current progress in the episode
- **`reward`**: Reward received for the last action
- **`done`**: Whether the episode has ended

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

The agent's final score is computed using a weighted rubric across five criteria:

| Criterion          | Weight | Description                                       |
| :----------------- | :----- | :------------------------------------------------ |
| **Classification** | 0.25   | Correct issue type identification.                |
| **Component**      | 0.30   | Correct team assignment.                          |
| **Severity**       | 0.20   | Proper priority leveling (partial credit for ±1). |
| **Clarification**  | 0.15   | Asking for _required_ info vs. unnecessary spam.  |
| **Next Action**    | 0.10   | Correct workflow recommendation.                  |

**Raw Score Calculation**:
```
raw_score = (0.25 × classification_score) +
            (0.30 × component_score) +
            (0.20 × severity_score) +
            (0.15 × clarification_score) +
            (0.10 × next_action_score)
```

---

## 🎁 Reward Signals

### Shaped Rewards (Step-Level)

The agent receives incremental rewards throughout the episode to guide learning:

**Positive Rewards**:
- ✅ Correct classification: **+0.15**
- ✅ Correct component assignment: **+0.20**
- ✅ Correct severity: **+0.20**
- ✅ Asked required clarification: **+0.15**
- ✅ Correct next action: **+0.15**
- ✅ Complete submission with all fields: **+0.15**

**Negative Penalties**:
- ❌ Submitting with missing required info: **-0.20**
- ❌ Asking unnecessary clarification: **-0.10**
- ❌ Invalid action format: **-0.10**
- ❌ Loop penalty (after step 6): **-0.05 per extra step**
- ❌ Early submission (< 2 steps): **30% penalty multiplier**
- ❌ Wrong security handling: **Score capped at 0.2**

### Partial Credit Mechanisms

**Severity (Off-by-One)**:
- Exact match: **1.0 × weight**
- One level off (e.g., S1 instead of S2): **0.5 × weight**
- Two+ levels off: **0.0 × weight**

**Component (Same Family)**:
- Exact match: **1.0 × weight**
- Same component family: **0.5 × weight**
  - Example: `auth` and `backend` are both in `service_core` family
- Different family: **0.0 × weight**

**Next Action (Same Policy)**:
- Exact match: **1.0 × weight**
- Same policy family: **0.5 × weight**
  - Example: `fix_immediately` and `needs_investigation` are both in `urgent_fix_path`
- Different policy: **0.0 × weight**

**Clarification Quality**:
```
score = (asked_required / total_required) - (0.1 × unnecessary_count)
```
Clamped to [0.0, 1.0]

### Security Cap Rule ⚠️

**Critical**: If a scenario has `security_flag = true` and the agent does NOT call `EscalateToHuman`, the final score is **capped at 0.2** regardless of all other correct decisions.

This enforces that security issues must always be escalated to human experts, even if the agent correctly identifies the type, severity, and component.

### Final Score Computation

```python
# Apply step-based penalties
penalty_multiplier = 1.0
if step_count > 6:
    loop_penalty = 0.05 × (step_count - 6)
    penalty_multiplier = max(0.0, 1.0 - loop_penalty)
if step_count < 2:
    penalty_multiplier *= 0.7

final_score = raw_score × penalty_multiplier

# Apply security cap
if security_flag and not agent_escalated:
    final_score = min(final_score, 0.2)

# Clamp to valid range
final_score = max(0.0, min(1.0, final_score))
```

---

## 💻 Installation & Usage

### Prerequisites

- **Python 3.10+** (tested with 3.12)
- **uv** (recommended) or **pip** for dependency management
- **Docker** (optional, for containerized deployment)
- **curl** or similar HTTP client for testing

### Local Setup (No Docker)

**Step 1: Clone the repository**
```bash
git clone https://github.com/yash2083/openenv-bug-triage.git
cd openenv-bug-triage
```

**Step 2: Install dependencies**

Using `make` (recommended):
```bash
make setup
source .venv/bin/activate
```

Or manually with `uv`:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install uv
uv sync
```

Or with `pip`:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Step 3: Start the environment server**
```bash
cd bugtriage_env
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`. You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Step 4: Verify the server is running**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

### Testing the Environment

**Basic Episode Flow**:

```bash
# 1. Reset to start a new episode (easy difficulty)
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json"

# 2. Take an action (set classification)
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "SetClassification",
    "issue_type": "bug"
  }'

# 3. Take another action (set severity)
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "SetSeverity",
    "severity": "S1_major"
  }'

# 4. Check current state
curl http://localhost:8000/state

# 5. Submit triage to end episode
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "SubmitTriage",
    "summary": "Payment gateway issue requiring immediate fix"
  }'
```

**Testing Different Difficulty Levels**:

The environment uses the `TASK_SET` environment variable to control difficulty:

```bash
# Easy scenarios (default)
TASK_SET=easy uvicorn server.app:app --port 8000

# Medium scenarios (missing information)
TASK_SET=medium uvicorn server.app:app --port 8000

# Hard scenarios (security-critical)
TASK_SET=hard uvicorn server.app:app --port 8000
```

### Running Tests

**Unit Tests** (pytest):
```bash
source .venv/bin/activate
pytest tests/ -v
```

**Backend Logic Validation**:
```bash
source .venv/bin/activate
python scripts/validate_backend_logic.py
```

**OpenEnv Compliance Validation**:
```bash
cd bugtriage_env
openenv validate
```

All tests should pass before deployment.

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

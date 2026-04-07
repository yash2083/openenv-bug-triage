# Contributing to Bug/Issue Triage OpenEnv

Thank you for contributing to the Bug/Issue Triage OpenEnv environment. This guide covers our conventions, workflow, and quality standards.

---

## Branch Naming Convention

All branches **must** follow this pattern:

| Owner   | Branch Name               | Area              |
|---------|---------------------------|--------------------|
| Mohit   | `feature/tasks-mohit`     | Task scenarios & dataset |
| Saksham | `feature/grader-saksham`  | Grader, rewards, baseline, tests |
| Yash    | `feature/platform-yash`   | Platform, Docker, deployment |

Additional branches (bugfix, hotfix) should follow:
```
bugfix/<short-description>
hotfix/<short-description>
```

---

## Pull Request Checklist

Before opening a PR, confirm **all** of the following:

- [ ] **Tests pass**: `pytest tests/ -v` exits with 0 failures.
- [ ] **No secrets committed**: `.env`, tokens, API keys must never appear in code or commits.
- [ ] **Docs updated**: If you changed Action/Observation schemas, update `docs/ACTIONS_OBS_SCHEMA.md`.
- [ ] **Schema stability**: Do not rename or remove fields in `Action` / `Observation` models without team agreement.
- [ ] **Deterministic**: No LLM calls inside the environment. Grading logic must be reproducible.
- [ ] **Docker builds**: `docker build -t bugtriage-openenv .` succeeds.
- [ ] **Linted**: Code follows formatting and type-hint guidelines (see below).

---

## Local Run Commands

### 1. Python virtual environment

```bash
# Option A: venv + pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Option B: uv (faster)
pip install uv
uv sync
```

### 2. Docker

```bash
docker build -t bugtriage-openenv .
docker run -p 8000:8000 --env-file .env bugtriage-openenv
```

### 3. OpenEnv validation

```bash
openenv validate
```

### 4. Baseline inference

```bash
export HF_TOKEN="<your-token>"
python inference.py
```

---

## Code Style

### Formatting
- Use **4-space indentation** (no tabs).
- Maximum line length: **100 characters**.
- Use `black` or `ruff format` for auto-formatting.

### Type Hints
- All public functions must have **full type annotations** (parameters + return types).
- Use Pydantic models for structured data (Action, Observation, State, Reward).

### Naming
- snake_case for functions and variables.
- PascalCase for classes.
- UPPER_SNAKE_CASE for constants.

### Schema Stability
- **Do not change** the Action/Observation model field names without updating:
  - `docs/ACTIONS_OBS_SCHEMA.md`
  - `examples/sample_issue.json`
  - `examples/sample_trajectory.md`
  - All test files under `tests/`

---

## How to Add a New Task Scenario

1. Read the task authoring guidelines in [`tasks/README.md`](tasks/README.md).
2. Choose the appropriate difficulty file:
   - `tasks/issues_easy.json`
   - `tasks/issues_medium.json`
   - `tasks/issues_hard.json`
3. Add a new JSON record following the required schema (see `tasks/README.md` for all fields).
4. Ensure ground-truth labels are deterministic and unambiguous.
5. Add or update tests in `tests/` to cover the new scenario.
6. Open a PR and reference the scenario `issue_id` in the PR title.

---

## Questions?

If anything is unclear, open a GitHub Issue or message the team on our group chat.

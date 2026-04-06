# OpenEnv Round 1 Work Plan (Bug/Issue Triage Environment)

**Last updated:** 2026-04-05 18:34  
**Project:** Bug/Issue Triage OpenEnv Environment (Jira/GitHub-style)

---

## 1) Goal (What we’re building)

A **real-world OpenEnv environment** that simulates **bug/issue triage** so an AI agent can:
- `reset()` into a new issue scenario
- observe structured issue context
- take structured actions via `step(action)`
- receive **shaped rewards** during the trajectory
- be graded deterministically with a **0.0–1.0 score** across **3 tasks** (easy → medium → hard)
- run locally in Docker and deploy as a **Hugging Face Space**

> Key reminder: **We are building the environment**, not “the best agent”. The agent runner (baseline inference script) is used to verify the env works.

---

## 2) Team Roles (Owners + Responsibilities)

### Person 1 — **You** (Platform & Deployment Owner)
**Focus:** “It runs everywhere, passes validation, deploys cleanly.”

**Responsibilities**
- Initialize project using `openenv init`
- Implement OpenEnv spec:
  - Typed Pydantic models: `Action`, `Observation`, `State`, `Reward`
  - Implement `reset()`, `step(action)`, `state()` with clean episode boundaries
- Integrate task loader (reads Mohit’s task files)
- Ensure Docker works:
  - `docker build` + `docker run`
  - environment starts cleanly
- Run and fix until:
  - `openenv validate` passes
  - HF Space is live with working demo
- Maintain repo structure and baseline “run” instructions in README

**Deliverables**
- Working environment core + API
- Dockerfile verified
- HF Space URL
- `openenv validate` passing output

---

### Teammate A — **Mohit** (Tasks & Dataset Owner)
**Focus:** “Real-world utility + difficulty progression.”

**Responsibilities**
- ✅ Define the bug triage domain rules:
  - ✅ issue types (bug/feature/question)
  - ✅ severity levels (S0–S3 or P0–P3)
  - ✅ component/team list
  - ✅ escalation policy (security/red flags)
- ✅ Create **3 tasks** (minimum):
  - ✅ **Easy:** complete info, obvious mapping
  - ✅ **Medium:** missing one critical field → requires clarification
  - ✅ **Hard:** multi-symptom / misleading hints / security red flag → must escalate correctly
- ✅ Build dataset (recommended **12–20 scenarios** total):
  - ✅ 15 scenarios total (5 per difficulty level)
- ✅ For each scenario include deterministic ground truth:
  - ✅ `true_type`, `true_component`, `true_severity`
  - ✅ `required_clarifications`
  - ✅ `gold_next_action`
  - ✅ optional: `security_flag`, `duplicate_of`, etc.
- ✅ Provide short task descriptions for README

**Deliverables**
- ✅ `tasks/` dataset file(s) (JSON/YAML) — `issues_easy.json`, `issues_medium.json`, `issues_hard.json`
- ✅ Ground-truth rubric fields (deterministic) — All scenarios include complete ground truth
- ✅ README task text snippets — Detailed difficulty descriptions added
- ✅ **Bonus:** `scripts/validate_tasks.py` — Schema validator with coverage reporting
- ✅ **Bonus:** `tests/test_task_scenarios.py` — 21 tests covering schema and grading integration

---

### Teammate B — **Saksham** (Grader, Rewards & Baseline Owner)
**Focus:** “Deterministic scoring + shaped rewards + reproducible baseline.”

**Responsibilities**
- Implement deterministic graders (no subjective scoring):
  - Return score in **[0.0, 1.0]**
  - Weighted scoring across multiple criteria
- Implement shaped reward signals across the trajectory:
  - partial progress rewards
  - penalties for loops/early submission/unsafe behavior
- Implement baseline inference script (`inference.py`):
  - Uses OpenAI-compatible client + HF Router
  - Reads `HF_TOKEN` from env
  - Runs all 3 tasks and prints reproducible scores
  - Low temperature for reproducibility
- Provide baseline scores for README

**Deliverables**
- `grader.py` + reward logic
- `inference.py` baseline runner
- baseline scores (per task + overall)

---

## 3) Environment Blueprint (High-level design)

### Observation (what agent sees)
Recommended fields (keep structured and consistent):
- `issue_id`
- `title`, `description`
- `reporter_type` (customer/internal/QA)
- `product_area` or `known_components` list
- `environment` (OS/browser/app_version/device)
- `logs_excerpt` (optional)
- `attachments_present` (bool)
- `conversation_history` (list of {role, message})
- `step_count`, `max_steps`

### Action space (structured actions)
Actions should be typed and narrow for deterministic grading:
1. `AskClarification(question_type, question_text)`
2. `SetClassification(issue_type)`
3. `SetSeverity(severity)`
4. `AssignComponent(component)`
5. `ProposeNextAction(next_action)`
6. `SubmitTriage(summary, final_decision)` → ends episode
7. `EscalateToHuman(reason)` → ends episode

### State (internal)
- scenario ground truth (hidden)
- agent decisions so far
- missing fields checklist
- flags (security risk, duplicate)

---

## 4) Tasks (Minimum 3)
Mohit will implement these, but this is the shared definition:

### Task 1 — Easy
- Clear repro + logs + environment info included
- Obvious component mapping
- Goal: correct classification + component + severity + next action

### Task 2 — Medium
- One critical missing field (e.g., missing repro steps or missing logs)
- Agent must ask a relevant clarification before submitting triage

### Task 3 — Hard
- Mixed symptoms + misleading hints
- Security red-flag phrase (e.g., “can see other user’s data”)
- Agent must escalate; heavy penalty if treated as normal bug

---

## 5) Deterministic Grading (0.0–1.0 score)
Saksham will implement, suggested weighted scoring:

- Classification correctness: **0.25**
- Component/team correctness: **0.30**
- Severity correctness: **0.20**
- Clarification behavior: **0.15**
- Next action correctness: **0.10**

Hard-task override:
- If `security_flag == true` and agent **does not** escalate → score cap at **0.2** (or apply strong penalty)

---

## 6) Reward shaping (step-level)
We need rewards throughout the trajectory (not only terminal). Suggested:

**Positive**
- correct classification chosen: `+0.15`
- correct component assigned: `+0.20`
- correct severity: `+0.20`
- asked required clarification (when missing info): `+0.15`
- correct final next-action: `+0.15`
- high-quality final submission (all required fields satisfied): `+0.15`

**Negative**
- submitting with missing required info: `-0.20`
- loop penalty after step N (e.g., after 6): `-0.05` per extra step
- wrong security handling (hard task): `-0.50`
- invalid action / unknown component: `-0.10`

> Final normalized score is computed by grader; step rewards help training and show “partial progress signals”.

---

## 7) Repo Structure (recommended)
```text
bugtriage-openenv/
  README.md
  requirements.txt
  openenv.yaml
  inference.py                 # baseline runner (Saksham)
  tasks/
    issues_easy.json
    issues_medium.json
    issues_hard.json
  my_env/
    __init__.py
    models.py                  # Pydantic models
    env.py                     # reset/step/state
    grader.py                  # deterministic scorer
  server/
    app.py                     # FastAPI wrapper
  Dockerfile
```

---

## 8) Step-by-step Execution Plan (Parallel-friendly)

### Milestone 1 — Skeleton runs (Day 1)
**Owner:** You  
- `openenv init <env_name>`
- Implement minimal models + `reset/step/state`
- Docker builds and runs
- HF Space initial deployment (even if tasks are dummy)

**Exit criteria**
- `docker build` succeeds
- `docker run` starts server
- `/health` works (or equivalent)
- `reset()` and `step()` respond

---

### Milestone 2 — Tasks integrated (Day 2)
**Owner:** Mohit + You
- ✅ Mohit delivers task dataset files
- ✅ You load tasks into env reset()
- ✅ Basic transitions work

**Exit criteria**
- ✅ selecting easy/medium/hard scenarios works
- ✅ env state updates correctly after actions

---

### Milestone 3 — Graders + rewards + baseline (Day 3)
**Owner:** Saksham + You  
- deterministic grader returns [0,1]
- shaped rewards per step
- inference.py runs end-to-end

**Exit criteria**
- `python inference.py` prints task scores
- scores are reproducible across runs

---

### Milestone 4 — Validate + polish + final deploy (Day 4)
**Owner:** You  
- `openenv validate` passes
- HF Space stable
- README finalized (tasks, action/obs spaces, setup, baseline scores)

**Exit criteria**
- `openenv validate` ✅
- HF Space URL works
- README complete

---

## 9) Commands (Quick Reference)

### Local
```bash
python -m venv .venv
source .venv/bin/activate

pip install -U "openenv-core[cli]" uv
# If using uv/pyproject:
uv sync
# Else:
pip install -r requirements.txt
```

### Docker
```bash
docker build -t bugtriage-openenv .
docker run -p 8000:8000 bugtriage-openenv
```

### Validate + Push
```bash
openenv validate
openenv push
```

### Baseline
```bash
export HF_TOKEN="..."
python inference.py
```

---

## 10) Definition of Done (Round 1 Checklist)
- [ ] Real-world bug/issue triage (not toy/game)
- [ ] OpenEnv-spec: typed models + `reset/step/state` + `openenv.yaml`
- [ ] 3 tasks: easy/medium/hard
- [ ] Deterministic grader returns 0.0–1.0
- [ ] Reward shaping provides partial progress signals + penalties
- [ ] Baseline inference script runs & reproduces scores
- [ ] `docker build && docker run` works
- [ ] `openenv validate` passes
- [ ] Hugging Face Space deployed and stable
- [ ] README includes: environment description, action/observation spaces, tasks, rewards, setup, baseline scores

---

## 11) Notes
- Keep environment deterministic (no external LLM calls inside env).
- Baseline script can use HF Router (free) via OpenAI-compatible client.
- Prefer structured actions (enums + fields) to make grading reliable and simple.

# Implementation Plan — Mohit (Tasks & Dataset Owner)

**Branch:** `feature/tasks-mohit`  
**Last Updated:** 2026-04-06  
**Status:** Approved — ready to execute

---

## 1. Goal

Create the **complete task dataset** for the Bug/Issue Triage OpenEnv environment.  
Without these files, the environment falls back to the single `examples/sample_issue.json` and cannot run Milestone 2+.

**Deliverables:**
- `tasks/issues_easy.json` — 5 scenarios
- `tasks/issues_medium.json` — 5 scenarios
- `tasks/issues_hard.json` — 5 scenarios
- `scripts/validate_tasks.py` — JSON schema validator
- `tests/test_task_scenarios.py` — Scenario-specific tests
- README task description snippets (updates to `README.md`)

**Total:** 15 scenarios, 1 validator, 1 test file, 1 README section update.

---

## 2. Approved Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Scenario count | **5 per level (15 total)** | Aligns with repo guideline of 12–18 total |
| Component coverage | **8 of 10** (skip `api`, `unknown`) | `unknown` is a fallback; `api` overlaps with `backend` |
| Security scenarios | **3 of 5 hard** are security-flagged | Prevents "always escalate" bias in training |
| `close_as_duplicate` | **Include** (1 easy scenario) | Already in schema; adds realism to triage task |

---

## 3. Enum Reference (from `models.py`)

Use **only** these values in the dataset JSON files:

```
true_type:        bug | feature_request | question
true_severity:    S0_critical | S1_major | S2_minor | S3_cosmetic
true_component:   backend | frontend | database | auth | payments |
                  notifications | infrastructure | mobile | api | unknown
gold_next_action: fix_immediately | schedule_next_sprint | add_to_backlog |
                  needs_investigation | close_as_duplicate | close_as_wontfix
required_clarifications (each item): missing_repro_steps | missing_environment |
                  missing_logs | missing_expected_behavior | missing_frequency | other
reporter_type:    customer | internal | qa
difficulty:       easy | medium | hard
```

---

## 4. JSON Schema (every scenario must match this)

```json
{
  "issue_id":               "TRIAGE-XXX",
  "title":                  "Short issue title (< 80 chars)",
  "description":            "Full issue description from reporter (2–5 sentences minimum)",
  "reporter_type":          "customer | internal | qa",
  "environment": {
    "os":          "...",
    "browser":     "...",
    "app_version": "...",
    "device":      "..."
  },
  "logs_excerpt":           "ERROR log lines here | null if intentionally missing",
  "true_type":              "bug | feature_request | question",
  "true_component":         "<component enum value>",
  "true_severity":          "<severity enum value>",
  "required_clarifications": [],
  "gold_next_action":       "<next_action enum value>",
  "security_flag":          false,
  "difficulty":             "easy | medium | hard"
}
```

> **Rule:** All 15 fields must be present in every scenario. `logs_excerpt` may be `null` only when the scenario intentionally tests a missing-logs situation.

---

## 5. Easy Scenarios (`tasks/issues_easy.json`)

**Rules:**
- All fields fully populated (no `null` values except where irrelevant)
- `required_clarifications: []` for all
- `security_flag: false` for all
- Optimal agent flow: 3–5 steps → `SubmitTriage`
- One scenario must use `close_as_duplicate` as `gold_next_action`

| # | ID | Title | Component | Severity | Type | Next Action | Reporter |
|---|---|---|---|---|---|---|---|
| 1 | TRIAGE-001 | Payment processing fails for international credit cards | `payments` | `S1_major` | `bug` | `fix_immediately` | `internal` |
| 2 | TRIAGE-002 | Dashboard charts not rendering on Safari 17 | `frontend` | `S2_minor` | `bug` | `schedule_next_sprint` | `qa` |
| 3 | TRIAGE-003 | Add dark mode toggle to account settings page | `frontend` | `S3_cosmetic` | `feature_request` | `add_to_backlog` | `customer` |
| 4 | TRIAGE-004 | Database connection pool exhausted under peak load | `database` | `S1_major` | `bug` | `fix_immediately` | `internal` |
| 5 | TRIAGE-005 | Login failure error identical to TRIAGE-001 — confirmed duplicate | `auth` | `S2_minor` | `bug` | `close_as_duplicate` | `qa` |

**Scenario Writing Rules for Easy:**
- Include realistic log excerpts (e.g., `ERROR 2026-03-25 09:14:33 payments.gateway - ...`)
- Environment: concrete OS + browser + app version + device
- Description: mention when the issue started, frequency, and impact
- Logs must clearly point to the `true_component`

---

## 6. Medium Scenarios (`tasks/issues_medium.json`)

**Rules:**
- Each scenario missing **exactly one** critical field
- `required_clarifications` contains exactly **one** item
- `security_flag: false` for all
- Optimal agent flow: 5–7 steps — `AskClarification` → receive response → classify → triage → `SubmitTriage`
- Cover all 5 `QuestionType` values across the 5 scenarios

| # | ID | Title | Component | Severity | Missing Info | `required_clarifications` | Reporter |
|---|---|---|---|---|---|---|---|
| 6 | TRIAGE-006 | Mobile app crashes on launch after v4.8 update | `mobile` | `S1_major` | No repro steps | `["missing_repro_steps"]` | `customer` |
| 7 | TRIAGE-007 | API rate limiter blocking legitimate user requests | `backend` | `S1_major` | No logs provided | `["missing_logs"]` | `internal` |
| 8 | TRIAGE-008 | User avatar upload completes but image never appears | `infrastructure` | `S2_minor` | No expected behavior stated | `["missing_expected_behavior"]` | `customer` |
| 9 | TRIAGE-009 | Sessions timing out too quickly after v4.7 deployment | `auth` | `S2_minor` | No environment info | `["missing_environment"]` | `qa` |
| 10 | TRIAGE-010 | Checkout flow intermittently hangs at payment confirmation | `payments` | `S1_major` | No frequency/reproducibility info | `["missing_frequency"]` | `customer` |

**Scenario Writing Rules for Medium:**
- The missing field must be **obviously absent** from the description
- After the agent asks the right question, the environment returns a deterministic canned response (already implemented in `bugtriage_env_environment.py:62-86`)
- The correct classification must be clear **after** clarification, not before
- For TRIAGE-007 (missing logs): set `logs_excerpt: null`

---

## 7. Hard Scenarios (`tasks/issues_hard.json`)

**Rules:**
- **3 scenarios:** `security_flag: true` → correct terminal action is `EscalateToHuman`
- **2 scenarios:** `security_flag: false` → misleading symptoms, but correct action is `SubmitTriage`
- All scenarios have multi-symptom descriptions with red-herrings
- Optimal agent flow: 4–8 steps

### 7a. Security-Flagged Hard Scenarios (3)

Must contain explicit red-flag phrases. Agent **must** call `EscalateToHuman`. Failing to escalate → score capped at 0.2.

| # | ID | Title | Component | Severity | Red-Flag Phrase | Reporter |
|---|---|---|---|---|---|---|
| 11 | TRIAGE-011 | User profile page displaying another user's personal data | `auth` | `S0_critical` | "I can see another user's contact information and order history" | `customer` |
| 12 | TRIAGE-012 | Password reset link remains valid after being used once | `auth` | `S0_critical` | "used the same reset link twice and both times worked" | `customer` |
| 13 | TRIAGE-013 | Internal admin dashboard accessible without authentication | `backend` | `S0_critical` | "navigated to /admin without logging in and had full access" | `internal` |

For security scenarios:
- `gold_next_action`: use `fix_immediately` (the correct action *if* it weren't a security issue — grader checks `agent_escalated` flag, not `next_action` for security scenarios)
- Logs show concerning patterns (e.g., mismatched `user_id`, unguarded endpoints)
- Description must make the security implication **obvious** to a careful reader
- `required_clarifications`: can be `[]` or `["missing_repro_steps"]`

### 7b. Non-Security Hard Scenarios (2)

Misleading symptoms — look scary but are actually non-security bugs. Agent should **not** escalate; should `SubmitTriage`.

| # | ID | Title | Component | Severity | Misleading Element | Correct Action | Reporter |
|---|---|---|---|---|---|---|---|
| 14 | TRIAGE-014 | Search results include records from other organization accounts | `database` | `S1_major` | Sounds like data leak — actually a missing `org_id` filter in queries | `SubmitTriage` | `qa` |
| 15 | TRIAGE-015 | Mass service failures across frontend, payments, and notifications after deploy | `infrastructure` | `S1_major` | Logs point to 3 components — actually a misconfigured environment variable | `SubmitTriage` | `internal` |

For TRIAGE-014: Include a note in the logs clearly showing a query bug (e.g., `WHERE status='active'` missing `AND org_id=...`), making it a database query error rather than a true data exposure.

For TRIAGE-015: Logs show errors in multiple services but all trace back to one `infrastructure` misconfiguration. Description should mention deployment context.

---

## 8. Coverage Matrix

| | Easy | Medium | Hard | Total |
|---|---|---|---|---|
| **bug** | 4 | 5 | 5 | 14 |
| **feature_request** | 1 | 0 | 0 | 1 |
| **S0_critical** | 0 | 0 | 3 | 3 |
| **S1_major** | 2 | 3 | 2 | 7 |
| **S2_minor** | 2 | 2 | 0 | 4 |
| **S3_cosmetic** | 1 | 0 | 0 | 1 |
| **customer** | 2 | 3 | 2 | 7 |
| **internal** | 2 | 1 | 2 | 5 |
| **qa** | 1 | 1 | 1 | 3 |
| **security_flag=true** | 0 | 0 | 3 | 3 |

---

## 9. Validator Script (`scripts/validate_tasks.py`)

A standalone Python script (no dependencies beyond stdlib + pydantic) that:

1. Loads each of the 3 task JSON files
2. For each scenario, checks:
   - All 15 required fields present
   - `true_type` is a valid `IssueType` enum value
   - `true_component` is a valid `Component` enum value
   - `true_severity` is a valid `Severity` enum value
   - `gold_next_action` is a valid `NextAction` enum value
   - Each item in `required_clarifications` is a valid `QuestionType`
   - `reporter_type` is one of `customer | internal | qa`
   - `difficulty` matches the file it came from
   - `security_flag` is a bool
3. Enforces difficulty-level rules:
   - Easy: `required_clarifications == []`, `security_flag == false`
   - Medium: `len(required_clarifications) == 1`
   - Hard: at least some have `security_flag == true`
4. Prints a coverage summary (components, severities, reporter types)
5. Exits with code `0` on success, `1` on failure

**Run:** `python scripts/validate_tasks.py`

---

## 10. Test File (`tests/test_task_scenarios.py`)

New test file with these test classes:

### `TestTaskFilesLoad`
- All 3 JSON files parse without error
- Each file is a JSON array (not a single object)
- Each file has at least 4 scenarios

### `TestEasyScenarioSchema`
- Every easy scenario has all required fields
- `required_clarifications` is always `[]`
- `security_flag` is always `False`
- `difficulty` is always `"easy"`

### `TestMediumScenarioSchema`
- Every medium scenario has exactly 1 item in `required_clarifications`
- `security_flag` is always `False`
- `difficulty` is always `"medium"`

### `TestHardScenarioSchema`
- At least 1 and at most 4 hard scenarios have `security_flag: true`
- All security-flagged scenarios use `S0_critical` severity
- `difficulty` is always `"hard"`

### `TestGradingIntegration`
- Easy scenario with perfect agent decisions → score ≥ 0.9 (using stub grader from `test_score_range.py`)
- Medium scenario without clarification → penalized score
- Medium scenario with correct clarification → score ≥ 0.8
- Hard security scenario with `agent_escalated=True` → score > 0.2
- Hard security scenario with `agent_escalated=False` → score ≤ 0.2

---

## 11. README Updates (`README.md`)

Update the **"Tasks & Scoring → Difficulty Levels"** section:

```markdown
### Easy — Complete Information
Fully-documented reports with clear repro steps, environment info, and error logs.
The correct classification, component routing, and severity are unambiguous from context.
> Example: An international payment processing failure traced via logs to a Stripe gateway
> configuration error introduced in v3.1.0.

### Medium — Missing Information
Reports arrive with one critical piece missing — repro steps, log output, or environment
details. The agent must identify the gap and ask one targeted clarification question
before completing triage. Unnecessary questions are penalized.
> Example: A mobile app crash report with no reproduction steps, where the agent must
> ask for steps before correctly classifying and routing.

### Hard — Complex & Security-Critical
Multi-symptom scenarios with misleading red-herrings, or clear security red-flags
(unauthorized data access, authentication bypass). The agent must recognize security
risks and call EscalateToHuman. Treating a security issue as a normal bug caps the
score at 0.2 regardless of other correct decisions.
> Example: A user reports seeing another customer's personal data and order history —
> the agent must escalate immediately, not just classify as a backend bug.
```

---

## 12. Execution Order

```
Step 1: git checkout -b feature/tasks-mohit
Step 2: Write tasks/issues_easy.json        (5 scenarios)
Step 3: Write tasks/issues_medium.json      (5 scenarios)
Step 4: Write tasks/issues_hard.json        (5 scenarios)
Step 5: Write scripts/validate_tasks.py
Step 6: Run: python scripts/validate_tasks.py → must pass
Step 7: Write tests/test_task_scenarios.py
Step 8: Run: pytest tests/ -v → must pass with 0 failures
Step 9: Update README.md task descriptions
Step 10: git add + commit (conventional: feat(tasks): add 15 bug triage scenarios)
Step 11: Open PR to main, tag Yash for review
```

---

## 13. Verification Commands

```bash
# Validate schema compliance
python scripts/validate_tasks.py

# Run all tests (must pass 0 failures)
pytest tests/ -v

# Verify the env loads each difficulty level (run from repo root)
cd bugtriage_env
TASK_SET=easy python -c "
from server.bugtriage_env_environment import _load_scenarios
s = _load_scenarios('easy')
print(f'Easy: {len(s)} scenarios loaded')
assert len(s) == 5
"

TASK_SET=medium python -c "
from server.bugtriage_env_environment import _load_scenarios
s = _load_scenarios('medium')
print(f'Medium: {len(s)} scenarios loaded')
assert len(s) == 5
"

TASK_SET=hard python -c "
from server.bugtriage_env_environment import _load_scenarios
s = _load_scenarios('hard')
print(f'Hard: {len(s)} scenarios loaded')
assert len(s) == 5
"

# Verify round-robin cycling works
TASK_SET=easy uvicorn server.app:app --port 8001 &
curl -s -X POST http://localhost:8001/reset | python -m json.tool | grep issue_id
curl -s -X POST http://localhost:8001/reset | python -m json.tool | grep issue_id
# Should show different issue_ids
```

---

## 14. Definition of Done (Mohit)

- [x] `tasks/issues_easy.json` — 5 scenarios, all fields valid, passes validator
- [x] `tasks/issues_medium.json` — 5 scenarios, 1 clarification each, passes validator
- [x] `tasks/issues_hard.json` — 5 scenarios (3 security-flagged), passes validator
- [x] `scripts/validate_tasks.py` — exits with code 0 on all 3 files
- [x] `tests/test_task_scenarios.py` — all tests pass
- [x] `pytest tests/ -v` — 0 failures (21 passed in 0.25s)
- [x] `README.md` task descriptions updated
- [x] PR ready on `feature/tasks-mohit` branch (pushed to remote, ready for manual PR creation)

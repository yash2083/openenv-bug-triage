# Actions & Observations Schema

This document defines the exact schemas for **Actions** and **Observations** used in the Bug/Issue Triage OpenEnv environment.

> **Rule**: All schema changes must be reflected here, in `examples/`, and in `tests/`. See [CONTRIBUTING.md](../CONTRIBUTING.md).

---

## Enums

### `issue_type`
```
bug | feature_request | question
```

### `severity`
```
S0_critical | S1_major | S2_minor | S3_cosmetic
```

### `component`
```
backend | frontend | database | auth | payments | notifications | infrastructure | mobile | api | unknown
```

### `question_type`
Used when the agent asks a clarification question.
```
missing_repro_steps | missing_environment | missing_logs | missing_expected_behavior | missing_frequency | other
```

### `next_action`
The recommended next action after triage.
```
fix_immediately | schedule_next_sprint | add_to_backlog | needs_investigation | close_as_duplicate | close_as_wontfix
```

---

## Action Schema

Every action sent via `env.step(action)` must conform to one of the following typed payloads. The top-level structure is:

```json
{
  "action_type": "<ActionType>",
  "payload": { ... }
}
```

### Action Types & Payloads

#### 1. `AskClarification`
Ask the reporter for missing information.

```json
{
  "action_type": "AskClarification",
  "payload": {
    "question_type": "missing_repro_steps",
    "question_text": "Could you provide the exact steps to reproduce this issue?"
  }
}
```

#### 2. `SetClassification`
Classify the issue type.

```json
{
  "action_type": "SetClassification",
  "payload": {
    "issue_type": "bug"
  }
}
```

#### 3. `SetSeverity`
Assign a severity level.

```json
{
  "action_type": "SetSeverity",
  "payload": {
    "severity": "S1_major"
  }
}
```

#### 4. `AssignComponent`
Assign the issue to a component/team.

```json
{
  "action_type": "AssignComponent",
  "payload": {
    "component": "auth"
  }
}
```

#### 5. `ProposeNextAction`
Recommend the next workflow action.

```json
{
  "action_type": "ProposeNextAction",
  "payload": {
    "next_action": "fix_immediately"
  }
}
```

#### 6. `SubmitTriage` *(terminal action)*
Submit the final triage decision. **Ends the episode.**

```json
{
  "action_type": "SubmitTriage",
  "payload": {
    "summary": "Authentication bypass bug affecting user sessions. Classified as S0 critical, assigned to auth team for immediate fix.",
    "final_decision": {
      "issue_type": "bug",
      "severity": "S0_critical",
      "component": "auth",
      "next_action": "fix_immediately"
    }
  }
}
```

#### 7. `EscalateToHuman` *(terminal action)*
Escalate the issue to a human operator. **Ends the episode.** Required for security-flagged scenarios.

```json
{
  "action_type": "EscalateToHuman",
  "payload": {
    "reason": "Potential security vulnerability: reporter mentions ability to access other users' data. Requires immediate human security review."
  }
}
```

---

## Observation Schema

Returned by `env.reset()` and `env.step(action)`. This is what the agent sees.

```json
{
  "issue_id": "TRIAGE-042",
  "title": "Login page returns 500 error after password reset",
  "description": "After resetting my password via the email link, attempting to log in with the new password results in a 500 Internal Server Error. This started happening after the latest deployment on 2026-03-28.",
  "reporter_type": "customer",
  "environment": {
    "os": "Windows 11",
    "browser": "Chrome 124.0",
    "app_version": "3.2.1",
    "device": "Desktop"
  },
  "logs_excerpt": "ERROR 2026-03-28 14:22:01 auth.handler - PasswordResetTokenExpired: token_id=a8f3... user_id=9921",
  "attachments_present": false,
  "conversation_history": [
    {
      "role": "reporter",
      "message": "I reset my password but now I can't log in at all. Getting a server error."
    },
    {
      "role": "agent",
      "message": "Could you provide the exact steps to reproduce this issue?"
    },
    {
      "role": "reporter",
      "message": "1. Click forgot password  2. Get email  3. Set new password  4. Try to log in  5. See 500 error"
    }
  ],
  "step_count": 2,
  "max_steps": 10,
  "available_actions": [
    "AskClarification",
    "SetClassification",
    "SetSeverity",
    "AssignComponent",
    "ProposeNextAction",
    "SubmitTriage",
    "EscalateToHuman"
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|---|---|---|
| `issue_id` | string | Unique identifier for the issue |
| `title` | string | Short issue title |
| `description` | string | Full issue description from the reporter |
| `reporter_type` | string | One of: `customer`, `internal`, `qa` |
| `environment` | object | OS, browser, app version, device info |
| `logs_excerpt` | string \| null | Relevant log lines (may be absent) |
| `attachments_present` | bool | Whether attachments were provided |
| `conversation_history` | array | List of `{role, message}` exchanges |
| `step_count` | int | Current step number (0-indexed at reset) |
| `max_steps` | int | Maximum allowed steps for this episode |
| `available_actions` | array | List of valid action types at this step |

---

## Step Return Format

`env.step(action)` returns a tuple:

```python
(observation, reward, done, info)
```

| Field | Type | Description |
|---|---|---|
| `observation` | Observation | Updated observation (schema above) |
| `reward` | float | Step reward signal (shaped, see `SCORING_RUBRIC.md`) |
| `done` | bool | `True` if episode ended (SubmitTriage or EscalateToHuman) |
| `info` | dict | Extra metadata, e.g., `{"action_accepted": true}` |

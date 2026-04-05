# Tasks — Issue Scenario Dataset

This folder contains the issue scenario datasets used by the Bug/Issue Triage OpenEnv environment.

---

## Dataset Files

| File | Difficulty | Description |
|------|-----------|-------------|
| `issues_easy.json` | Easy | Complete info, obvious triage |
| `issues_medium.json` | Medium | Missing critical fields, requires clarification |
| `issues_hard.json` | Hard | Misleading symptoms, security red-flags, requires escalation |

---

## Required Fields for Each Issue Scenario

Every scenario record **must** include the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `issue_id` | string | ✅ | Unique identifier (e.g., `"TRIAGE-001"`) |
| `title` | string | ✅ | Short issue title |
| `description` | string | ✅ | Full issue description from the reporter |
| `reporter_type` | string | ✅ | One of: `"customer"`, `"internal"`, `"qa"` |
| `environment` | object | ✅ | `{os, browser, app_version, device}` |
| `logs_excerpt` | string \| null | ❌ | Relevant log lines; `null` if intentionally missing |
| `true_type` | string | ✅ | Ground truth issue type (enum: `bug`, `feature_request`, `question`) |
| `true_component` | string | ✅ | Ground truth component (enum: see `docs/ACTIONS_OBS_SCHEMA.md`) |
| `true_severity` | string | ✅ | Ground truth severity (enum: `S0_critical`, `S1_major`, `S2_minor`, `S3_cosmetic`) |
| `required_clarifications` | array | ✅ | List of `question_type` values the agent should ask; empty list `[]` if none needed |
| `gold_next_action` | string | ✅ | Correct next action (enum: see `docs/ACTIONS_OBS_SCHEMA.md`) |
| `security_flag` | bool | ❌ | `true` if the scenario involves a security risk; defaults to `false` |
| `difficulty` | string | ✅ | One of: `"easy"`, `"medium"`, `"hard"` |

---

## Example Scenario (Complete)

```json
{
  "issue_id": "TRIAGE-005",
  "title": "Payment processing fails for international credit cards",
  "description": "International customers report that payments with non-US credit cards are being rejected at checkout. The error message says 'Transaction declined' but the cards work on other platforms. This started after the v3.1.0 release last Tuesday. Approximately 15% of international transactions are affected based on our monitoring dashboard.",
  "reporter_type": "internal",
  "environment": {
    "os": "Linux (production server)",
    "browser": "N/A (server-side)",
    "app_version": "3.1.0",
    "device": "Server"
  },
  "logs_excerpt": "ERROR 2026-03-25 09:14:33 payments.gateway - CardValidationError: unsupported_bin_range country_code=DE card_prefix=4917** gateway=stripe_v3",
  "true_type": "bug",
  "true_component": "payments",
  "true_severity": "S1_major",
  "required_clarifications": [],
  "gold_next_action": "fix_immediately",
  "security_flag": false,
  "difficulty": "easy"
}
```

---

## Authoring Guidelines

1. **Realism**: Write scenarios that reflect genuine software issues a triage engineer would encounter. Use realistic log formats, error messages, and technical details.

2. **No plagiarism**: All scenarios must be original. Do not copy from public issue trackers.

3. **Deterministic labels**: Every ground-truth field must be unambiguous. If reasonable people could disagree on the label, refine the scenario until the answer is clear.

4. **Difficulty alignment**:
   - **Easy**: All info present, single clear component, obvious severity.
   - **Medium**: Exactly one critical gap requiring clarification.
   - **Hard**: Multiple symptoms, at least one red-flag, answer requires careful reasoning.

5. **Balanced coverage**: Spread scenarios across different components, severity levels, and reporter types.

6. **Security scenarios** (hard only): Include phrases like "can see other user's data", "authentication bypass", "data exposed", etc. Set `security_flag: true`.

7. **Recommended count**: 4–6 scenarios per difficulty level (12–18 total).

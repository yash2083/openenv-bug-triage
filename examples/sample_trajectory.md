# Sample Trajectories

This document shows two complete episode walkthroughs demonstrating how the Bug/Issue Triage environment works end-to-end.

---

## Trajectory 1: Medium Task — Clarification Before Submit

**Scenario**: `TRIAGE-020` — "Dashboard widgets not loading for some users"

The issue description mentions widgets fail to load but does **not include logs or browser console errors** (a required clarification).

---

### Step 0: `reset()`

**Observation returned:**
```json
{
  "issue_id": "TRIAGE-020",
  "title": "Dashboard widgets not loading for some users",
  "description": "Several users have reported that the analytics dashboard widgets show a spinning loader indefinitely. The page itself loads fine, but individual widget cards never populate with data. This seems to affect roughly 30% of users.",
  "reporter_type": "customer",
  "environment": {
    "os": "Windows 10",
    "browser": "Chrome 123.0",
    "app_version": "4.5.0",
    "device": "Desktop"
  },
  "logs_excerpt": null,
  "attachments_present": false,
  "conversation_history": [
    {
      "role": "reporter",
      "message": "Several users have reported that the analytics dashboard widgets show a spinning loader indefinitely."
    }
  ],
  "step_count": 0,
  "max_steps": 10,
  "available_actions": ["AskClarification", "SetClassification", "SetSeverity", "AssignComponent", "ProposeNextAction", "SubmitTriage", "EscalateToHuman"]
}
```

---

### Step 1: Agent asks for missing logs

**Action:**
```json
{
  "action_type": "AskClarification",
  "payload": {
    "question_type": "missing_logs",
    "question_text": "Could you provide the browser console errors or network tab output when the widgets fail to load?"
  }
}
```

**Return:** `(observation, reward=+0.15, done=False, info={"action_accepted": true})`

The `+0.15` reward is because `missing_logs` is in `required_clarifications`.

Updated `conversation_history` now includes:
```json
[
  {"role": "reporter", "message": "Several users have reported..."},
  {"role": "agent", "message": "Could you provide the browser console errors..."},
  {"role": "reporter", "message": "Console shows: 'TypeError: Cannot read property map of undefined' in widget-renderer.js:142. Network tab shows 200 OK for /api/widgets but response body is empty JSON array."}
]
```

---

### Step 2: Agent classifies the issue

**Action:**
```json
{
  "action_type": "SetClassification",
  "payload": {
    "issue_type": "bug"
  }
}
```

**Return:** `(observation, reward=+0.15, done=False, info={"action_accepted": true})`

Correct classification → positive reward.

---

### Step 3: Agent sets severity

**Action:**
```json
{
  "action_type": "SetSeverity",
  "payload": {
    "severity": "S1_major"
  }
}
```

**Return:** `(observation, reward=+0.20, done=False, info={"action_accepted": true})`

---

### Step 4: Agent assigns component

**Action:**
```json
{
  "action_type": "AssignComponent",
  "payload": {
    "component": "frontend"
  }
}
```

**Return:** `(observation, reward=+0.20, done=False, info={"action_accepted": true})`

---

### Step 5: Agent submits triage

**Action:**
```json
{
  "action_type": "SubmitTriage",
  "payload": {
    "summary": "Frontend bug causing dashboard widgets to fail loading for ~30% of users. Empty API response triggers TypeError in widget-renderer.js. Classified as S1 major, assigned to frontend team.",
    "final_decision": {
      "issue_type": "bug",
      "severity": "S1_major",
      "component": "frontend",
      "next_action": "fix_immediately"
    }
  }
}
```

**Return:** `(observation, reward=+0.15, done=True, info={"action_accepted": true})`

---

### Grader Result

```
classification_score = 1.0  (bug == bug)
component_score      = 1.0  (frontend == frontend)
severity_score       = 1.0  (S1_major == S1_major)
clarification_score  = 1.0  (asked missing_logs, 1/1 required)
next_action_score    = 1.0  (fix_immediately == fix_immediately)

raw_score = 0.25*1.0 + 0.30*1.0 + 0.20*1.0 + 0.15*1.0 + 0.10*1.0 = 1.0
penalty_multiplier = 1.0  (5 steps < 6 threshold, not early submit)

final_score = 1.0 * 1.0 = 1.0
```

---

---

## Trajectory 2: Hard Task — Security Escalation

**Scenario**: `TRIAGE-031` — "I can see another customer's invoices in my billing page"

This is a hard task with `security_flag: true`. The agent **must escalate**.

---

### Step 0: `reset()`

**Observation returned:**
```json
{
  "issue_id": "TRIAGE-031",
  "title": "I can see another customer's invoices in my billing page",
  "description": "When I navigate to the billing section, I see invoices that do not belong to my account. The invoice numbers, amounts, and company names are clearly from a different organization. I noticed this after switching between two browser tabs where I was logged into different accounts. This is extremely concerning from a privacy perspective.",
  "reporter_type": "customer",
  "environment": {
    "os": "macOS 14.2",
    "browser": "Safari 17.3",
    "app_version": "4.6.0",
    "device": "Desktop"
  },
  "logs_excerpt": null,
  "attachments_present": true,
  "conversation_history": [
    {
      "role": "reporter",
      "message": "I can see invoices from another company on my billing page. This is a serious privacy issue."
    }
  ],
  "step_count": 0,
  "max_steps": 10,
  "available_actions": ["AskClarification", "SetClassification", "SetSeverity", "AssignComponent", "ProposeNextAction", "SubmitTriage", "EscalateToHuman"]
}
```

---

### Step 1: Agent classifies as bug

**Action:**
```json
{
  "action_type": "SetClassification",
  "payload": {
    "issue_type": "bug"
  }
}
```

**Return:** `(observation, reward=+0.15, done=False, info={"action_accepted": true})`

---

### Step 2: Agent sets severity to critical

**Action:**
```json
{
  "action_type": "SetSeverity",
  "payload": {
    "severity": "S0_critical"
  }
}
```

**Return:** `(observation, reward=+0.20, done=False, info={"action_accepted": true})`

---

### Step 3: Agent asks for clarification on reproduction

**Action:**
```json
{
  "action_type": "AskClarification",
  "payload": {
    "question_type": "missing_repro_steps",
    "question_text": "Can you confirm the exact steps: were you actively switching between tabs, or did this appear immediately after login?"
  }
}
```

**Return:** `(observation, reward=+0.15, done=False, info={"action_accepted": true})`

Updated conversation includes the reporter's response confirming the tab-switching triggered it.

---

### Step 4: Agent escalates to human

**Action:**
```json
{
  "action_type": "EscalateToHuman",
  "payload": {
    "reason": "SECURITY ESCALATION: Customer reports cross-account data leakage — invoices from another organization are visible on their billing page. This indicates a potential session isolation or authorization bypass vulnerability. Requires immediate human security review and possible incident response."
  }
}
```

**Return:** `(observation, reward=+0.15, done=True, info={"action_accepted": true, "escalation": true})`

---

### Grader Result

```
classification_score = 1.0  (bug == bug)
component_score      = 0.0  (agent did not set component before escalation — acceptable trade-off)
severity_score       = 1.0  (S0_critical == S0_critical)
clarification_score  = 1.0  (asked missing_repro_steps, 1/1 required)
next_action_score    = 1.0  (EscalateToHuman matches gold for security_flag scenarios)

raw_score = 0.25*1.0 + 0.30*0.0 + 0.20*1.0 + 0.15*1.0 + 0.10*1.0 = 0.70
penalty_multiplier = 1.0  (4 steps, no penalties)

final_score = 0.70 * 1.0 = 0.70
```

> **Note**: The agent scored 0.70 because it did not assign the component before escalating. An agent that also calls `AssignComponent(auth)` before escalating would score 1.0. Both behaviors are valid — escalating quickly for security is acceptable.

---

## Key Takeaways

1. **Medium tasks** require at least one clarification before submission. Skipping clarification leads to a penalty.
2. **Hard tasks** with `security_flag: true` require `EscalateToHuman`. Using `SubmitTriage` caps the score at 0.2.
3. Step rewards provide immediate feedback — the agent knows when it's on track.
4. The grader evaluates the final state independently from step rewards.

# Task Specification

This document defines the **task difficulty levels**, expected agent behavior, and termination conditions for the Bug/Issue Triage OpenEnv environment.

---

## Difficulty Definitions

### Easy

**Characteristics**:
- Issue has **complete information**: clear title, detailed description, reproduction steps, environment info, and log excerpt.
- The correct classification, component, and severity are **obvious** from the provided context.
- No clarification questions are required.

**What "done" means**:
- Agent correctly classifies the issue type.
- Agent assigns the correct component.
- Agent sets the correct severity.
- Agent proposes the correct next action.
- Agent calls `SubmitTriage` with a coherent summary.

**Expected agent flow** (3–5 steps):
1. `SetClassification` → correct type
2. `SetSeverity` → correct severity
3. `AssignComponent` → correct team
4. `ProposeNextAction` → correct action
5. `SubmitTriage` → final summary with all decisions

---

### Medium

**Characteristics**:
- Issue is **missing one critical piece of information** (e.g., no reproduction steps, no logs, or missing environment details).
- The agent **must ask at least one clarification** before submitting.
- After receiving clarification, the triage becomes straightforward.

**What "done" means**:
- Agent identifies the missing information and asks a relevant clarification.
- After clarification, agent correctly classifies, assigns component, sets severity, and submits.

**Expected agent flow** (5–7 steps):
1. Read the issue and recognize missing info.
2. `AskClarification` → relevant question targeting the gap.
3. Receive clarification in the updated observation.
4. `SetClassification` → correct type
5. `SetSeverity` → correct severity
6. `AssignComponent` → correct team
7. `SubmitTriage` → with `ProposeNextAction` in final decision

---

### Hard

**Characteristics**:
- Issue has **mixed or misleading symptoms** that could point to multiple components.
- Issue contains a **security red-flag** (e.g., "I can see another user's data", "authentication bypass", "data leak").
- The ground truth has `security_flag: true`.
- The agent **must escalate** to a human; treating it as a normal bug results in a heavy penalty.
- May also require clarification before escalation.

**What "done" means**:
- Agent recognizes the security risk.
- Agent calls `EscalateToHuman` with a clear reason mentioning the security concern.
- Partial credit is given for correct classification and severity if set before escalation.

**Expected agent flow** (4–8 steps):
1. Read the issue and notice security signals.
2. Optionally `AskClarification` if needed to confirm the security scope.
3. `SetClassification` → correct type
4. `SetSeverity` → `S0_critical` (security issues are always critical)
5. `EscalateToHuman` → with clear security-related reason

---

## Termination Conditions

An episode ends when **any** of the following occur:

| Condition | Trigger |
|-----------|---------|
| **SubmitTriage** | Agent calls `SubmitTriage` action |
| **EscalateToHuman** | Agent calls `EscalateToHuman` action |
| **Max steps reached** | Agent reaches `max_steps` without a terminal action |

When max steps is reached without a terminal action:
- Episode ends with `done = True`.
- The grader evaluates whatever state has been set so far.
- Loop penalty applies (see `SCORING_RUBRIC.md`).

---

## Max Steps Guidance

| Difficulty | Recommended Max Steps | Typical Optimal Steps |
|------------|----------------------|----------------------|
| Easy       | 8                    | 3–5                  |
| Medium     | 10                   | 5–7                  |
| Hard       | 10                   | 4–8                  |

- Setting max steps too low prevents agents from completing the task.
- Setting max steps too high allows excessive looping (mitigated by loop penalty after step 6).
- The environment enforces the max step limit; the agent cannot exceed it.

---

## Summary Table

| Aspect | Easy | Medium | Hard |
|--------|------|--------|------|
| Info completeness | Full | Missing 1 critical field | Mixed/misleading |
| Clarification required | No | Yes (≥1) | Optional |
| Security flag | No | No | Yes |
| Terminal action | SubmitTriage | SubmitTriage | EscalateToHuman |
| Max steps | 8 | 10 | 10 |
| Key challenge | Straightforward mapping | Identify gap, ask, then triage | Detect security risk, escalate |

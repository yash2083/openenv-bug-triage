# Scoring Rubric

This document defines the **deterministic scoring formula** used by the Bug/Issue Triage OpenEnv environment grader. All scores are in the range **[0.0, 1.0]**.

---

## Final Score Formula

```
final_score = (
    W_classification * classification_score
  + W_component      * component_score
  + W_severity       * severity_score
  + W_clarification  * clarification_score
  + W_next_action    * next_action_score
) * penalty_multiplier
```

### Weight Breakdown

| Criterion            | Weight | Symbol             | Description |
|----------------------|--------|--------------------|-------------|
| Classification       | 0.25   | `W_classification` | Did the agent correctly identify the issue type (bug / feature_request / question)? |
| Component            | 0.30   | `W_component`      | Did the agent assign the correct component/team? |
| Severity             | 0.20   | `W_severity`       | Did the agent set the correct severity level? |
| Clarification        | 0.15   | `W_clarification`  | Did the agent ask required clarifications (and avoid unnecessary ones)? |
| Next Action          | 0.10   | `W_next_action`    | Did the agent propose the correct workflow next-action? |
| **Total**            | **1.00** | | |

---

## Per-Criterion Scoring

### Classification Score (0.0 or 1.0)
- `1.0` if `agent_issue_type == true_type`
- `0.0` otherwise

### Component Score (0.0 or 1.0)
- `1.0` if `agent_component == true_component`
- `0.0` otherwise

### Severity Score (0.0, 0.5, or 1.0)
- `1.0` if exact match
- `0.5` if off by one level (e.g., S1 vs S2)
- `0.0` if off by two or more levels

### Clarification Score (0.0 – 1.0)
```
clarification_score = asked_required / total_required - unnecessary_penalty
```
- `asked_required`: count of required clarifications the agent actually asked
- `total_required`: count of clarifications needed (from ground truth)
- `unnecessary_penalty`: `0.1` per unnecessary clarification asked (clamped so score ≥ 0.0)
- If `total_required == 0` and agent asked 0 clarifications → `1.0`
- If `total_required == 0` and agent asked ≥ 1 clarification → `0.8` (mild penalty)

### Next Action Score (0.0 or 1.0)
- `1.0` if `agent_next_action == gold_next_action`
- `0.0` otherwise

---

## Special Rules

### 1. Security Flag Override (Hard Tasks)

If the scenario has `security_flag: true`:

- **Agent MUST call `EscalateToHuman`** as the terminal action.
- If the agent calls `SubmitTriage` instead (i.e., does not escalate):
  - **Final score is capped at 0.2**, regardless of how correct other fields are.
  - Formula: `final_score = min(raw_score, 0.2)`
- If the agent correctly escalates:
  - Score is computed normally with `next_action_score = 1.0`.

### 2. Loop Penalty

If the agent exceeds **6 steps** without reaching a terminal action:

```
loop_penalty = 0.05 * (step_count - 6)
```

This is subtracted from the penalty multiplier:
```
penalty_multiplier = max(0.0, 1.0 - loop_penalty)
```

**Example**: Agent takes 9 steps → `loop_penalty = 0.05 * 3 = 0.15` → `penalty_multiplier = 0.85`

### 3. Submit-Too-Early Penalty

If the agent calls `SubmitTriage` before **step 2** (i.e., submits on step 0 or 1):

```
penalty_multiplier *= 0.7
```

This penalizes agents that skip all analysis and immediately guess.

### 4. Invalid Action Penalty

If the agent sends an action with an unrecognized `action_type` or invalid enum value:

- The step returns `reward = -0.10`
- The action is **not applied** to the state

---

## Step-Level Reward Signals

Step rewards provide shaped feedback throughout the episode. They are **informational** for agent training and **do not directly determine the final score** (which is computed by the grader at episode end). However, the sum of step rewards should correlate with final score.

### Positive Rewards

| Event | Reward | Condition |
|-------|--------|-----------|
| Correct classification set | `+0.15` | `SetClassification` matches `true_type` |
| Correct component assigned | `+0.20` | `AssignComponent` matches `true_component` |
| Correct severity set | `+0.20` | `SetSeverity` matches `true_severity` |
| Required clarification asked | `+0.15` | `AskClarification` with `question_type` in `required_clarifications` |
| Correct next action proposed | `+0.15` | `ProposeNextAction` matches `gold_next_action` |
| Complete correct submission | `+0.15` | `SubmitTriage` with all fields correct |

### Negative Rewards

| Event | Reward | Condition |
|-------|--------|-----------|
| Submit with missing required info | `-0.20` | `SubmitTriage` before asking required clarifications |
| Loop penalty (after step 6) | `-0.05` | Each step beyond step 6 |
| Wrong security handling | `-0.50` | `security_flag == true` and agent does not escalate |
| Invalid/unknown action | `-0.10` | Unrecognized action type or invalid enum value |
| Unnecessary clarification | `-0.05` | Clarification asked that is not in `required_clarifications` |

---

## Relationship: Step Rewards → Final Score

- **Step rewards** are emitted during the episode to guide agent behavior.
- **Final score** is computed by the grader at episode end using the formula above.
- Step rewards are **not summed** to produce the final score. They are separate signals.
- A well-performing agent will accumulate positive step rewards AND achieve a high final score.
- The grader examines the agent's final submitted state (or escalation) against ground truth.

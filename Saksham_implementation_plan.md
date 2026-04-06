# Implementation Plan for Saksham (Grader, Rewards & Baseline Owner)

## Overview
This document outlines the detailed implementation procedure for Saksham based on the OpenEnv Bug/Issue Triage Work Plan and README. Saksham is responsible for deterministic scoring, shaped rewards, and creating a reproducible baseline inference script.

## Responsibilities & Deliverables
**Focus:** “Deterministic scoring + shaped rewards + reproducible baseline.”

### Primary Deliverables
1. `grader.py`: Contains the deterministic scoring logic and reward shaping algorithms.
2. `inference.py`: A baseline runner using Hugging Face Router and an OpenAI-compatible client.
3. **Baseline Scores**: Documented baseline scores per task and overall for the `README.md`.

---

## Step-by-Step Execution Plan (Milestone 3)

### Step 1: Implement the Deterministic Grader (`grader.py`)
Create a grader that evaluates an episode purely deterministically, without subjective LLM-based scoring. The final score must strictly be in the `[0.0, 1.0]` range.

**Weighted Scoring Rubric:**
- **Classification Correctness:** `0.25`
- **Component/Team Correctness:** `0.30`
- **Severity Correctness:** `0.20` (Implement partial credit for ±1 severity level if applicable)
- **Clarification Behavior:** `0.15` (Agent must ask for required information vs. avoiding unnecessary spam)
- **Next Action Correctness:** `0.10`

**Hard-task Override (Security Cap Rule):**
- If the ground truth scenario has `security_flag == true` and the agent **does not** explicitly use the `EscalateToHuman` action, the final score must be **capped at 0.2** (or heavily penalized), regardless of other correct categorizations.

### Step 2: Implement Shaped Rewards (Step-Level)
In addition to the final grade, agents must receive immediate incremental step rewards and penalties during the trajectory. Implement this within `grader.py` or the environment step evaluation logic.

**Positive Rewards (+):**
- Correct classification chosen: `+0.15`
- Correct component assigned: `+0.20`
- Correct severity assigned: `+0.20`
- Asked required clarification (when info was missing): `+0.15`
- Correct final next-action proposed: `+0.15`
- High-quality final submission (all required fields satisfied): `+0.15`

**Negative Penalties (-):**
- Submitting with missing required info: `-0.20`
- Loop penalty after an acceptable step count N (e.g., after 6 steps): `-0.05` per extra step
- Wrong security handling (on hard task, failing to escalate): `-0.50`
- Invalid action / unknown component choice: `-0.10`

### Step 3: Implement Baseline Inference Script (`inference.py`)
Develop a baseline runner to validate the environment and provide reference scores.

**Requirements:**
- Connect via an OpenAI-compatible client routing through the **Hugging Face Router**.
- Retrieve authentication via the `HF_TOKEN` environment variable.
- Configure inference with **low temperature** (e.g., `temperature=0.0`) to ensure deterministic and reproducible outputs.
- Execute across all three task difficulty levels (`easy`, `medium`, `hard` specified by `TASK_SET`).
- Parse the structured environment API (handling `/reset`, `/step`, `/state`).
- Read and format observation space to the LLM and map LLM outputs to the 7 action space types (e.g., `AskClarification`, `SetClassification`, `SubmitTriage`, `EscalateToHuman`).
- Output and print a detailed breakdown of task scores explicitly at the end of the run.

### Step 4: Testing & Verification
- Execute `python inference.py` locally.
- Verify that it completes runs for `easy`, `medium`, and `hard` task sets correctly without errors.
- Ensure that multiple runs print reproducible and identical scores (due to low temperature config).
- Make sure that agents triggering the hard task accurately trigger the "Security Cap Rule" and properly receive step-level shaped rewards/penalties during evaluation.

### Step 5: Deliver Baseline Scores
- Gather the final performance numbers from `inference.py`.
- Formulate a brief score report out of these numbers and deliver them so they can be added to the Baseline portion of the `README.md`.

---

## Target Exit Criteria
- Deterministic grader reliably returns `[0.0, 1.0]`.
- Shaped rewards clearly demonstrate partial progress signals per step in logs or returned payloads.
- `python inference.py` runs end-to-end flawlessly using an HF model (e.g., `meta-llama/Llama-3-70b-instruct`) and produces reproducible scores.

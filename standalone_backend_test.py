


import os
import sys
import json
from pathlib import Path

# Ensure the project root is in the path for imports
project_root = Path(__file__).parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from bugtriage_env.server.bugtriage_env_environment import BugtriageEnvironment
from bugtriage_env.models import (
    BugtriageAction,
    ActionType,
    IssueType,
    Severity,
    Component,
    NextAction,
    FinalDecision
)
from bugtriage_env.grader import grade_episode_breakdown

def run_test():
    print("=== STARTING STANDALONE BACKEND TEST ===")
    env = BugtriageEnvironment()

    # --- Test Case 1: Happy Path (TRIAGE-001) ---
    print("\n--- TEST 1: Happy Path (TRIAGE-001) ---")
    obs = env.reset(task_set="easy")
    print(f"Initial Observation: {obs.title} (ID: {obs.issue_id})")
    
    # Step 1: Set Classification
    obs = env.step(BugtriageAction(action_type=ActionType.SET_CLASSIFICATION, issue_type=IssueType.BUG))
    print(f"Step 1 Reward: {obs.reward}")
    
    # Step 2: Set Severity
    obs = env.step(BugtriageAction(action_type=ActionType.SET_SEVERITY, severity=Severity.S1_MAJOR))
    print(f"Step 2 Reward: {obs.reward}")
    
    # Step 3: Assign Component
    obs = env.step(BugtriageAction(action_type=ActionType.ASSIGN_COMPONENT, component=Component.PAYMENTS))
    print(f"Step 3 Reward: {obs.reward}")
    
    # Step 4: Propose Next Action
    obs = env.step(BugtriageAction(action_type=ActionType.PROPOSE_NEXT_ACTION, next_action=NextAction.FIX_IMMEDIATELY))
    print(f"Step 4 Reward: {obs.reward}")
    
    # Step 5: Submit Triage
    final_decision = FinalDecision(
        issue_type=IssueType.BUG,
        severity=Severity.S1_MAJOR,
        component=Component.PAYMENTS,
        next_action=NextAction.FIX_IMMEDIATELY
    )
    obs = env.step(BugtriageAction(action_type=ActionType.SUBMIT_TRIAGE, summary="Verified payment issue.", final_decision=final_decision))
    print(f"Step 5 (Final) Reward: {obs.reward}")
    print(f"Done: {obs.done}")
    print(f"Final Score: {obs.final_score}")
    print(f"Score Breakdown: {obs.score_breakdown}")
    
    assert obs.done is True
    assert obs.final_score > 0.9, f"Score should be high for correct triage, got {obs.final_score}"

    # --- Test Case 2: Security Logic (TRIAGE-011) ---
    # We'll search for the security flag scenario in hard/medium if TRIAGE-011 isn't first.
    # For simplicity, we'll just check if the grader handles security correctly.
    print("\n--- TEST 2: Grader Security Logic ---")
    result = grade_episode_breakdown(
        agent_type="bug",
        agent_component="backend",
        agent_severity="S0_critical",
        agent_next_action="fix_immediately",
        true_type="bug",
        true_component="backend",
        true_severity="S0_critical",
        gold_next_action="fix_immediately",
        asked_clarifications=[],
        required_clarifications=[],
        unnecessary_clarifications=0,
        security_flag=True,   # Security issue!
        agent_escalated=False, # Did NOT escalate
        step_count=3
    )
    print(f"Security Issue (No Escalation) Score: {result.final_score}")
    assert result.final_score <= 0.2, "Security issue without escalation should be capped at 0.2"

    result_escalated = grade_episode_breakdown(
        agent_type="bug",
        agent_component="backend",
        agent_severity="S0_critical",
        agent_next_action="fix_immediately",
        true_type="bug",
        true_component="backend",
        true_severity="S0_critical",
        gold_next_action="fix_immediately",
        asked_clarifications=[],
        required_clarifications=[],
        unnecessary_clarifications=0,
        security_flag=True,   # Security issue!
        agent_escalated=True,  # Correctly escalated
        step_count=2
    )
    print(f"Security Issue (Escalated) Score: {result_escalated.final_score}")
    # High score because escalation is correct for security
    assert result_escalated.final_score > 0.9

    # --- Test Case 3: Grader Partial Credit ---
    print("\n--- TEST 3: Grader Partial Credit ---")
    # Off-by-one severity reward
    result_partial = grade_episode_breakdown(
        agent_type="bug",
        agent_component="backend",
        agent_severity="S1_major", # Correct: S0_critical
        agent_next_action="fix_immediately",
        true_type="bug",
        true_component="backend",
        true_severity="S0_critical",
        gold_next_action="fix_immediately",
        asked_clarifications=[],
        required_clarifications=[],
        unnecessary_clarifications=0,
        security_flag=False,
        agent_escalated=False,
        step_count=3
    )
    print(f"Partial Severity (agent=S1, truth=S0) Score: {result_partial.final_score}")
    # raw_score calculation (S1 vs S0 diff=1 -> 0.5 * 0.20 = 0.10 severity)
    # The rest: (0.25 * 1.0) + (0.30 * 1.0) + (0.20 * 0.5) + (0.15 * 1.0) + (0.10 * 1.0) = 0.25 + 0.30 + 0.10 + 0.15 + 0.10 = 0.90
    assert result_partial.final_score == 0.90

    print("\n=== ALL STANDALONE TESTS PASSED! ===")

if __name__ == "__main__":
    run_test()

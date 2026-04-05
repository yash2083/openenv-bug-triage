# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Bug/Issue Triage Environment Implementation.

A deterministic OpenEnv environment that simulates bug/issue triage.
The agent observes an issue scenario, takes structured actions
(classify, set severity, assign component, ask clarification, etc.),
and receives shaped rewards throughout the episode.

Phase 0: Skeleton with single sample_issue.json scenario.
Phase 1+: Will load tasks from tasks/*.json datasets.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import (
        AVAILABLE_ACTIONS,
        ActionType,
        BugtriageAction,
        BugtriageObservation,
        Component,
        ConversationEntry,
        EnvironmentInfo,
        IssueType,
        NextAction,
        QuestionType,
        Severity,
    )
except ImportError:
    from models import (
        AVAILABLE_ACTIONS,
        ActionType,
        BugtriageAction,
        BugtriageObservation,
        Component,
        ConversationEntry,
        EnvironmentInfo,
        IssueType,
        NextAction,
        QuestionType,
        Severity,
    )


# ============================================================
# Predefined clarification responses (deterministic, no LLM)
# ============================================================

CLARIFICATION_RESPONSES: Dict[str, str] = {
    "missing_repro_steps": (
        "Here are the steps to reproduce: "
        "1. Navigate to the affected page. "
        "2. Perform the action described in the issue. "
        "3. Observe the error."
    ),
    "missing_environment": (
        "I'm using the environment details listed in the issue. "
        "Let me know if you need more specifics."
    ),
    "missing_logs": (
        "Here are the relevant log entries from the time of the incident."
    ),
    "missing_expected_behavior": (
        "I expected the feature to work as documented in the user guide. "
        "Instead, I got the behavior described in the issue."
    ),
    "missing_frequency": (
        "This happens consistently, approximately 8 out of 10 times I try."
    ),
    "other": (
        "I've provided additional details as requested."
    ),
}


# ---------------------------------------------------------------------------
# Round-robin index per difficulty level (class-level, persists across
# episodes within a single server process — deterministic, no randomness).
# ---------------------------------------------------------------------------
_ROUND_ROBIN_INDEX: Dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}


def _resolve_examples_root() -> Path:
    """Return the directory that contains the scenario JSON files.

    Searches multiple candidate locations so the same code works both
    locally (repo root) and inside Docker (where PYTHONPATH=/app/env).
    """
    candidates = [
        # Repo layout: bugtriage_env/server/ → ../../examples/
        Path(__file__).parent.parent.parent / "examples",
        # Docker layout: /app/env/examples  (PYTHONPATH=/app/env)
        Path(__file__).parent.parent / "examples",
        # cwd-relative (uvicorn started from bugtriage_env/)
        Path.cwd() / "examples",
        # cwd-relative (uvicorn started from repo root)
        Path.cwd() / "bugtriage_env" / "examples",
        # Last resort: sibling of server/
        Path(__file__).parent / "examples",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    raise FileNotFoundError(
        "Could not find the 'examples/' directory. Searched:\n"
        + "\n".join(f"  {c}" for c in candidates)
    )


def _load_scenarios(difficulty: str) -> List[Dict[str, Any]]:
    """Load all scenarios for the given difficulty.

    Phase 1 strategy:
      1. If tasks/{difficulty}.json exists at repo root, load that list.
      2. Otherwise fall back to tasks/issues_{difficulty}.json.
      3. Finally fall back to examples/sample_issue.json (Phase 0).

    File formats accepted:
      - JSON array of scenario dicts (preferred for task sets)
      - Single JSON object (for sample_issue.json)
    """
    examples_root = _resolve_examples_root()

    # ── Task-dataset files (Phase 1) ────────────────────────────────────────
    task_candidates = [
        examples_root.parent / "tasks" / f"issues_{difficulty}.json",
        examples_root.parent / "tasks" / f"{difficulty}.json",
        Path.cwd() / "tasks" / f"issues_{difficulty}.json",
        Path.cwd() / "tasks" / f"{difficulty}.json",
    ]
    for tc in task_candidates:
        if tc.exists():
            with open(tc, "r") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data]

    # ── Phase 0 fallback ────────────────────────────────────────────────────
    fallback = examples_root / "sample_issue.json"
    if fallback.exists():
        with open(fallback, "r") as f:
            return [json.load(f)]

    raise FileNotFoundError(
        f"No scenario files found for difficulty='{difficulty}'. "
        f"Checked task files and {fallback}"
    )


def _pick_scenario(scenarios: List[Dict[str, Any]], difficulty: str) -> Dict[str, Any]:
    """Pick a scenario deterministically using round-robin.

    The index is advanced per difficulty bucket so easy/medium/hard pools
    are independently cycled. Within a single process the sequence is
    fully deterministic and reproducible.
    """
    idx = _ROUND_ROBIN_INDEX.get(difficulty, 0) % len(scenarios)
    _ROUND_ROBIN_INDEX[difficulty] = (idx + 1) % len(scenarios)
    return scenarios[idx]


def _load_sample_scenario() -> Dict[str, Any]:
    """Load a deterministic scenario respecting the TASK_SET env variable.

    TASK_SET=easy|medium|hard  (default: easy)
    Selection is round-robin within the chosen difficulty pool.
    """
    difficulty = os.environ.get("TASK_SET", "easy").strip().lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "easy"
    scenarios = _load_scenarios(difficulty)
    return _pick_scenario(scenarios, difficulty)


class BugtriageEnvironment(Environment):
    """
    Bug/Issue Triage OpenEnv Environment.

    Simulates a bug triage workflow where an AI agent must:
    - Read an issue report
    - Classify the issue type
    - Assign severity and component
    - Ask clarification questions if info is missing
    - Submit a final triage decision or escalate to a human

    The environment is fully deterministic — no LLM calls, no randomness.
    Rewards are shaped throughout the trajectory.
    Final score is computed by the grader at episode end (0.0–1.0).
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self) -> None:
        """Initialize the bugtriage environment."""
        super().__init__()

        # Internal state
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._scenario: Dict[str, Any] = {}
        self._conversation_history: List[ConversationEntry] = []
        self._agent_decisions: Dict[str, Any] = {}
        self._done: bool = False
        self._max_steps: int = 10
        self._cumulative_reward: float = 0.0

        # Track what required clarifications the agent has asked
        self._asked_clarifications: List[str] = []

    # ------------------------------------------------------------------
    # reset()
    # ------------------------------------------------------------------

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> BugtriageObservation:
        """
        Reset the environment to a new episode.

        Loads a scenario (currently the single sample_issue.json) and
        returns the initial observation.

        Args:
            seed: Unused (deterministic env). Reserved for future use.
            episode_id: Optional episode identifier.

        Returns:
            BugtriageObservation with the issue context.
        """
        # Reset internal state
        self._state = State(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
        )
        self._done = False
        self._cumulative_reward = 0.0
        self._agent_decisions = {}
        self._asked_clarifications = []

        # Load scenario
        self._scenario = _load_sample_scenario()

        # Determine max_steps based on difficulty
        difficulty = self._scenario.get("difficulty", "easy")
        self._max_steps = {"easy": 8, "medium": 10, "hard": 10}.get(difficulty, 10)

        # Initialize conversation with reporter's initial message
        self._conversation_history = [
            ConversationEntry(
                role="reporter",
                message=self._scenario["description"],
            )
        ]

        return self._build_observation()

    # ------------------------------------------------------------------
    # step()
    # ------------------------------------------------------------------

    def step(
        self,
        action: BugtriageAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> BugtriageObservation:
        """
        Execute one step in the environment.

        Processes the agent's action, updates state, computes shaped
        reward, and returns the updated observation.

        Args:
            action: BugtriageAction with action_type and relevant fields.
            timeout_s: Unused. Reserved for interface compatibility.

        Returns:
            BugtriageObservation with updated state, reward, and done flag.
        """
        if self._done:
            return self._build_observation(reward=0.0, done=True)

        # Increment step count
        self._state.step_count += 1
        step_num = self._state.step_count

        reward = 0.0
        done = False
        info: Dict[str, Any] = {"action_accepted": True}

        try:
            action_type = action.action_type
        except Exception:
            # Invalid action
            reward = -0.10
            info["action_accepted"] = False
            info["error"] = "Invalid action format"
            return self._build_observation(reward=reward, done=False, extra_metadata=info)

        # --- Process each action type ---

        if action_type == ActionType.ASK_CLARIFICATION:
            reward = self._handle_ask_clarification(action)

        elif action_type == ActionType.SET_CLASSIFICATION:
            reward = self._handle_set_classification(action)

        elif action_type == ActionType.SET_SEVERITY:
            reward = self._handle_set_severity(action)

        elif action_type == ActionType.ASSIGN_COMPONENT:
            reward = self._handle_assign_component(action)

        elif action_type == ActionType.PROPOSE_NEXT_ACTION:
            reward = self._handle_propose_next_action(action)

        elif action_type == ActionType.SUBMIT_TRIAGE:
            reward = self._handle_submit_triage(action)
            done = True

        elif action_type == ActionType.ESCALATE_TO_HUMAN:
            reward = self._handle_escalate_to_human(action)
            done = True

        else:
            reward = -0.10
            info["action_accepted"] = False
            info["error"] = f"Unknown action type: {action_type}"

        # --- Loop penalty (after step 6) ---
        if step_num > 6 and not done:
            reward -= 0.05

        # --- Max steps check ---
        if step_num >= self._max_steps:
            done = True
            info["termination_reason"] = "max_steps_reached"

        self._done = done
        self._cumulative_reward += reward

        # Add final score to info on episode end
        if done:
            info["final_score"] = self._compute_final_score()
            info["cumulative_reward"] = self._cumulative_reward

        return self._build_observation(reward=reward, done=done, extra_metadata=info)

    # ------------------------------------------------------------------
    # state property
    # ------------------------------------------------------------------

    @property
    def state(self) -> State:
        """
        Get the current internal environment state.

        Returns:
            State with episode_id, step_count, and extra fields.
        """
        return State(
            episode_id=self._state.episode_id,
            step_count=self._state.step_count,
            # Extra fields (State has extra="allow")
            done=self._done,
            agent_decisions=self._agent_decisions.copy(),
            asked_clarifications=list(self._asked_clarifications),
            cumulative_reward=self._cumulative_reward,
            scenario_id=self._scenario.get("issue_id", ""),
            difficulty=self._scenario.get("difficulty", ""),
        )

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_ask_clarification(self, action: BugtriageAction) -> float:
        """Handle AskClarification action."""
        q_type = action.question_type
        q_text = action.question_text or "Could you provide more details?"

        if q_type is None:
            # No question type specified — treat as invalid
            self._conversation_history.append(
                ConversationEntry(role="agent", message=q_text)
            )
            return -0.05

        q_type_str = q_type.value if isinstance(q_type, QuestionType) else str(q_type)

        # Add agent question to conversation
        self._conversation_history.append(
            ConversationEntry(role="agent", message=q_text)
        )

        # Add deterministic reporter response
        response = CLARIFICATION_RESPONSES.get(q_type_str, CLARIFICATION_RESPONSES["other"])
        self._conversation_history.append(
            ConversationEntry(role="reporter", message=response)
        )

        # Score: check if this was a required clarification
        required = self._scenario.get("required_clarifications", [])
        if q_type_str in required and q_type_str not in self._asked_clarifications:
            self._asked_clarifications.append(q_type_str)
            return 0.15  # asked a needed clarification
        else:
            # Unnecessary clarification — mild penalty
            return -0.05

    def _handle_set_classification(self, action: BugtriageAction) -> float:
        """Handle SetClassification action."""
        if action.issue_type is None:
            return -0.10

        agent_type = action.issue_type.value if isinstance(action.issue_type, IssueType) else str(action.issue_type)
        self._agent_decisions["issue_type"] = agent_type

        # Add a system note to conversation
        self._conversation_history.append(
            ConversationEntry(role="agent", message=f"Classified issue as: {agent_type}")
        )

        true_type = self._scenario.get("true_type", "")
        if agent_type == true_type:
            return 0.15
        return 0.0

    def _handle_set_severity(self, action: BugtriageAction) -> float:
        """Handle SetSeverity action."""
        if action.severity is None:
            return -0.10

        agent_sev = action.severity.value if isinstance(action.severity, Severity) else str(action.severity)
        self._agent_decisions["severity"] = agent_sev

        self._conversation_history.append(
            ConversationEntry(role="agent", message=f"Set severity to: {agent_sev}")
        )

        true_sev = self._scenario.get("true_severity", "")

        if agent_sev == true_sev:
            return 0.20
        # Partial credit for off-by-one
        severity_order = ["S0_critical", "S1_major", "S2_minor", "S3_cosmetic"]
        try:
            diff = abs(severity_order.index(agent_sev) - severity_order.index(true_sev))
            if diff == 1:
                return 0.10
        except ValueError:
            pass
        return 0.0

    def _handle_assign_component(self, action: BugtriageAction) -> float:
        """Handle AssignComponent action."""
        if action.component is None:
            return -0.10

        agent_comp = action.component.value if isinstance(action.component, Component) else str(action.component)
        self._agent_decisions["component"] = agent_comp

        self._conversation_history.append(
            ConversationEntry(role="agent", message=f"Assigned to component: {agent_comp}")
        )

        true_comp = self._scenario.get("true_component", "")
        if agent_comp == true_comp:
            return 0.20
        return 0.0

    def _handle_propose_next_action(self, action: BugtriageAction) -> float:
        """Handle ProposeNextAction action."""
        if action.next_action is None:
            return -0.10

        agent_na = action.next_action.value if isinstance(action.next_action, NextAction) else str(action.next_action)
        self._agent_decisions["next_action"] = agent_na

        self._conversation_history.append(
            ConversationEntry(role="agent", message=f"Proposed next action: {agent_na}")
        )

        gold_na = self._scenario.get("gold_next_action", "")
        if agent_na == gold_na:
            return 0.15
        return 0.0

    def _handle_submit_triage(self, action: BugtriageAction) -> float:
        """Handle SubmitTriage (terminal action)."""
        summary = action.summary or ""
        self._agent_decisions["submitted"] = True
        self._agent_decisions["summary"] = summary

        # If final_decision is provided, extract its fields
        if action.final_decision is not None:
            fd = action.final_decision
            self._agent_decisions.setdefault(
                "issue_type",
                fd.issue_type.value if isinstance(fd.issue_type, IssueType) else str(fd.issue_type),
            )
            self._agent_decisions.setdefault(
                "severity",
                fd.severity.value if isinstance(fd.severity, Severity) else str(fd.severity),
            )
            self._agent_decisions.setdefault(
                "component",
                fd.component.value if isinstance(fd.component, Component) else str(fd.component),
            )
            self._agent_decisions.setdefault(
                "next_action",
                fd.next_action.value if isinstance(fd.next_action, NextAction) else str(fd.next_action),
            )

        self._conversation_history.append(
            ConversationEntry(
                role="agent",
                message=f"Submitted triage: {summary[:200]}",
            )
        )

        # Submit-too-early penalty check
        if self._state.step_count < 2:
            return -0.20

        # Check if required clarifications were asked
        required = self._scenario.get("required_clarifications", [])
        if required and not self._asked_clarifications:
            return -0.20  # submitted without asking required clarifications

        # Security flag check
        security_flag = self._scenario.get("security_flag", False)
        if security_flag:
            return -0.50  # should have escalated, not submitted

        return 0.15  # normal submit

    def _handle_escalate_to_human(self, action: BugtriageAction) -> float:
        """Handle EscalateToHuman (terminal action)."""
        reason = action.reason or ""
        self._agent_decisions["escalated"] = True
        self._agent_decisions["escalation_reason"] = reason

        self._conversation_history.append(
            ConversationEntry(
                role="agent",
                message=f"Escalated to human: {reason[:200]}",
            )
        )

        security_flag = self._scenario.get("security_flag", False)
        if security_flag:
            return 0.15  # correct — security issue should be escalated
        else:
            return -0.10  # unnecessary escalation

    # ------------------------------------------------------------------
    # Score computation (Phase 0 placeholder — Saksham will finalize)
    # ------------------------------------------------------------------

    def _compute_final_score(self) -> float:
        """
        Compute the deterministic final score (0.0–1.0).

        Uses the weighted formula from docs/SCORING_RUBRIC.md.
        This is a Phase 0 implementation; Saksham will refine in Phase 2.
        """
        # Per-criterion scores
        true_type = self._scenario.get("true_type", "")
        true_comp = self._scenario.get("true_component", "")
        true_sev = self._scenario.get("true_severity", "")
        gold_na = self._scenario.get("gold_next_action", "")
        required_clar = self._scenario.get("required_clarifications", [])
        security_flag = self._scenario.get("security_flag", False)

        # Classification
        classification_score = 1.0 if self._agent_decisions.get("issue_type") == true_type else 0.0

        # Component
        component_score = 1.0 if self._agent_decisions.get("component") == true_comp else 0.0

        # Severity (with partial credit)
        agent_sev = self._agent_decisions.get("severity", "")
        severity_order = ["S0_critical", "S1_major", "S2_minor", "S3_cosmetic"]
        if agent_sev == true_sev:
            severity_score = 1.0
        else:
            try:
                diff = abs(severity_order.index(agent_sev) - severity_order.index(true_sev))
                severity_score = 0.5 if diff == 1 else 0.0
            except ValueError:
                severity_score = 0.0

        # Clarification
        if len(required_clar) == 0:
            clarification_score = 1.0 if len(self._asked_clarifications) == 0 else 0.8
        else:
            asked_required = len(set(self._asked_clarifications) & set(required_clar))
            unnecessary = len(self._asked_clarifications) - asked_required
            clarification_score = max(
                0.0,
                asked_required / len(required_clar) - 0.1 * unnecessary,
            )

        # Next action
        agent_escalated = self._agent_decisions.get("escalated", False)
        if security_flag and agent_escalated:
            next_action_score = 1.0
        elif not security_flag:
            next_action_score = 1.0 if self._agent_decisions.get("next_action") == gold_na else 0.0
        else:
            next_action_score = 0.0

        # Weighted sum
        raw_score = (
            0.25 * classification_score
            + 0.30 * component_score
            + 0.20 * severity_score
            + 0.15 * clarification_score
            + 0.10 * next_action_score
        )

        # Penalty multiplier
        penalty_multiplier = 1.0
        step_count = self._state.step_count

        # Loop penalty
        if step_count > 6:
            loop_penalty = 0.05 * (step_count - 6)
            penalty_multiplier = max(0.0, 1.0 - loop_penalty)

        # Submit-too-early penalty
        if step_count < 2:
            penalty_multiplier *= 0.7

        final_score = raw_score * penalty_multiplier

        # Security flag override
        if security_flag and not agent_escalated:
            final_score = min(final_score, 0.2)

        return max(0.0, min(1.0, final_score))

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------

    def _build_observation(
        self,
        reward: float = 0.0,
        done: bool = False,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> BugtriageObservation:
        """Build and return a BugtriageObservation from current state."""

        env_info = self._scenario.get("environment", {})

        return BugtriageObservation(
            # Issue context
            issue_id=self._scenario.get("issue_id", ""),
            title=self._scenario.get("title", ""),
            description=self._scenario.get("description", ""),
            reporter_type=self._scenario.get("reporter_type", ""),
            environment=EnvironmentInfo(
                os=env_info.get("os"),
                browser=env_info.get("browser"),
                app_version=env_info.get("app_version"),
                device=env_info.get("device"),
            ) if env_info else None,
            logs_excerpt=self._scenario.get("logs_excerpt"),
            attachments_present=self._scenario.get("attachments_present", False),
            # Conversation
            conversation_history=list(self._conversation_history),
            # Episode tracking
            step_count=self._state.step_count,
            max_steps=self._max_steps,
            available_actions=list(AVAILABLE_ACTIONS),
            # OpenEnv base fields
            done=done,
            # Guard: reward MUST always be a float (never None, never str)
            reward=float(reward) if reward is not None else 0.0,
            metadata=extra_metadata or {},
        )

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
    from ..grader import (
        grade_episode,
        grade_episode_breakdown,
        submit_has_all_required_fields,
    )
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
    from grader import (
        grade_episode,
        grade_episode_breakdown,
        submit_has_all_required_fields,
    )
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


def _contains_any(text: str, terms: List[str]) -> bool:
    lower = text.lower()
    return any(t in lower for t in terms)


def _extract_signals(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Build deterministic helper signals from issue text/logs and explicit hints."""
    description = (scenario.get("description") or "")
    logs = (scenario.get("logs_excerpt") or "")
    text = f"{description}\n{logs}".lower()

    security_terms = [
        "password",
        "credential",
        "token",
        "secret",
        "email address",
        "personal data",
        "privacy",
        "unauthorized",
        "admin",
        "access denied",
    ]
    duplicate_terms = ["duplicate", "same issue", "matches the exact error pattern"]

    component_markers: Dict[str, List[str]] = {
        "auth": ["login", "session", "auth", "password", "token"],
        "payments": ["payment", "checkout", "stripe", "charge", "card"],
        "database": ["database", "query", "sql", "connection pool"],
        "frontend": ["ui", "frontend", "safari", "javascript", "charts"],
        "mobile": ["mobile", "ios", "android", "app crashes"],
        "infrastructure": ["deployment", "env", ".env", "configuration", "smtp"],
        "backend": ["api", "middleware", "service", "controller"],
        "api": ["endpoint", "429", "rate limiter", "request"],
        "notifications": ["notification", "email", "smtp"],
    }

    affected_component = "unknown"
    for component, markers in component_markers.items():
        if _contains_any(text, markers):
            affected_component = component
            break

    if _contains_any(text, ["all users", "completely down", "service outage", "widespread"]):
        outage_scope = "widespread"
    elif _contains_any(text, ["30%", "15%", "multiple users", "segment"]):
        outage_scope = "segment"
    else:
        outage_scope = "single_user"

    signals: Dict[str, Any] = {
        "likely_security": bool(scenario.get("security_flag", False) or _contains_any(text, security_terms)),
        "likely_duplicate": _contains_any(text, duplicate_terms),
        "outage_scope": outage_scope,
        "affected_surface": affected_component,
        "has_stacktrace": _contains_any(text, ["stack trace", "exception", "line "]),
        "has_sensitive_terms": _contains_any(text, security_terms),
        "explicit_feature_request": _contains_any(text, ["would like", "feature", "quality-of-life", "add "]),
    }

    explicit_hints = scenario.get("explicit_hints")
    if isinstance(explicit_hints, dict):
        signals["explicit_hints"] = explicit_hints
    return signals


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


def _load_sample_scenario(task_set_override: Optional[str] = None) -> Dict[str, Any]:
    """Load a deterministic scenario respecting the TASK_SET env variable.

    TASK_SET=easy|medium|hard  (default: easy)
    Selection is round-robin within the chosen difficulty pool.
    """
    difficulty = (task_set_override or os.environ.get("TASK_SET", "easy")).strip().lower()
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
        self._all_clarification_questions: List[str] = []

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
        self._all_clarification_questions = []

        # Load scenario
        task_set = kwargs.get("task_set")
        self._scenario = _load_sample_scenario(task_set_override=task_set)

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

        return self._build_observation(extracted_signals=_extract_signals(self._scenario))

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
            required = set(self._scenario.get("required_clarifications", []))
            unnecessary_count = sum(
                1 for q in self._all_clarification_questions if q not in required
            )
            breakdown = grade_episode_breakdown(
                agent_type=self._agent_decisions.get("issue_type", ""),
                agent_component=self._agent_decisions.get("component", ""),
                agent_severity=self._agent_decisions.get("severity", ""),
                agent_next_action=self._agent_decisions.get("next_action", ""),
                true_type=self._scenario.get("true_type", ""),
                true_component=self._scenario.get("true_component", ""),
                true_severity=self._scenario.get("true_severity", ""),
                gold_next_action=self._scenario.get("gold_next_action", ""),
                asked_clarifications=self._asked_clarifications,
                required_clarifications=self._scenario.get("required_clarifications", []),
                unnecessary_clarifications=unnecessary_count,
                security_flag=self._scenario.get("security_flag", False),
                agent_escalated=self._agent_decisions.get("escalated", False),
                step_count=self._state.step_count,
            )
            info["final_score"] = breakdown.final_score
            info["score_breakdown"] = breakdown.as_dict()
            info["cumulative_reward"] = self._cumulative_reward

        return self._build_observation(
            reward=reward,
            done=done,
            extra_metadata=info,
            extracted_signals=_extract_signals(self._scenario),
            final_score=info.get("final_score"),
            score_breakdown=info.get("score_breakdown", {}),
            termination_reason=info.get("termination_reason"),
        )

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
        self._all_clarification_questions.append(q_type_str)

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

        if submit_has_all_required_fields(self._agent_decisions):
            return 0.15
        return 0.0

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
    # Score computation
    # ------------------------------------------------------------------

    def _compute_final_score(self) -> float:
        required = set(self._scenario.get("required_clarifications", []))
        unnecessary_count = sum(
            1 for q in self._all_clarification_questions if q not in required
        )

        return grade_episode(
            agent_type=self._agent_decisions.get("issue_type", ""),
            agent_component=self._agent_decisions.get("component", ""),
            agent_severity=self._agent_decisions.get("severity", ""),
            agent_next_action=self._agent_decisions.get("next_action", ""),
            true_type=self._scenario.get("true_type", ""),
            true_component=self._scenario.get("true_component", ""),
            true_severity=self._scenario.get("true_severity", ""),
            gold_next_action=self._scenario.get("gold_next_action", ""),
            asked_clarifications=self._asked_clarifications,
            required_clarifications=self._scenario.get("required_clarifications", []),
            unnecessary_clarifications=unnecessary_count,
            security_flag=self._scenario.get("security_flag", False),
            agent_escalated=self._agent_decisions.get("escalated", False),
            step_count=self._state.step_count,
        )

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------

    def _build_observation(
        self,
        reward: float = 0.0,
        done: bool = False,
        extra_metadata: Optional[Dict[str, Any]] = None,
        extracted_signals: Optional[Dict[str, Any]] = None,
        final_score: Optional[float] = None,
        score_breakdown: Optional[Dict[str, float]] = None,
        termination_reason: Optional[str] = None,
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
            extracted_signals=extracted_signals or {},
            final_score=final_score,
            score_breakdown=score_breakdown or {},
            termination_reason=termination_reason,
            # OpenEnv base fields
            done=done,
            # Guard: reward MUST always be a float (never None, never str)
            reward=float(reward) if reward is not None else 0.0,
            metadata=extra_metadata or {},
        )

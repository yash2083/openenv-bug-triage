# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Bug/Issue Triage OpenEnv Environment.

Defines typed Action and Observation schemas using Pydantic.
All enums and models here are the shared contract between
platform (Yash), tasks (Mohit), and grader (Saksham).
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


# ============================================================
# Enums — keep these stable; any change must update docs + tests
# ============================================================


class IssueType(str, Enum):
    """Type of issue being reported."""
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    QUESTION = "question"


class Severity(str, Enum):
    """Severity level for the issue."""
    S0_CRITICAL = "S0_critical"
    S1_MAJOR = "S1_major"
    S2_MINOR = "S2_minor"
    S3_COSMETIC = "S3_cosmetic"


class Component(str, Enum):
    """Component/team the issue should be assigned to."""
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    AUTH = "auth"
    PAYMENTS = "payments"
    NOTIFICATIONS = "notifications"
    INFRASTRUCTURE = "infrastructure"
    MOBILE = "mobile"
    API = "api"
    UNKNOWN = "unknown"


class QuestionType(str, Enum):
    """Type of clarification question the agent can ask."""
    MISSING_REPRO_STEPS = "missing_repro_steps"
    MISSING_ENVIRONMENT = "missing_environment"
    MISSING_LOGS = "missing_logs"
    MISSING_EXPECTED_BEHAVIOR = "missing_expected_behavior"
    MISSING_FREQUENCY = "missing_frequency"
    OTHER = "other"


class NextAction(str, Enum):
    """Recommended next workflow action after triage."""
    FIX_IMMEDIATELY = "fix_immediately"
    SCHEDULE_NEXT_SPRINT = "schedule_next_sprint"
    ADD_TO_BACKLOG = "add_to_backlog"
    NEEDS_INVESTIGATION = "needs_investigation"
    CLOSE_AS_DUPLICATE = "close_as_duplicate"
    CLOSE_AS_WONTFIX = "close_as_wontfix"


class ActionType(str, Enum):
    """The type of action the agent can take."""
    ASK_CLARIFICATION = "AskClarification"
    SET_CLASSIFICATION = "SetClassification"
    SET_SEVERITY = "SetSeverity"
    ASSIGN_COMPONENT = "AssignComponent"
    PROPOSE_NEXT_ACTION = "ProposeNextAction"
    SUBMIT_TRIAGE = "SubmitTriage"
    ESCALATE_TO_HUMAN = "EscalateToHuman"


# ============================================================
# Action payload sub-models
# ============================================================


class FinalDecision(Action):
    """Final triage decision submitted with SubmitTriage."""
    issue_type: IssueType = Field(..., description="Classified issue type")
    severity: Severity = Field(..., description="Assigned severity")
    component: Component = Field(..., description="Assigned component")
    next_action: NextAction = Field(..., description="Recommended next action")


class Reward(Action):
    """Typed reward payload returned by the environment."""
    value: float = Field(..., description="Scalar reward value")
    done: bool = Field(default=False, description="Whether the episode ended")
    success: bool = Field(default=False, description="Whether the action was successful")
    reason: Optional[str] = Field(default=None, description="Optional reward explanation")


# ============================================================
# Top-level Action model
# ============================================================


class BugtriageAction(Action):
    """
    Action for the Bug/Issue Triage environment.

    Every action has an `action_type` discriminator and typed payload fields.
    Only the fields relevant to the chosen action_type need to be populated.
    """
    action_type: ActionType = Field(..., description="Type of action to take")

    # --- AskClarification fields ---
    question_type: Optional[QuestionType] = Field(
        default=None, description="Type of clarification question"
    )
    question_text: Optional[str] = Field(
        default=None, description="Free-text clarification question"
    )

    # --- SetClassification fields ---
    issue_type: Optional[IssueType] = Field(
        default=None, description="Issue type classification"
    )

    # --- SetSeverity fields ---
    severity: Optional[Severity] = Field(
        default=None, description="Severity level"
    )

    # --- AssignComponent fields ---
    component: Optional[Component] = Field(
        default=None, description="Component/team assignment"
    )

    # --- ProposeNextAction fields ---
    next_action: Optional[NextAction] = Field(
        default=None, description="Proposed next workflow action"
    )

    # --- SubmitTriage fields ---
    summary: Optional[str] = Field(
        default=None, description="Final triage summary text"
    )
    final_decision: Optional[FinalDecision] = Field(
        default=None, description="Final decision object"
    )

    # --- EscalateToHuman fields ---
    reason: Optional[str] = Field(
        default=None, description="Reason for escalation"
    )

    # --- Optional reasoning fields (used by baseline policy, ignored by env scoring) ---
    analysis_summary: Optional[str] = Field(
        default=None, description="Short evidence-based analysis summary"
    )
    evidence_keys: Optional[List[str]] = Field(
        default=None, description="Compact evidence tags used for decision"
    )
    confidence: Optional[float] = Field(
        default=None, description="Agent confidence for the chosen action in [0, 1]"
    )


# ============================================================
# Conversation history entry
# ============================================================


class ConversationEntry(Action):
    """A single entry in the conversation history."""
    role: str = Field(..., description="Role: 'reporter', 'agent', or 'system'")
    message: str = Field(..., description="Message content")


# ============================================================
# Environment info sub-model
# ============================================================


class EnvironmentInfo(Action):
    """Reporter's environment details."""
    os: Optional[str] = Field(default=None, description="Operating system")
    browser: Optional[str] = Field(default=None, description="Browser name and version")
    app_version: Optional[str] = Field(default=None, description="Application version")
    device: Optional[str] = Field(default=None, description="Device type")


# ============================================================
# Top-level Observation model
# ============================================================

# All valid action type strings for reference in observations
AVAILABLE_ACTIONS = [at.value for at in ActionType]


class BugtriageObservation(Observation):
    """
    Observation from the Bug/Issue Triage environment.

    Returned by reset() and step(). Contains all information the agent
    can see about the current issue scenario.
    """
    # --- Issue context ---
    issue_id: str = Field(default="", description="Unique issue identifier")
    title: str = Field(default="", description="Issue title")
    description: str = Field(default="", description="Full issue description")
    reporter_type: str = Field(default="", description="Reporter type: customer/internal/qa")
    environment: Optional[EnvironmentInfo] = Field(
        default=None, description="Reporter environment details"
    )
    logs_excerpt: Optional[str] = Field(
        default=None, description="Relevant log excerpt (may be null)"
    )
    attachments_present: bool = Field(
        default=False, description="Whether attachments were provided"
    )

    # --- Conversation ---
    conversation_history: List[ConversationEntry] = Field(
        default_factory=list, description="Conversation history entries"
    )

    # --- Episode tracking ---
    step_count: int = Field(default=0, description="Current step number")
    max_steps: int = Field(default=10, description="Maximum steps for this episode")
    available_actions: List[str] = Field(
        default_factory=lambda: list(AVAILABLE_ACTIONS),
        description="List of valid action types at this step",
    )

    # --- Deterministic helper signals and terminal scoring outputs ---
    extracted_signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Deterministic extracted hints from issue text and logs",
    )
    final_score: Optional[float] = Field(
        default=None,
        description="Final deterministic episode score in [0,1] when done",
    )
    score_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-criterion final score breakdown when done",
    )
    termination_reason: Optional[str] = Field(
        default=None,
        description="Reason for episode termination, if available",
    )

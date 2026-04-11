# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Deterministic grader utilities for the Bug/Issue Triage environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


SEVERITY_ORDER = ["S0_critical", "S1_major", "S2_minor", "S3_cosmetic"]

COMPONENT_FAMILY = {
    "auth": "service_core",
    "backend": "service_core",
    "api": "service_core",
    "database": "platform_data",
    "infrastructure": "platform_data",
    "frontend": "client_surface",
    "mobile": "client_surface",
    "payments": "commerce",
    "notifications": "communication",
    "unknown": "unknown",
}

NEXT_ACTION_FAMILY = {
    "fix_immediately": "urgent_fix_path",
    "needs_investigation": "urgent_fix_path",
    "schedule_next_sprint": "planned_path",
    "add_to_backlog": "planned_path",
    "close_as_duplicate": "duplicate_path",
    "close_as_wontfix": "reject_path",
}


@dataclass(frozen=True)
class ScoreBreakdown:
    """Normalized per-criterion scores and final score."""

    classification: float
    component: float
    severity: float
    clarification: float
    next_action: float
    raw_score: float
    penalty_multiplier: float
    final_score: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "classification": self.classification,
            "component": self.component,
            "severity": self.severity,
            "clarification": self.clarification,
            "next_action": self.next_action,
            "raw_score": self.raw_score,
            "penalty_multiplier": self.penalty_multiplier,
            "final_score": self.final_score,
        }


def severity_score(agent: str, truth: str) -> float:
    """Score severity with partial credit for off-by-one."""
    if agent == truth:
        return 1.0
    try:
        diff = abs(SEVERITY_ORDER.index(agent) - SEVERITY_ORDER.index(truth))
    except ValueError:
        return 0.0
    return 0.5 if diff == 1 else 0.0


def component_score(agent: str, truth: str) -> float:
    """Score component with partial credit for same component family."""
    if agent == truth:
        return 1.0
    agent_family = COMPONENT_FAMILY.get(agent, "unknown")
    truth_family = COMPONENT_FAMILY.get(truth, "unknown")
    if agent_family == truth_family and agent_family != "unknown":
        return 0.5
    return 0.0


def next_action_score(agent: str, truth: str) -> float:
    """Score next action with partial credit for same policy family."""
    if agent == truth:
        return 1.0
    agent_family = NEXT_ACTION_FAMILY.get(agent, "unknown")
    truth_family = NEXT_ACTION_FAMILY.get(truth, "unknown")
    if agent_family == truth_family and agent_family != "unknown":
        return 0.5
    return 0.0


def clarification_score(
    asked_clarifications: List[str],
    required_clarifications: List[str],
    unnecessary_clarifications: int,
) -> float:
    """Score clarification quality in the [0.0, 1.0] range."""
    total_required = len(required_clarifications)
    if total_required == 0:
        return 0.8 if unnecessary_clarifications > 0 else 1.0

    asked_required = len(set(asked_clarifications) & set(required_clarifications))
    score = asked_required / total_required - 0.1 * unnecessary_clarifications
    return max(0.0, min(1.0, score))


def grade_episode(
    agent_type: str,
    agent_component: str,
    agent_severity: str,
    agent_next_action: str,
    true_type: str,
    true_component: str,
    true_severity: str,
    gold_next_action: str,
    asked_clarifications: List[str],
    required_clarifications: List[str],
    unnecessary_clarifications: int,
    security_flag: bool,
    agent_escalated: bool,
    step_count: int,
) -> float:
    """Grade a finished episode and return a deterministic score in [0.0, 1.0]."""
    return grade_episode_breakdown(
        agent_type=agent_type,
        agent_component=agent_component,
        agent_severity=agent_severity,
        agent_next_action=agent_next_action,
        true_type=true_type,
        true_component=true_component,
        true_severity=true_severity,
        gold_next_action=gold_next_action,
        asked_clarifications=asked_clarifications,
        required_clarifications=required_clarifications,
        unnecessary_clarifications=unnecessary_clarifications,
        security_flag=security_flag,
        agent_escalated=agent_escalated,
        step_count=step_count,
    ).final_score


def grade_episode_breakdown(
    agent_type: str,
    agent_component: str,
    agent_severity: str,
    agent_next_action: str,
    true_type: str,
    true_component: str,
    true_severity: str,
    gold_next_action: str,
    asked_clarifications: List[str],
    required_clarifications: List[str],
    unnecessary_clarifications: int,
    security_flag: bool,
    agent_escalated: bool,
    step_count: int,
) -> ScoreBreakdown:
    """Return full deterministic score breakdown for a finished episode."""
    classification = 1.0 if agent_type == true_type else 0.0
    component = component_score(agent_component, true_component)
    severity = severity_score(agent_severity, true_severity)
    clarification = clarification_score(
        asked_clarifications,
        required_clarifications,
        unnecessary_clarifications,
    )

    if security_flag and agent_escalated:
        next_action = 1.0
    elif not security_flag:
        next_action = next_action_score(agent_next_action, gold_next_action)
    else:
        next_action = 0.0

    raw_score = (
        0.25 * classification
        + 0.30 * component
        + 0.20 * severity
        + 0.15 * clarification
        + 0.10 * next_action
    )

    penalty_multiplier = 1.0
    if step_count > 6:
        loop_penalty = 0.05 * (step_count - 6)
        penalty_multiplier = max(0.0, 1.0 - loop_penalty)
    if step_count < 2:
        penalty_multiplier *= 0.7

    final_score = raw_score * penalty_multiplier
    if security_flag and not agent_escalated:
        final_score = min(final_score, 0.2)
    final_score = max(0.01, min(0.99, final_score))

    return ScoreBreakdown(
        classification=classification,
        component=component,
        severity=severity,
        clarification=clarification,
        next_action=next_action,
        raw_score=raw_score,
        penalty_multiplier=penalty_multiplier,
        final_score=final_score,
    )


def submit_has_all_required_fields(agent_decisions: Dict[str, Any]) -> bool:
    """Return True when submit payload includes all required triage fields."""
    required = ["issue_type", "component", "severity", "next_action"]
    return all(bool(agent_decisions.get(key)) for key in required)

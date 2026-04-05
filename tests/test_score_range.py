"""
test_score_range.py — Verify grader always returns scores in [0.0, 1.0].

Tests the grading function across various scenarios (perfect, partial, worst-case)
to ensure the final score is always within the valid range.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Stub grader — mirrors the deterministic scoring formula from SCORING_RUBRIC.md
# Replace with `from my_env.grader import grade_episode` once implemented.
# ---------------------------------------------------------------------------


def _severity_score(agent: str, truth: str) -> float:
    """Score severity with partial credit for off-by-one."""
    levels = ["S0_critical", "S1_major", "S2_minor", "S3_cosmetic"]
    if agent == truth:
        return 1.0
    try:
        diff = abs(levels.index(agent) - levels.index(truth))
    except ValueError:
        return 0.0
    if diff == 1:
        return 0.5
    return 0.0


def _clarification_score(
    asked: list[str], required: list[str], unnecessary_count: int = 0
) -> float:
    """Score clarification behavior."""
    total_required = len(required)
    if total_required == 0:
        return 0.8 if unnecessary_count > 0 else 1.0
    asked_required = len(set(asked) & set(required))
    score = asked_required / total_required - 0.1 * unnecessary_count
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
    asked_clarifications: list[str],
    required_clarifications: list[str],
    unnecessary_clarifications: int,
    security_flag: bool,
    agent_escalated: bool,
    step_count: int,
) -> float:
    """
    Deterministic grading function.
    Returns a score in [0.0, 1.0].
    """
    # Per-criterion scores
    classification = 1.0 if agent_type == true_type else 0.0
    component = 1.0 if agent_component == true_component else 0.0
    severity = _severity_score(agent_severity, true_severity)
    clarification = _clarification_score(
        asked_clarifications, required_clarifications, unnecessary_clarifications
    )

    # For security scenarios, EscalateToHuman is the gold next action
    if security_flag and agent_escalated:
        next_action = 1.0
    elif not security_flag:
        next_action = 1.0 if agent_next_action == gold_next_action else 0.0
    else:
        next_action = 0.0

    # Weighted sum
    raw_score = (
        0.25 * classification
        + 0.30 * component
        + 0.20 * severity
        + 0.15 * clarification
        + 0.10 * next_action
    )

    # Penalty multiplier
    penalty_multiplier = 1.0

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

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, final_score))


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "perfect_easy",
        "params": {
            "agent_type": "bug",
            "agent_component": "backend",
            "agent_severity": "S2_minor",
            "agent_next_action": "schedule_next_sprint",
            "true_type": "bug",
            "true_component": "backend",
            "true_severity": "S2_minor",
            "gold_next_action": "schedule_next_sprint",
            "asked_clarifications": [],
            "required_clarifications": [],
            "unnecessary_clarifications": 0,
            "security_flag": False,
            "agent_escalated": False,
            "step_count": 4,
        },
    },
    {
        "name": "perfect_medium_with_clarification",
        "params": {
            "agent_type": "bug",
            "agent_component": "frontend",
            "agent_severity": "S1_major",
            "agent_next_action": "fix_immediately",
            "true_type": "bug",
            "true_component": "frontend",
            "true_severity": "S1_major",
            "gold_next_action": "fix_immediately",
            "asked_clarifications": ["missing_logs"],
            "required_clarifications": ["missing_logs"],
            "unnecessary_clarifications": 0,
            "security_flag": False,
            "agent_escalated": False,
            "step_count": 5,
        },
    },
    {
        "name": "perfect_hard_escalation",
        "params": {
            "agent_type": "bug",
            "agent_component": "auth",
            "agent_severity": "S0_critical",
            "agent_next_action": "",
            "true_type": "bug",
            "true_component": "auth",
            "true_severity": "S0_critical",
            "gold_next_action": "fix_immediately",
            "asked_clarifications": ["missing_repro_steps"],
            "required_clarifications": ["missing_repro_steps"],
            "unnecessary_clarifications": 0,
            "security_flag": True,
            "agent_escalated": True,
            "step_count": 4,
        },
    },
    {
        "name": "everything_wrong",
        "params": {
            "agent_type": "feature_request",
            "agent_component": "mobile",
            "agent_severity": "S3_cosmetic",
            "agent_next_action": "close_as_wontfix",
            "true_type": "bug",
            "true_component": "backend",
            "true_severity": "S0_critical",
            "gold_next_action": "fix_immediately",
            "asked_clarifications": [],
            "required_clarifications": ["missing_logs", "missing_repro_steps"],
            "unnecessary_clarifications": 0,
            "security_flag": False,
            "agent_escalated": False,
            "step_count": 3,
        },
    },
    {
        "name": "submit_too_early",
        "params": {
            "agent_type": "bug",
            "agent_component": "backend",
            "agent_severity": "S2_minor",
            "agent_next_action": "schedule_next_sprint",
            "true_type": "bug",
            "true_component": "backend",
            "true_severity": "S2_minor",
            "gold_next_action": "schedule_next_sprint",
            "asked_clarifications": [],
            "required_clarifications": [],
            "unnecessary_clarifications": 0,
            "security_flag": False,
            "agent_escalated": False,
            "step_count": 1,
        },
    },
    {
        "name": "excessive_looping",
        "params": {
            "agent_type": "bug",
            "agent_component": "backend",
            "agent_severity": "S2_minor",
            "agent_next_action": "schedule_next_sprint",
            "true_type": "bug",
            "true_component": "backend",
            "true_severity": "S2_minor",
            "gold_next_action": "schedule_next_sprint",
            "asked_clarifications": [],
            "required_clarifications": [],
            "unnecessary_clarifications": 0,
            "security_flag": False,
            "agent_escalated": False,
            "step_count": 10,
        },
    },
    {
        "name": "security_not_escalated",
        "params": {
            "agent_type": "bug",
            "agent_component": "auth",
            "agent_severity": "S0_critical",
            "agent_next_action": "fix_immediately",
            "true_type": "bug",
            "true_component": "auth",
            "true_severity": "S0_critical",
            "gold_next_action": "fix_immediately",
            "asked_clarifications": [],
            "required_clarifications": [],
            "unnecessary_clarifications": 0,
            "security_flag": True,
            "agent_escalated": False,
            "step_count": 4,
        },
    },
    {
        "name": "partial_severity_off_by_one",
        "params": {
            "agent_type": "bug",
            "agent_component": "backend",
            "agent_severity": "S1_major",
            "agent_next_action": "schedule_next_sprint",
            "true_type": "bug",
            "true_component": "backend",
            "true_severity": "S2_minor",
            "gold_next_action": "schedule_next_sprint",
            "asked_clarifications": [],
            "required_clarifications": [],
            "unnecessary_clarifications": 0,
            "security_flag": False,
            "agent_escalated": False,
            "step_count": 4,
        },
    },
]


class TestScoreRange:
    """Verify grader score is always in [0.0, 1.0] for all scenarios."""

    @pytest.mark.parametrize(
        "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
    )
    def test_score_in_valid_range(self, scenario):
        score = grade_episode(**scenario["params"])
        assert 0.0 <= score <= 1.0, (
            f"Score {score} out of range for scenario '{scenario['name']}'"
        )

    @pytest.mark.parametrize(
        "scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS]
    )
    def test_score_is_float(self, scenario):
        score = grade_episode(**scenario["params"])
        assert isinstance(score, float), f"Score must be float, got {type(score)}"

    def test_perfect_easy_score_is_one(self):
        """A perfect easy scenario should score exactly 1.0."""
        score = grade_episode(**SCENARIOS[0]["params"])
        assert score == pytest.approx(1.0), f"Perfect easy score should be 1.0, got {score}"

    def test_everything_wrong_score_is_low(self):
        """All-wrong scenario should score very low."""
        score = grade_episode(**SCENARIOS[3]["params"])
        assert score < 0.3, f"All-wrong score should be < 0.3, got {score}"

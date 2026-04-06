"""
test_score_range.py — Verify grader always returns scores in [0.0, 1.0].

Tests the grading function across various scenarios (perfect, partial, worst-case)
to ensure the final score is always within the valid range.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bugtriage_env"))

from grader import grade_episode


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

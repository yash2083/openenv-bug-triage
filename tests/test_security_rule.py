"""
test_security_rule.py — Verify security flag scoring rules.

For hard scenarios with security_flag=True:
- If the agent does NOT escalate → score is capped at 0.2
- If the agent escalates correctly → normal scoring applies
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the grader (reuse from test_score_range until real grader is available)
from tests.test_score_range import grade_episode


# ---------------------------------------------------------------------------
# Security scenario ground truth
# ---------------------------------------------------------------------------

SECURITY_SCENARIO_TRUTH = {
    "true_type": "bug",
    "true_component": "auth",
    "true_severity": "S0_critical",
    "gold_next_action": "fix_immediately",
    "required_clarifications": ["missing_repro_steps"],
    "security_flag": True,
}


class TestSecurityRule:
    """Tests for the security_flag scoring override."""

    def test_no_escalation_caps_score_at_02(self):
        """
        When security_flag is True and agent does NOT escalate,
        the final score must be capped at 0.2 — even if all other
        fields are correct.
        """
        score = grade_episode(
            agent_type="bug",
            agent_component="auth",
            agent_severity="S0_critical",
            agent_next_action="fix_immediately",
            asked_clarifications=["missing_repro_steps"],
            unnecessary_clarifications=0,
            agent_escalated=False,
            step_count=5,
            **{
                k: v
                for k, v in SECURITY_SCENARIO_TRUTH.items()
                if k not in ("security_flag",)
            },
            security_flag=True,
        )
        assert score <= 0.2, (
            f"Security scenario without escalation should be capped at 0.2, got {score}"
        )

    def test_escalation_gives_normal_score(self):
        """
        When security_flag is True and agent DOES escalate,
        the score should be computed normally (no cap).
        """
        score = grade_episode(
            agent_type="bug",
            agent_component="auth",
            agent_severity="S0_critical",
            agent_next_action="",
            asked_clarifications=["missing_repro_steps"],
            unnecessary_clarifications=0,
            agent_escalated=True,
            step_count=4,
            **{
                k: v
                for k, v in SECURITY_SCENARIO_TRUTH.items()
                if k not in ("security_flag",)
            },
            security_flag=True,
        )
        assert score > 0.2, (
            f"Security scenario with correct escalation should score > 0.2, got {score}"
        )

    def test_escalation_score_in_range(self):
        """Escalated security scenario score must still be in [0.0, 1.0]."""
        score = grade_episode(
            agent_type="bug",
            agent_component="auth",
            agent_severity="S0_critical",
            agent_next_action="",
            asked_clarifications=["missing_repro_steps"],
            unnecessary_clarifications=0,
            agent_escalated=True,
            step_count=4,
            **{
                k: v
                for k, v in SECURITY_SCENARIO_TRUTH.items()
                if k not in ("security_flag",)
            },
            security_flag=True,
        )
        assert 0.0 <= score <= 1.0

    def test_no_escalation_wrong_fields_still_capped(self):
        """
        Even with wrong classification + component, the cap at 0.2 must hold
        (score should be ≤ 0.2, potentially lower).
        """
        score = grade_episode(
            agent_type="feature_request",
            agent_component="frontend",
            agent_severity="S3_cosmetic",
            agent_next_action="close_as_wontfix",
            true_type="bug",
            true_component="auth",
            true_severity="S0_critical",
            gold_next_action="fix_immediately",
            asked_clarifications=[],
            required_clarifications=["missing_repro_steps"],
            unnecessary_clarifications=0,
            security_flag=True,
            agent_escalated=False,
            step_count=3,
        )
        assert score <= 0.2, (
            f"Wrong fields + no escalation on security scenario should be ≤ 0.2, got {score}"
        )

    def test_non_security_flag_no_cap(self):
        """
        When security_flag is False, there should be no 0.2 cap
        even if agent doesn't escalate.
        """
        score = grade_episode(
            agent_type="bug",
            agent_component="backend",
            agent_severity="S2_minor",
            agent_next_action="schedule_next_sprint",
            true_type="bug",
            true_component="backend",
            true_severity="S2_minor",
            gold_next_action="schedule_next_sprint",
            asked_clarifications=[],
            required_clarifications=[],
            unnecessary_clarifications=0,
            security_flag=False,
            agent_escalated=False,
            step_count=4,
        )
        assert score > 0.2, (
            f"Non-security perfect scenario should score > 0.2, got {score}"
        )

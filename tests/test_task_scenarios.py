"""
test_task_scenarios.py — Validate task scenario files and grading integration.

Tests that all task JSON files are valid, follow schema rules, and integrate
correctly with the grading system.
"""

import json
import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the grading function from test_score_range.py
from tests.test_score_range import grade_episode


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def load_task_file(filename: str) -> list:
    """Load a task JSON file."""
    tasks_dir = Path(__file__).parent.parent / "tasks"
    file_path = tasks_dir / filename
    with open(file_path, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test Class: TestTaskFilesLoad
# ---------------------------------------------------------------------------

class TestTaskFilesLoad:
    """Test that all task files load correctly."""

    def test_easy_file_loads(self):
        """Easy task file should parse without error."""
        scenarios = load_task_file("issues_easy.json")
        assert isinstance(scenarios, list), "Easy file should contain a JSON array"

    def test_medium_file_loads(self):
        """Medium task file should parse without error."""
        scenarios = load_task_file("issues_medium.json")
        assert isinstance(scenarios, list), "Medium file should contain a JSON array"

    def test_hard_file_loads(self):
        """Hard task file should parse without error."""
        scenarios = load_task_file("issues_hard.json")
        assert isinstance(scenarios, list), "Hard file should contain a JSON array"

    def test_easy_has_minimum_scenarios(self):
        """Easy file should have at least 4 scenarios."""
        scenarios = load_task_file("issues_easy.json")
        assert len(scenarios) >= 4, f"Expected at least 4 easy scenarios, got {len(scenarios)}"

    def test_medium_has_minimum_scenarios(self):
        """Medium file should have at least 4 scenarios."""
        scenarios = load_task_file("issues_medium.json")
        assert len(scenarios) >= 4, f"Expected at least 4 medium scenarios, got {len(scenarios)}"

    def test_hard_has_minimum_scenarios(self):
        """Hard file should have at least 4 scenarios."""
        scenarios = load_task_file("issues_hard.json")
        assert len(scenarios) >= 4, f"Expected at least 4 hard scenarios, got {len(scenarios)}"


# ---------------------------------------------------------------------------
# Test Class: TestEasyScenarioSchema
# ---------------------------------------------------------------------------

class TestEasyScenarioSchema:
    """Test that easy scenarios follow schema rules."""

    @pytest.fixture
    def easy_scenarios(self):
        """Load easy scenarios."""
        return load_task_file("issues_easy.json")

    def test_all_required_fields_present(self, easy_scenarios):
        """Every easy scenario should have all required fields."""
        required_fields = [
            "issue_id", "title", "description", "reporter_type", "environment",
            "logs_excerpt", "true_type", "true_component", "true_severity",
            "required_clarifications", "gold_next_action", "security_flag", "difficulty"
        ]
        for scenario in easy_scenarios:
            for field in required_fields:
                assert field in scenario, f"Scenario {scenario.get('issue_id')} missing field: {field}"

    def test_required_clarifications_empty(self, easy_scenarios):
        """Easy scenarios should have empty required_clarifications."""
        for scenario in easy_scenarios:
            assert scenario["required_clarifications"] == [], \
                f"Easy scenario {scenario['issue_id']} should have empty required_clarifications"

    def test_security_flag_false(self, easy_scenarios):
        """Easy scenarios should have security_flag=false."""
        for scenario in easy_scenarios:
            assert scenario["security_flag"] is False, \
                f"Easy scenario {scenario['issue_id']} should have security_flag=false"

    def test_difficulty_is_easy(self, easy_scenarios):
        """Easy scenarios should have difficulty='easy'."""
        for scenario in easy_scenarios:
            assert scenario["difficulty"] == "easy", \
                f"Easy scenario {scenario['issue_id']} should have difficulty='easy'"


# ---------------------------------------------------------------------------
# Test Class: TestMediumScenarioSchema
# ---------------------------------------------------------------------------

class TestMediumScenarioSchema:
    """Test that medium scenarios follow schema rules."""

    @pytest.fixture
    def medium_scenarios(self):
        """Load medium scenarios."""
        return load_task_file("issues_medium.json")

    def test_exactly_one_clarification(self, medium_scenarios):
        """Medium scenarios should have exactly 1 required_clarification."""
        for scenario in medium_scenarios:
            clarifications = scenario["required_clarifications"]
            assert len(clarifications) == 1, \
                f"Medium scenario {scenario['issue_id']} should have exactly 1 clarification, got {len(clarifications)}"

    def test_security_flag_false(self, medium_scenarios):
        """Medium scenarios should have security_flag=false."""
        for scenario in medium_scenarios:
            assert scenario["security_flag"] is False, \
                f"Medium scenario {scenario['issue_id']} should have security_flag=false"

    def test_difficulty_is_medium(self, medium_scenarios):
        """Medium scenarios should have difficulty='medium'."""
        for scenario in medium_scenarios:
            assert scenario["difficulty"] == "medium", \
                f"Medium scenario {scenario['issue_id']} should have difficulty='medium'"


# ---------------------------------------------------------------------------
# Test Class: TestHardScenarioSchema
# ---------------------------------------------------------------------------

class TestHardScenarioSchema:
    """Test that hard scenarios follow schema rules."""

    @pytest.fixture
    def hard_scenarios(self):
        """Load hard scenarios."""
        return load_task_file("issues_hard.json")

    def test_has_security_flagged_scenarios(self, hard_scenarios):
        """At least 1 and at most 4 hard scenarios should have security_flag=true."""
        security_count = sum(1 for s in hard_scenarios if s["security_flag"])
        assert 1 <= security_count <= 4, \
            f"Expected 1-4 security-flagged scenarios, got {security_count}"

    def test_security_scenarios_use_critical_severity(self, hard_scenarios):
        """Security-flagged scenarios should use S0_critical severity."""
        for scenario in hard_scenarios:
            if scenario["security_flag"]:
                assert scenario["true_severity"] == "S0_critical", \
                    f"Security scenario {scenario['issue_id']} should use S0_critical severity"

    def test_difficulty_is_hard(self, hard_scenarios):
        """Hard scenarios should have difficulty='hard'."""
        for scenario in hard_scenarios:
            assert scenario["difficulty"] == "hard", \
                f"Hard scenario {scenario['issue_id']} should have difficulty='hard'"


# ---------------------------------------------------------------------------
# Test Class: TestGradingIntegration
# ---------------------------------------------------------------------------

class TestGradingIntegration:
    """Test that scenarios integrate correctly with the grading system."""

    def test_easy_perfect_score(self):
        """Easy scenario with perfect agent decisions should score >= 0.9."""
        # Load first easy scenario
        scenarios = load_task_file("issues_easy.json")
        scenario = scenarios[0]

        # Perfect agent decisions
        score = grade_episode(
            agent_type=scenario["true_type"],
            agent_component=scenario["true_component"],
            agent_severity=scenario["true_severity"],
            agent_next_action=scenario["gold_next_action"],
            true_type=scenario["true_type"],
            true_component=scenario["true_component"],
            true_severity=scenario["true_severity"],
            gold_next_action=scenario["gold_next_action"],
            asked_clarifications=[],
            required_clarifications=scenario["required_clarifications"],
            unnecessary_clarifications=0,
            security_flag=scenario["security_flag"],
            agent_escalated=False,
            step_count=4,
        )

        assert score >= 0.9, f"Perfect easy scenario should score >= 0.9, got {score}"

    def test_medium_without_clarification_penalized(self):
        """Medium scenario without asking clarification should be penalized."""
        # Load first medium scenario
        scenarios = load_task_file("issues_medium.json")
        scenario = scenarios[0]

        # Agent doesn't ask required clarification
        score = grade_episode(
            agent_type=scenario["true_type"],
            agent_component=scenario["true_component"],
            agent_severity=scenario["true_severity"],
            agent_next_action=scenario["gold_next_action"],
            true_type=scenario["true_type"],
            true_component=scenario["true_component"],
            true_severity=scenario["true_severity"],
            gold_next_action=scenario["gold_next_action"],
            asked_clarifications=[],  # Didn't ask
            required_clarifications=scenario["required_clarifications"],
            unnecessary_clarifications=0,
            security_flag=scenario["security_flag"],
            agent_escalated=False,
            step_count=4,
        )

        # Should be penalized for missing clarification
        assert score < 0.9, f"Missing clarification should reduce score below 0.9, got {score}"

    def test_medium_with_correct_clarification(self):
        """Medium scenario with correct clarification should score >= 0.8."""
        # Load first medium scenario
        scenarios = load_task_file("issues_medium.json")
        scenario = scenarios[0]

        # Agent asks the required clarification
        score = grade_episode(
            agent_type=scenario["true_type"],
            agent_component=scenario["true_component"],
            agent_severity=scenario["true_severity"],
            agent_next_action=scenario["gold_next_action"],
            true_type=scenario["true_type"],
            true_component=scenario["true_component"],
            true_severity=scenario["true_severity"],
            gold_next_action=scenario["gold_next_action"],
            asked_clarifications=scenario["required_clarifications"],  # Asked correctly
            required_clarifications=scenario["required_clarifications"],
            unnecessary_clarifications=0,
            security_flag=scenario["security_flag"],
            agent_escalated=False,
            step_count=6,
        )

        assert score >= 0.8, f"Correct clarification should score >= 0.8, got {score}"

    def test_hard_security_with_escalation(self):
        """Hard security scenario with escalation should score > 0.2."""
        # Load hard scenarios and find a security-flagged one
        scenarios = load_task_file("issues_hard.json")
        security_scenario = next(s for s in scenarios if s["security_flag"])

        # Agent correctly escalates
        score = grade_episode(
            agent_type=security_scenario["true_type"],
            agent_component=security_scenario["true_component"],
            agent_severity=security_scenario["true_severity"],
            agent_next_action=security_scenario["gold_next_action"],
            true_type=security_scenario["true_type"],
            true_component=security_scenario["true_component"],
            true_severity=security_scenario["true_severity"],
            gold_next_action=security_scenario["gold_next_action"],
            asked_clarifications=[],
            required_clarifications=security_scenario["required_clarifications"],
            unnecessary_clarifications=0,
            security_flag=security_scenario["security_flag"],
            agent_escalated=True,  # Correctly escalated
            step_count=4,
        )

        assert score > 0.2, f"Security scenario with escalation should score > 0.2, got {score}"

    def test_hard_security_without_escalation_capped(self):
        """Hard security scenario without escalation should score <= 0.2."""
        # Load hard scenarios and find a security-flagged one
        scenarios = load_task_file("issues_hard.json")
        security_scenario = next(s for s in scenarios if s["security_flag"])

        # Agent fails to escalate (treats as normal bug)
        score = grade_episode(
            agent_type=security_scenario["true_type"],
            agent_component=security_scenario["true_component"],
            agent_severity=security_scenario["true_severity"],
            agent_next_action=security_scenario["gold_next_action"],
            true_type=security_scenario["true_type"],
            true_component=security_scenario["true_component"],
            true_severity=security_scenario["true_severity"],
            gold_next_action=security_scenario["gold_next_action"],
            asked_clarifications=[],
            required_clarifications=security_scenario["required_clarifications"],
            unnecessary_clarifications=0,
            security_flag=security_scenario["security_flag"],
            agent_escalated=False,  # Failed to escalate
            step_count=4,
        )

        assert score <= 0.2, f"Security scenario without escalation should score <= 0.2, got {score}"

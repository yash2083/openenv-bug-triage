"""
test_reset_step.py — Basic environment reset/step contract tests.

Verifies:
1. reset() returns a valid observation with all required fields.
2. step() with a valid action returns (obs, reward, done, info) without crashing.
"""

import pytest
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Fixtures — minimal stub env for testing when real env is not yet available
# ---------------------------------------------------------------------------

SAMPLE_SCENARIO = {
    "issue_id": "TRIAGE-TEST-001",
    "title": "Test issue for unit testing",
    "description": "This is a test issue to verify reset and step behavior.",
    "reporter_type": "internal",
    "environment": {
        "os": "Linux",
        "browser": "Chrome 124.0",
        "app_version": "1.0.0",
        "device": "Desktop",
    },
    "logs_excerpt": "ERROR test.module - TestException: something went wrong",
    "true_type": "bug",
    "true_component": "backend",
    "true_severity": "S2_minor",
    "required_clarifications": [],
    "gold_next_action": "schedule_next_sprint",
    "security_flag": False,
    "difficulty": "easy",
}

REQUIRED_OBS_FIELDS = {
    "issue_id",
    "title",
    "description",
    "reporter_type",
    "environment",
    "conversation_history",
    "step_count",
    "max_steps",
}

VALID_ACTION = {
    "action_type": "SetClassification",
    "payload": {"issue_type": "bug"},
}


class StubEnv:
    """Minimal environment stub for contract testing before real env is built."""

    def __init__(self, scenario: dict):
        self.scenario = scenario
        self._step_count = 0
        self._max_steps = 10
        self._done = False
        self._decisions = {}

    def reset(self) -> dict:
        self._step_count = 0
        self._done = False
        self._decisions = {}
        return {
            "issue_id": self.scenario["issue_id"],
            "title": self.scenario["title"],
            "description": self.scenario["description"],
            "reporter_type": self.scenario["reporter_type"],
            "environment": self.scenario["environment"],
            "logs_excerpt": self.scenario.get("logs_excerpt"),
            "attachments_present": False,
            "conversation_history": [
                {"role": "reporter", "message": self.scenario["description"]}
            ],
            "step_count": self._step_count,
            "max_steps": self._max_steps,
            "available_actions": [
                "AskClarification",
                "SetClassification",
                "SetSeverity",
                "AssignComponent",
                "ProposeNextAction",
                "SubmitTriage",
                "EscalateToHuman",
            ],
        }

    def step(self, action: dict) -> tuple:
        self._step_count += 1
        done = action["action_type"] in ("SubmitTriage", "EscalateToHuman")
        if self._step_count >= self._max_steps:
            done = True
        self._done = done

        obs = {
            "issue_id": self.scenario["issue_id"],
            "title": self.scenario["title"],
            "description": self.scenario["description"],
            "reporter_type": self.scenario["reporter_type"],
            "environment": self.scenario["environment"],
            "logs_excerpt": self.scenario.get("logs_excerpt"),
            "attachments_present": False,
            "conversation_history": [
                {"role": "reporter", "message": self.scenario["description"]}
            ],
            "step_count": self._step_count,
            "max_steps": self._max_steps,
            "available_actions": [
                "AskClarification",
                "SetClassification",
                "SetSeverity",
                "AssignComponent",
                "ProposeNextAction",
                "SubmitTriage",
                "EscalateToHuman",
            ],
        }

        reward = 0.0
        info = {"action_accepted": True}

        return (obs, reward, done, info)


@pytest.fixture
def env():
    """Provide a fresh environment instance for each test."""
    return StubEnv(SAMPLE_SCENARIO)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReset:
    """Tests for env.reset() contract."""

    def test_reset_returns_dict(self, env):
        obs = env.reset()
        assert isinstance(obs, dict), "reset() must return a dict observation"

    def test_reset_has_required_fields(self, env):
        obs = env.reset()
        missing = REQUIRED_OBS_FIELDS - set(obs.keys())
        assert not missing, f"Observation missing required fields: {missing}"

    def test_reset_step_count_is_zero(self, env):
        obs = env.reset()
        assert obs["step_count"] == 0, "step_count should be 0 after reset"

    def test_reset_max_steps_positive(self, env):
        obs = env.reset()
        assert obs["max_steps"] > 0, "max_steps must be positive"

    def test_reset_conversation_history_non_empty(self, env):
        obs = env.reset()
        assert len(obs["conversation_history"]) >= 1, (
            "conversation_history must have at least the reporter message"
        )

    def test_reset_issue_id_matches(self, env):
        obs = env.reset()
        assert obs["issue_id"] == SAMPLE_SCENARIO["issue_id"]


class TestStep:
    """Tests for env.step(action) contract."""

    def test_step_returns_tuple_of_four(self, env):
        env.reset()
        result = env.step(VALID_ACTION)
        assert isinstance(result, tuple), "step() must return a tuple"
        assert len(result) == 4, "step() must return (obs, reward, done, info)"

    def test_step_obs_is_dict(self, env):
        env.reset()
        obs, _, _, _ = env.step(VALID_ACTION)
        assert isinstance(obs, dict)

    def test_step_reward_is_float(self, env):
        env.reset()
        _, reward, _, _ = env.step(VALID_ACTION)
        assert isinstance(reward, (int, float)), "reward must be numeric"

    def test_step_done_is_bool(self, env):
        env.reset()
        _, _, done, _ = env.step(VALID_ACTION)
        assert isinstance(done, bool), "done must be a boolean"

    def test_step_info_is_dict(self, env):
        env.reset()
        _, _, _, info = env.step(VALID_ACTION)
        assert isinstance(info, dict), "info must be a dict"

    def test_step_increments_step_count(self, env):
        env.reset()
        obs, _, _, _ = env.step(VALID_ACTION)
        assert obs["step_count"] == 1

    def test_submit_triage_ends_episode(self, env):
        env.reset()
        submit_action = {
            "action_type": "SubmitTriage",
            "payload": {
                "summary": "Test summary",
                "final_decision": {
                    "issue_type": "bug",
                    "severity": "S2_minor",
                    "component": "backend",
                    "next_action": "schedule_next_sprint",
                },
            },
        }
        _, _, done, _ = env.step(submit_action)
        assert done is True, "SubmitTriage must end the episode"

    def test_escalate_ends_episode(self, env):
        env.reset()
        escalate_action = {
            "action_type": "EscalateToHuman",
            "payload": {"reason": "Security concern"},
        }
        _, _, done, _ = env.step(escalate_action)
        assert done is True, "EscalateToHuman must end the episode"

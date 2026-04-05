# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""Bug/Issue Triage Environment Client."""

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import (
    BugtriageAction,
    BugtriageObservation,
    ConversationEntry,
    EnvironmentInfo,
)


class BugtriageEnv(
    EnvClient[BugtriageAction, BugtriageObservation, State]
):
    """
    Client for the Bug/Issue Triage Environment.

    This client maintains a persistent WebSocket connection to the environment server,
    enabling efficient multi-step interactions with lower latency.
    Each client instance has its own dedicated environment session on the server.

    Example:
        >>> with BugtriageEnv(base_url="http://localhost:8000") as client:
        ...     result = client.reset()
        ...     print(result.observation.title)
        ...
        ...     action = BugtriageAction(
        ...         action_type="SetClassification",
        ...         issue_type="bug"
        ...     )
        ...     result = client.step(action)
        ...     print(result.observation.step_count)
    """

    def _step_payload(self, action: BugtriageAction) -> Dict[str, Any]:
        """Convert BugtriageAction to JSON payload for step message."""
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[BugtriageObservation]:
        """Parse server response into StepResult[BugtriageObservation]."""
        obs_data = payload.get("observation", {})

        # Parse conversation history
        conv_history = [
            ConversationEntry(role=e["role"], message=e["message"])
            for e in obs_data.get("conversation_history", [])
        ]

        # Parse environment info
        env_data = obs_data.get("environment")
        env_info = EnvironmentInfo(**env_data) if env_data else None

        observation = BugtriageObservation(
            issue_id=obs_data.get("issue_id", ""),
            title=obs_data.get("title", ""),
            description=obs_data.get("description", ""),
            reporter_type=obs_data.get("reporter_type", ""),
            environment=env_info,
            logs_excerpt=obs_data.get("logs_excerpt"),
            attachments_present=obs_data.get("attachments_present", False),
            conversation_history=conv_history,
            step_count=obs_data.get("step_count", 0),
            max_steps=obs_data.get("max_steps", 10),
            available_actions=obs_data.get("available_actions", []),
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> State:
        """Parse server response into State object."""
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )

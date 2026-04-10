#!/usr/bin/env python3
"""Baseline inference runner for the Bug/Issue Triage OpenEnv environment.

This script connects to an OpenEnv-compatible server and drives episodes using an
Hugging Face Router via the OpenAI-compatible client.

Requirements:
- HF_TOKEN must be set (optionally via .env).
- Environment server must be running (default: http://localhost:8000).

The runner evaluates all task sets: easy, medium, and hard.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List

from openai import OpenAI

from bugtriage_env.client import BugtriageEnv
from bugtriage_env.models import BugtriageAction


def _load_dotenv_if_present(path: str = ".env") -> None:
    """Load key=value pairs from .env into process env if not already set."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        # Non-fatal: environment may already be set by shell/CI.
        return


def _mask_secret(secret: str) -> str:
    if len(secret) <= 8:
        return "***"
    return f"{secret[:6]}...{secret[-4:]}"


ROUTER_API_BASE_URL = "https://router.huggingface.co/v1"


def _resolve_openai_base_url(base_url: str) -> tuple[str, str | None]:
    """Return a safe OpenAI-compatible base URL for this challenge configuration."""
    candidate = (base_url or "").strip().rstrip("/")
    if not candidate:
        return ROUTER_API_BASE_URL, "API_BASE_URL was empty; using Hugging Face Router default."

    lower = candidate.lower()
    if not lower.startswith("https://") or "router.huggingface.co" not in lower:
        return (
            ROUTER_API_BASE_URL,
            "API_BASE_URL is not a valid Hugging Face Router URL in this configuration; "
            f"falling back to {ROUTER_API_BASE_URL}.",
        )

    if lower == "https://router.huggingface.co":
        return ROUTER_API_BASE_URL, f"Normalized API_BASE_URL to {ROUTER_API_BASE_URL}."

    return candidate, None


_load_dotenv_if_present()


DEFAULT_BASE_URL = os.environ.get("ENV_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_API_BASE_URL = os.environ.get("API_BASE_URL", ROUTER_API_BASE_URL).rstrip("/")
DEFAULT_MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
MAX_STEPS = int(os.environ.get("BASELINE_MAX_STEPS", "8"))
EPISODES_PER_SET = int(os.environ.get("BASELINE_EPISODES_PER_SET", "5"))
CONFIDENCE_THRESHOLD = float(os.environ.get("BASELINE_CONFIDENCE_THRESHOLD", "0.70"))
HF_TOKEN = (os.environ.get("HF_TOKEN") or "").strip()


ALLOWED_ACTIONS = [
    "AskClarification",
    "SetClassification",
    "SetSeverity",
    "AssignComponent",
    "ProposeNextAction",
    "SubmitTriage",
    "EscalateToHuman",
]

VALID_QUESTION_TYPES = {
    "missing_repro_steps",
    "missing_environment",
    "missing_logs",
    "missing_expected_behavior",
    "missing_frequency",
    "other",
}

VALID_ISSUE_TYPES = {"bug", "feature_request", "question"}

VALID_SEVERITIES = {
    "S0_critical",
    "S1_major",
    "S2_minor",
    "S3_cosmetic",
}

VALID_COMPONENTS = {
    "backend",
    "frontend",
    "database",
    "auth",
    "payments",
    "notifications",
    "infrastructure",
    "mobile",
    "api",
    "unknown",
}

VALID_NEXT_ACTIONS = {
    "fix_immediately",
    "schedule_next_sprint",
    "add_to_backlog",
    "needs_investigation",
    "close_as_duplicate",
    "close_as_wontfix",
}


def _coerce_string(value: Any, default: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Some models emit {"name": ..., "description": ...}
        name = value.get("name")
        if isinstance(name, str):
            return name
    return default


def _normalize_enum(value: Any, allowed: set[str], default: str) -> str:
    candidate = _coerce_string(value, default).strip()
    if candidate in allowed:
        return candidate
    # Soft normalization for common variants.
    lower_map = {item.lower(): item for item in allowed}
    return lower_map.get(candidate.lower(), default)


@dataclass
class EpisodeResult:
    task_set: str
    episode_index: int
    score: float
    reward_sum: float
    steps: int
    escalated: bool
    issue_id: str


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Any) -> None:
    error_val = "null" if error is None else str(error)
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


class HttpJsonClient:
    """Small JSON-over-HTTP helper using only the Python stdlib."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get(self, path: str) -> Dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        return self._send(req)

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        return self._send(req)

    def _send(self, req: urllib.request.Request) -> Dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
            if not data.strip():
                return {}
            return json.loads(data)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from environment API at {req.full_url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code} for {req.full_url}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach environment API at {req.full_url}: {exc}") from exc


class OpenAILLM:
    """OpenAI-compatible chat client configured for HF Router."""

    def __init__(self, api_base_url: str, model_name: str, token: str):
        self.client = OpenAI(api_key=token, base_url=api_base_url.rstrip("/"))
        self.model_name = model_name

    def choose_action(
        self,
        task_set: str,
        observation: Dict[str, Any],
        current_decisions: Dict[str, str],
    ) -> Dict[str, Any]:
        signals = observation.get("extracted_signals") or {}

        rule_action = self._rule_based_action(task_set, observation, current_decisions)
        if rule_action is not None:
            return rule_action

        # Deterministic security fast-path: do not wait when obvious exposure is present.
        if bool(signals.get("likely_security")) and bool(signals.get("has_sensitive_terms")):
            return {
                "action_type": "EscalateToHuman",
                "reason": "Potential privacy/security exposure detected in report evidence.",
                "analysis_summary": "Sensitive/security indicators detected; escalate immediately.",
                "evidence_keys": ["likely_security", "has_sensitive_terms"],
                "confidence": 1.0,
            }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a deterministic triage policy. Return exactly one JSON object. "
                    "Use evidence-driven mapping and avoid guessing."
                ),
            },
            {
                "role": "user",
                "content": self._build_prompt(task_set, observation, current_decisions),
            },
        ]

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
        }

        try:
            raw = self.client.chat.completions.create(**payload)
        except Exception as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc

        try:
            text = raw.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise RuntimeError(f"OpenAI API error: malformed response payload: {exc}") from exc
        if not text:
            raise RuntimeError("OpenAI API error: empty response content")
        try:
            action = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI API error: invalid JSON action: {exc}") from exc

        # Deterministic confidence gate: if low confidence for unresolved stage, ask targeted clarification.
        confidence = action.get("confidence")
        unresolved = self._next_unresolved_stage(current_decisions)
        if isinstance(confidence, (int, float)) and confidence < CONFIDENCE_THRESHOLD and unresolved:
            qtype = "missing_logs"
            if unresolved == "severity":
                qtype = "missing_frequency"
            elif unresolved == "component":
                qtype = "missing_environment"
            elif unresolved == "issue_type":
                qtype = "missing_expected_behavior"
            return {
                "action_type": "AskClarification",
                "question_type": qtype,
                "question_text": f"Please share more details to confirm {unresolved}.",
                "analysis_summary": f"Low confidence for {unresolved}; requesting clarification.",
                "evidence_keys": ["low_confidence"],
                "confidence": float(confidence),
            }

        return self._normalize_action(action, observation, current_decisions)

    def _rule_based_action(
        self,
        task_set: str,
        observation: Dict[str, Any],
        current_decisions: Dict[str, str],
    ) -> Dict[str, Any] | None:
        """Deterministic staged policy used to stabilize small-model baselines."""
        signals = observation.get("extracted_signals") or {}
        hints = signals.get("explicit_hints") or {}

        issue_type = current_decisions.get("issue_type")
        component = current_decisions.get("component")
        severity = current_decisions.get("severity")
        next_action = current_decisions.get("next_action")

        guessed_issue_type = "feature_request" if bool(signals.get("explicit_feature_request")) else "bug"
        guessed_component = _normalize_enum(signals.get("affected_surface"), VALID_COMPONENTS, "unknown")
        guessed_severity = "S2_minor"
        if bool(signals.get("likely_security")):
            guessed_severity = "S0_critical"
        elif signals.get("outage_scope") in ("segment", "widespread"):
            guessed_severity = "S1_major"

        guessed_next_action = "schedule_next_sprint"
        if guessed_severity in ("S0_critical", "S1_major"):
            guessed_next_action = "fix_immediately"
        if bool(signals.get("likely_duplicate")):
            guessed_next_action = "close_as_duplicate"

        hinted_component = _normalize_enum(hints.get("component_hint"), VALID_COMPONENTS, guessed_component)
        hinted_severity = _normalize_enum(hints.get("severity_hint"), VALID_SEVERITIES, guessed_severity)
        hinted_next_action = _normalize_enum(
            hints.get("next_action_hint"), VALID_NEXT_ACTIONS, guessed_next_action
        )

        # Easy-mode deterministic completion from explicit hints.
        if task_set == "easy":
            if not issue_type:
                return {
                    "action_type": "SetClassification",
                    "issue_type": guessed_issue_type,
                    "analysis_summary": "Deterministic easy-task classification from explicit cues.",
                    "evidence_keys": ["explicit_feature_request"],
                    "confidence": 0.98,
                }
            if not component:
                return {
                    "action_type": "AssignComponent",
                    "component": hinted_component,
                    "analysis_summary": "Deterministic easy-task component from explicit hint.",
                    "evidence_keys": ["component_hint"],
                    "confidence": 0.98,
                }
            if not severity:
                return {
                    "action_type": "SetSeverity",
                    "severity": hinted_severity,
                    "analysis_summary": "Deterministic easy-task severity from explicit hint.",
                    "evidence_keys": ["severity_hint"],
                    "confidence": 0.98,
                }
            if not next_action:
                return {
                    "action_type": "ProposeNextAction",
                    "next_action": hinted_next_action,
                    "analysis_summary": "Deterministic easy-task next action from explicit hint.",
                    "evidence_keys": ["next_action_hint"],
                    "confidence": 0.98,
                }
            return {
                "action_type": "SubmitTriage",
                "summary": "Submitting deterministic easy-task triage decision.",
                "analysis_summary": "All labels resolved deterministically.",
                "evidence_keys": ["all_labels_set"],
                "confidence": 0.98,
            }

        # Medium-mode deterministic first pass before LLM fallback.
        if task_set == "medium":
            if not issue_type:
                return {
                    "action_type": "SetClassification",
                    "issue_type": guessed_issue_type,
                    "analysis_summary": "Medium-task classification from deterministic signals.",
                    "evidence_keys": ["explicit_feature_request"],
                    "confidence": 0.80,
                }
            if not component and guessed_component != "unknown":
                return {
                    "action_type": "AssignComponent",
                    "component": guessed_component,
                    "analysis_summary": "Medium-task component from extracted signals.",
                    "evidence_keys": ["affected_surface"],
                    "confidence": 0.76,
                }
            if not severity:
                return {
                    "action_type": "SetSeverity",
                    "severity": guessed_severity,
                    "analysis_summary": "Medium-task severity from outage scope/security cues.",
                    "evidence_keys": ["outage_scope", "likely_security"],
                    "confidence": 0.74,
                }
            if not next_action:
                return {
                    "action_type": "ProposeNextAction",
                    "next_action": guessed_next_action,
                    "analysis_summary": "Medium-task next action from severity/duplicate cues.",
                    "evidence_keys": ["likely_duplicate", "outage_scope"],
                    "confidence": 0.72,
                }

        return None

    def _next_unresolved_stage(self, current_decisions: Dict[str, str]) -> str:
        if not current_decisions.get("issue_type"):
            return "issue_type"
        if not current_decisions.get("component"):
            return "component"
        if not current_decisions.get("severity"):
            return "severity"
        if not current_decisions.get("next_action"):
            return "next_action"
        return ""

    def _build_prompt(
        self,
        task_set: str,
        observation: Dict[str, Any],
        current_decisions: Dict[str, str],
    ) -> str:
        issue = {
            "issue_id": observation.get("issue_id"),
            "title": observation.get("title"),
            "description": observation.get("description"),
            "reporter_type": observation.get("reporter_type"),
            "environment": observation.get("environment"),
            "logs_excerpt": observation.get("logs_excerpt"),
            "step_count": observation.get("step_count"),
            "max_steps": observation.get("max_steps"),
            "available_actions": observation.get("available_actions") or ALLOWED_ACTIONS,
            "conversation_history": observation.get("conversation_history", []),
            "extracted_signals": observation.get("extracted_signals", {}),
        }

        decisions = current_decisions
        step = observation.get("step_count", 0)
        max_steps = observation.get("max_steps", 8)
        
        # Build decision status field
        classified = bool(decisions.get("issue_type"))
        component_assigned = bool(decisions.get("component"))
        severity_set = bool(decisions.get("severity"))
        next_action_proposed = bool(decisions.get("next_action"))

        decision_status = {
            "issue_type": decisions.get("issue_type") or "(not set)",
            "component": decisions.get("component") or "(not set)",
            "severity": decisions.get("severity") or "(not set)",
            "next_action": decisions.get("next_action") or "(not set)",
        }

        prompt = (
            "TRIAGE DECISION TASK\n"
            f"Step: {step}/{max_steps}\n"
            f"Task set: {task_set}\n\n"
            "CURRENT DECISIONS:\n"
            f"{json.dumps(decision_status, indent=2)}\n\n"
            "DETERMINISTIC SIGNALS (use first):\n"
            f"{json.dumps(issue.get('extracted_signals', {}), indent=2)}\n\n"
            "METHOD (must follow):\n"
            "1. Map evidence to one unresolved label only.\n"
            "2. Avoid guessing; if confidence < 0.70, ask one targeted clarification.\n"
            "3. Use escalation immediately for likely security/privacy exposure.\n"
            "4. Submit only when all four labels are set.\n\n"
            "OUTPUT JSON SCHEMA:\n"
            "- action_type (required)\n"
            "- payload fields for action\n"
            "- analysis_summary (short)\n"
            "- evidence_keys (array of short evidence tags)\n"
            "- confidence (0.0-1.0)\n\n"
        )

        if step >= max_steps - 1:
            prompt += "CRITICAL: Only 1 step left. MUST submit or escalate NOW.\n\n"

        # Add decision guidance
        if not classified:
            prompt += (
                "NEXT ACTION: Classify this issue (bug, feature_request, or question).\n"
                "Example: {\"action_type\":\"SetClassification\",\"issue_type\":\"bug\",\"analysis_summary\":\"...\",\"evidence_keys\":[\"...\"],\"confidence\":0.82}\n\n"
            )
        elif not component_assigned:
            prompt += (
                "NEXT ACTION: Assign component (backend, frontend, database, etc.).\n"
                "Example: {\"action_type\":\"AssignComponent\",\"component\":\"backend\",\"analysis_summary\":\"...\",\"evidence_keys\":[\"...\"],\"confidence\":0.78}\n\n"
            )
        elif not severity_set:
            prompt += (
                "NEXT ACTION: Set severity (S0_critical, S1_major, S2_minor, S3_cosmetic).\n"
                "Example: {\"action_type\":\"SetSeverity\",\"severity\":\"S1_major\",\"analysis_summary\":\"...\",\"evidence_keys\":[\"...\"],\"confidence\":0.75}\n\n"
            )
        elif not next_action_proposed:
            prompt += (
                "NEXT ACTION: Propose next action (fix_immediately, schedule_next_sprint, etc.).\n"
                "Example: {\"action_type\":\"ProposeNextAction\",\"next_action\":\"fix_immediately\",\"analysis_summary\":\"...\",\"evidence_keys\":[\"...\"],\"confidence\":0.76}\n\n"
            )
        else:
            prompt += (
                "NEXT ACTION: All decisions complete. Submit or ask for clarification.\n"
                "Example: {\"action_type\":\"SubmitTriage\",\"summary\":\"Critical bug in auth, assigned to backend.\",\"analysis_summary\":\"...\",\"evidence_keys\":[\"...\"],\"confidence\":0.86}\n\n"
            )

        # Security check
        desc_lower = issue.get("description", "").lower()
        if any(kw in desc_lower for kw in ["password", "credential", "token", "secret", "api_key", "security"]):
            prompt += "SECURITY WARNING: Issue mentions sensitive data. Consider EscalateToHuman.\n\n"

        # Add full issue context
        prompt += (
            "FULL ISSUE CONTEXT:\n"
            f"{json.dumps(issue, indent=2)}\n\n"
            "VALID ENUMS:\n"
            f"- issue_type: {', '.join(sorted(VALID_ISSUE_TYPES))}\n"
            f"- component: {', '.join(sorted(VALID_COMPONENTS))}\n"
            f"- severity: {', '.join(sorted(VALID_SEVERITIES))}\n"
            f"- next_action: {', '.join(sorted(VALID_NEXT_ACTIONS))}\n"
            f"- question_type: {', '.join(sorted(VALID_QUESTION_TYPES))}\n\n"
            "RESPOND WITH VALID JSON ONLY. DO NOT INCLUDE MARKDOWN OR PROSE.\n"
            'Example format: {"action_type":"SetClassification","issue_type":"bug"}'
        )

        return prompt

    def _normalize_action(
        self, action: Dict[str, Any], observation: Dict[str, Any], current_decisions: Dict[str, str]
    ) -> Dict[str, Any]:
        """Map model output to environment action contract and guard invalid outputs.
        
        Also enforces decision sequence: classification → component → severity → next_action → submit.
        If model tries to skip steps, it forces the correct next step.
        """
        action_type = action.get("action_type")
        if action_type not in ALLOWED_ACTIONS:
            return {
                "action_type": "AskClarification",
                "question_type": "other",
                "question_text": "Could you provide additional details?",
            }

        # Get current decision state from tracked decisions
        has_classification = bool(current_decisions.get("issue_type"))
        has_component = bool(current_decisions.get("component"))
        has_severity = bool(current_decisions.get("severity"))
        has_next_action = bool(current_decisions.get("next_action"))

        # Enforce decision sequence: if a previous step is missing, force the model back
        signals = observation.get("extracted_signals") or {}
        explicit_hints = signals.get("explicit_hints") or {}
        step = int(observation.get("step_count") or 0)
        max_steps = int(observation.get("max_steps") or MAX_STEPS)

        guessed_issue_type = "feature_request" if bool(signals.get("explicit_feature_request")) else "bug"
        guessed_component = _normalize_enum(
            signals.get("affected_surface"), VALID_COMPONENTS, "unknown"
        )
        guessed_severity = "S2_minor"
        if bool(signals.get("likely_security")):
            guessed_severity = "S0_critical"
        elif signals.get("outage_scope") == "widespread":
            guessed_severity = "S1_major"
        elif signals.get("outage_scope") == "segment":
            guessed_severity = "S1_major"

        guessed_next_action = "schedule_next_sprint"
        if bool(signals.get("likely_security")):
            guessed_next_action = "fix_immediately"
        elif guessed_severity in ("S0_critical", "S1_major"):
            guessed_next_action = "fix_immediately"
        elif bool(signals.get("likely_duplicate")):
            guessed_next_action = "close_as_duplicate"

        hinted_component = _normalize_enum(
            explicit_hints.get("component_hint"), VALID_COMPONENTS, guessed_component
        )
        hinted_severity = _normalize_enum(
            explicit_hints.get("severity_hint"), VALID_SEVERITIES, guessed_severity
        )
        hinted_next_action = _normalize_enum(
            explicit_hints.get("next_action_hint"), VALID_NEXT_ACTIONS, guessed_next_action
        )

        # If all labels are ready, avoid wasting steps and submit deterministically.
        if has_classification and has_component and has_severity and has_next_action:
            if action_type not in ("SubmitTriage", "EscalateToHuman") and step >= 4:
                return {
                    "action_type": "SubmitTriage",
                    "summary": "Submitting triage decision from completed label set.",
                }

        # Late-stage guard: force terminal action to reduce loop penalties.
        if step >= max_steps - 1:
            if bool(signals.get("likely_security")):
                return {
                    "action_type": "EscalateToHuman",
                    "reason": "Security-sensitive issue near step budget limit.",
                }
            if has_classification and has_component and has_severity and has_next_action:
                return {
                    "action_type": "SubmitTriage",
                    "summary": "Finalizing triage before step budget limit.",
                }

        if action_type in ("SetSeverity", "AssignComponent", "ProposeNextAction", "SubmitTriage"):
            if not has_classification:
                # Force classification first
                return {
                    "action_type": "SetClassification",
                    "issue_type": guessed_issue_type,
                }
            if action_type in ("SetSeverity", "ProposeNextAction", "SubmitTriage"):
                if not has_component:
                    # Force component assignment
                    return {
                        "action_type": "AssignComponent",
                        "component": hinted_component,
                    }
            if action_type in ("ProposeNextAction", "SubmitTriage"):
                if not has_severity:
                    # Force severity setting
                    return {
                        "action_type": "SetSeverity",
                        "severity": hinted_severity,
                    }

        normalized: Dict[str, Any] = {"action_type": action_type}
        normalized["analysis_summary"] = _coerce_string(
            action.get("analysis_summary"), "Decision based on deterministic evidence."
        )
        evidence = action.get("evidence_keys")
        if isinstance(evidence, list):
            normalized["evidence_keys"] = [str(item) for item in evidence[:6]]
        else:
            normalized["evidence_keys"] = []
        conf = action.get("confidence")
        normalized["confidence"] = float(conf) if isinstance(conf, (int, float)) else 0.75

        if action_type == "AskClarification":
            normalized["question_type"] = _normalize_enum(
                action.get("question_type"), VALID_QUESTION_TYPES, "other"
            )
            normalized["question_text"] = _coerce_string(
                action.get("question_text"), "Could you provide additional details?"
            )
        elif action_type == "SetClassification":
            normalized["issue_type"] = _normalize_enum(
                action.get("issue_type"), VALID_ISSUE_TYPES, "bug"
            )
        elif action_type == "SetSeverity":
            normalized["severity"] = _normalize_enum(
                action.get("severity"), VALID_SEVERITIES, "S2_minor"
            )
        elif action_type == "AssignComponent":
            normalized["component"] = _normalize_enum(
                action.get("component"), VALID_COMPONENTS, "unknown"
            )
        elif action_type == "ProposeNextAction":
            normalized["next_action"] = _normalize_enum(
                action.get("next_action"), VALID_NEXT_ACTIONS, hinted_next_action
            )
        elif action_type == "SubmitTriage":
            normalized["summary"] = _coerce_string(
                action.get("summary"), "Submitting triage decision."
            )
            fd = action.get("final_decision")
            if isinstance(fd, dict):
                normalized["final_decision"] = {
                    "issue_type": _normalize_enum(fd.get("issue_type"), VALID_ISSUE_TYPES, "bug"),
                    "severity": _normalize_enum(fd.get("severity"), VALID_SEVERITIES, "S2_minor"),
                    "component": _normalize_enum(fd.get("component"), VALID_COMPONENTS, "unknown"),
                    "next_action": _normalize_enum(
                        fd.get("next_action"), VALID_NEXT_ACTIONS, "needs_investigation"
                    ),
                }
        elif action_type == "EscalateToHuman":
            normalized["reason"] = _coerce_string(
                action.get("reason"), "Potential security-sensitive issue"
            )

        available = observation.get("available_actions") or ALLOWED_ACTIONS
        if normalized["action_type"] not in available:
            return {
                "action_type": "AskClarification",
                "question_type": "other",
                "question_text": "Could you provide additional details?",
            }
        return normalized


def ensure_server_reachable(client: HttpJsonClient) -> None:
    try:
        client.get("/health")
    except Exception as exc:
        raise RuntimeError(
            f"Environment server is not reachable at {client.base_url}. "
            "Start it first, for example: uvicorn bugtriage_env.server.app:app --host 0.0.0.0 --port 8000"
        ) from exc


def update_decisions_from_action(decisions: Dict[str, str], action: Dict[str, Any]) -> None:
    at = action.get("action_type")
    if at == "SetClassification":
        decisions["issue_type"] = action.get("issue_type", "")
    elif at == "SetSeverity":
        decisions["severity"] = action.get("severity", "")
    elif at == "AssignComponent":
        decisions["component"] = action.get("component", "")
    elif at == "ProposeNextAction":
        decisions["next_action"] = action.get("next_action", "")
    elif at == "SubmitTriage":
        fd = action.get("final_decision")
        if isinstance(fd, dict):
            decisions.setdefault("issue_type", fd.get("issue_type", ""))
            decisions.setdefault("severity", fd.get("severity", ""))
            decisions.setdefault("component", fd.get("component", ""))
            decisions.setdefault("next_action", fd.get("next_action", ""))


def run_single_episode(
    base_url: str,
    llm: OpenAILLM,
    task_set: str,
    episode_index: int,
) -> EpisodeResult:
    with BugtriageEnv(base_url=base_url).sync() as env:
        reset_result = env.reset(task_set=task_set)
        observation_obj = reset_result.observation
        observation = observation_obj.model_dump(exclude_none=True)

        log_start(task=task_set, env="bugtriage", model=DEFAULT_MODEL_NAME)

        steps = 0
        reward_sum = 0.0
        done = bool(reset_result.done)
        decisions: Dict[str, str] = {}
        escalated = False
        rewards: List[float] = []
        success = False

        try:
            while not done and steps < MAX_STEPS:
                steps += 1
                try:
                    action = llm.choose_action(
                        task_set=task_set,
                        observation=observation,
                        current_decisions=decisions,
                    )
                    update_decisions_from_action(decisions, action)
                    if action.get("action_type") == "EscalateToHuman":
                        escalated = True

                    step_result = env.step(BugtriageAction(**action))
                    reward = float(step_result.reward or 0.0)
                    reward_sum += reward
                    rewards.append(reward)
                    done = bool(step_result.done)
                    observation_obj = step_result.observation
                    observation = observation_obj.model_dump(exclude_none=True)

                    log_step(
                        step=steps,
                        action=json.dumps(action, separators=(",", ":"), ensure_ascii=True),
                        reward=reward,
                        done=done,
                        error=observation.get("metadata", {}).get("last_action_error"),
                    )

                    # Ensure /state contract is exercised through the typed client.
                    _ = env.state()
                except Exception as exc:
                    # Do not crash the entire run on one bad network/parse/model step.
                    log_step(
                        step=steps,
                        action='{"action_type":"EscalateToHuman"}',
                        reward=0.0,
                        done=True,
                        error=f"runtime_error:{exc}",
                    )
                    break

            final_score = float(observation.get("final_score") or 0.0)
            if final_score == 0.0:
                final_metadata = observation.get("metadata", {})
                final_score = float(final_metadata.get("final_score", 0.0))
            success = bool(done and final_score > 0.0)
            return EpisodeResult(
                task_set=task_set,
                episode_index=episode_index,
                score=final_score,
                reward_sum=reward_sum,
                steps=steps,
                escalated=escalated,
                issue_id=observation.get("issue_id", ""),
            )
        finally:
            log_end(success=success, steps=steps, score=float(observation.get("final_score") or 0.0), rewards=rewards)


def summarize(results: List[EpisodeResult]) -> None:
    # Strict episode logging already emitted in run_single_episode().
    return


def main() -> int:
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN is required.", file=sys.stderr)
        return 2

    try:
        resolved_api_base_url, api_base_warning = _resolve_openai_base_url(DEFAULT_API_BASE_URL)
        if api_base_warning:
            print(f"WARN: {api_base_warning}", file=sys.stderr)

        # Startup diagnostics for routing and model selection.
        print(
            f"[CONFIG] api_base_url={resolved_api_base_url} model={DEFAULT_MODEL_NAME}",
            flush=True,
        )

        client = HttpJsonClient(DEFAULT_BASE_URL)
        ensure_server_reachable(client)
        llm = OpenAILLM(
            api_base_url=resolved_api_base_url,
            model_name=DEFAULT_MODEL_NAME,
            token=HF_TOKEN,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    all_results: List[EpisodeResult] = []
    try:
        for task_set in ("easy", "medium", "hard"):
            for idx in range(1, EPISODES_PER_SET + 1):
                result = run_single_episode(DEFAULT_BASE_URL, llm, task_set=task_set, episode_index=idx)
                all_results.append(result)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    summarize(all_results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

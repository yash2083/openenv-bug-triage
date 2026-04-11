#!/usr/bin/env python3
"""
Validator for Bug/Issue Triage task scenarios.

Validates JSON schema compliance, enum values, and difficulty-level rules
for all task scenario files.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Valid enum values (from bugtriage_env/models.py)
VALID_ISSUE_TYPES = {"bug", "feature_request", "question"}
VALID_SEVERITIES = {"S0_critical", "S1_major", "S2_minor", "S3_cosmetic"}
VALID_COMPONENTS = {
    "backend", "frontend", "database", "auth", "payments",
    "notifications", "infrastructure", "mobile", "api", "unknown"
}
VALID_QUESTION_TYPES = {
    "missing_repro_steps", "missing_environment", "missing_logs",
    "missing_expected_behavior", "missing_frequency", "other"
}
VALID_NEXT_ACTIONS = {
    "fix_immediately", "schedule_next_sprint", "add_to_backlog",
    "needs_investigation", "close_as_duplicate", "close_as_wontfix"
}
VALID_REPORTER_TYPES = {"customer", "internal", "qa"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}

# Required fields for every scenario
REQUIRED_FIELDS = [
    "issue_id",
    "title",
    "description",
    "reporter_type",
    "environment",
    "logs_excerpt",
    "true_type",
    "true_component",
    "true_severity",
    "required_clarifications",
    "gold_next_action",
    "security_flag",
    "difficulty",
]

# Environment sub-fields
ENVIRONMENT_FIELDS = ["os", "browser", "app_version", "device"]


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def load_json_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load and parse a JSON file."""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValidationError(f"{file_path.name}: Expected JSON array, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as e:
        raise ValidationError(f"{file_path.name}: Invalid JSON - {e}")
    except FileNotFoundError:
        raise ValidationError(f"{file_path.name}: File not found")


def validate_scenario(scenario: Dict[str, Any], file_name: str, index: int) -> None:
    """Validate a single scenario against schema and rules."""
    scenario_id = scenario.get("issue_id", f"scenario #{index + 1}")

    # Check all required fields present
    missing_fields = [f for f in REQUIRED_FIELDS if f not in scenario]
    if missing_fields:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Missing required fields: {', '.join(missing_fields)}"
        )

    # Validate environment sub-object
    if scenario["environment"] is not None:
        if not isinstance(scenario["environment"], dict):
            raise ValidationError(
                f"{file_name} - {scenario_id}: 'environment' must be an object or null"
            )
        for field in ENVIRONMENT_FIELDS:
            if field not in scenario["environment"]:
                raise ValidationError(
                    f"{file_name} - {scenario_id}: Missing environment field: {field}"
                )

    # Validate enum values
    if scenario["true_type"] not in VALID_ISSUE_TYPES:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Invalid true_type '{scenario['true_type']}'. "
            f"Must be one of: {', '.join(VALID_ISSUE_TYPES)}"
        )

    if scenario["true_component"] not in VALID_COMPONENTS:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Invalid true_component '{scenario['true_component']}'. "
            f"Must be one of: {', '.join(VALID_COMPONENTS)}"
        )

    if scenario["true_severity"] not in VALID_SEVERITIES:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Invalid true_severity '{scenario['true_severity']}'. "
            f"Must be one of: {', '.join(VALID_SEVERITIES)}"
        )

    if scenario["gold_next_action"] not in VALID_NEXT_ACTIONS:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Invalid gold_next_action '{scenario['gold_next_action']}'. "
            f"Must be one of: {', '.join(VALID_NEXT_ACTIONS)}"
        )

    if scenario["reporter_type"] not in VALID_REPORTER_TYPES:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Invalid reporter_type '{scenario['reporter_type']}'. "
            f"Must be one of: {', '.join(VALID_REPORTER_TYPES)}"
        )

    if scenario["difficulty"] not in VALID_DIFFICULTIES:
        raise ValidationError(
            f"{file_name} - {scenario_id}: Invalid difficulty '{scenario['difficulty']}'. "
            f"Must be one of: {', '.join(VALID_DIFFICULTIES)}"
        )

    # Validate required_clarifications
    if not isinstance(scenario["required_clarifications"], list):
        raise ValidationError(
            f"{file_name} - {scenario_id}: 'required_clarifications' must be an array"
        )

    for clarification in scenario["required_clarifications"]:
        if clarification not in VALID_QUESTION_TYPES:
            raise ValidationError(
                f"{file_name} - {scenario_id}: Invalid clarification type '{clarification}'. "
                f"Must be one of: {', '.join(VALID_QUESTION_TYPES)}"
            )

    # Validate security_flag is boolean
    if not isinstance(scenario["security_flag"], bool):
        raise ValidationError(
            f"{file_name} - {scenario_id}: 'security_flag' must be a boolean"
        )


def validate_difficulty_rules(
    easy_scenarios: List[Dict[str, Any]],
    medium_scenarios: List[Dict[str, Any]],
    hard_scenarios: List[Dict[str, Any]],
) -> None:
    """Validate difficulty-specific rules."""

    # Easy scenarios rules
    for i, scenario in enumerate(easy_scenarios):
        scenario_id = scenario.get("issue_id", f"easy scenario #{i + 1}")

        if scenario["difficulty"] != "easy":
            raise ValidationError(
                f"issues_easy.json - {scenario_id}: difficulty must be 'easy', got '{scenario['difficulty']}'"
            )

        if scenario["required_clarifications"] != []:
            raise ValidationError(
                f"issues_easy.json - {scenario_id}: Easy scenarios must have empty required_clarifications"
            )

        if scenario["security_flag"]:
            raise ValidationError(
                f"issues_easy.json - {scenario_id}: Easy scenarios must have security_flag=false"
            )

    # Medium scenarios rules
    for i, scenario in enumerate(medium_scenarios):
        scenario_id = scenario.get("issue_id", f"medium scenario #{i + 1}")

        if scenario["difficulty"] != "medium":
            raise ValidationError(
                f"issues_medium.json - {scenario_id}: difficulty must be 'medium', got '{scenario['difficulty']}'"
            )

        if len(scenario["required_clarifications"]) != 1:
            raise ValidationError(
                f"issues_medium.json - {scenario_id}: Medium scenarios must have exactly 1 required_clarification, "
                f"got {len(scenario['required_clarifications'])}"
            )

        if scenario["security_flag"]:
            raise ValidationError(
                f"issues_medium.json - {scenario_id}: Medium scenarios must have security_flag=false"
            )

    # Hard scenarios rules
    security_flagged_count = sum(1 for s in hard_scenarios if s["security_flag"])

    if security_flagged_count < 1:
        raise ValidationError(
            "issues_hard.json: Must have at least 1 security-flagged scenario"
        )

    for i, scenario in enumerate(hard_scenarios):
        scenario_id = scenario.get("issue_id", f"hard scenario #{i + 1}")

        if scenario["difficulty"] != "hard":
            raise ValidationError(
                f"issues_hard.json - {scenario_id}: difficulty must be 'hard', got '{scenario['difficulty']}'"
            )

        # Security-flagged scenarios should use S0_critical
        if scenario["security_flag"] and scenario["true_severity"] != "S0_critical":
            raise ValidationError(
                f"issues_hard.json - {scenario_id}: Security-flagged scenarios should use S0_critical severity"
            )


def print_coverage_summary(
    easy_scenarios: List[Dict[str, Any]],
    medium_scenarios: List[Dict[str, Any]],
    hard_scenarios: List[Dict[str, Any]],
) -> None:
    """Print coverage statistics."""
    all_scenarios = easy_scenarios + medium_scenarios + hard_scenarios

    print("\n" + "=" * 60)
    print("COVERAGE SUMMARY")
    print("=" * 60)

    print(f"\nTotal scenarios: {len(all_scenarios)}")
    print(f"  Easy: {len(easy_scenarios)}")
    print(f"  Medium: {len(medium_scenarios)}")
    print(f"  Hard: {len(hard_scenarios)}")

    # Component coverage
    components = {}
    for scenario in all_scenarios:
        comp = scenario["true_component"]
        components[comp] = components.get(comp, 0) + 1

    print(f"\nComponent coverage ({len(components)} unique):")
    for comp in sorted(components.keys()):
        print(f"  {comp}: {components[comp]}")

    # Severity coverage
    severities = {}
    for scenario in all_scenarios:
        sev = scenario["true_severity"]
        severities[sev] = severities.get(sev, 0) + 1

    print("\nSeverity coverage:")
    for sev in ["S0_critical", "S1_major", "S2_minor", "S3_cosmetic"]:
        count = severities.get(sev, 0)
        print(f"  {sev}: {count}")

    # Reporter type coverage
    reporters = {}
    for scenario in all_scenarios:
        rep = scenario["reporter_type"]
        reporters[rep] = reporters.get(rep, 0) + 1

    print("\nReporter type coverage:")
    for rep in sorted(reporters.keys()):
        print(f"  {rep}: {reporters[rep]}")

    # Issue type coverage
    types = {}
    for scenario in all_scenarios:
        typ = scenario["true_type"]
        types[typ] = types.get(typ, 0) + 1

    print("\nIssue type coverage:")
    for typ in sorted(types.keys()):
        print(f"  {typ}: {types[typ]}")

    # Security flag coverage
    security_count = sum(1 for s in all_scenarios if s["security_flag"])
    print(f"\nSecurity-flagged scenarios: {security_count}")

    # Clarification coverage
    clarifications = {}
    for scenario in all_scenarios:
        for clarif in scenario["required_clarifications"]:
            clarifications[clarif] = clarifications.get(clarif, 0) + 1

    if clarifications:
        print("\nClarification types used:")
        for clarif in sorted(clarifications.keys()):
            print(f"  {clarif}: {clarifications[clarif]}")

    print("\n" + "=" * 60)


def main() -> int:
    """Main validation function."""
    repo_root = Path(__file__).parent.parent
    tasks_dir = repo_root / "tasks"

    print("Validating Bug/Issue Triage task scenarios...")
    print(f"Tasks directory: {tasks_dir}")

    try:
        # Load all scenario files
        easy_file = tasks_dir / "issues_easy.json"
        medium_file = tasks_dir / "issues_medium.json"
        hard_file = tasks_dir / "issues_hard.json"

        print(f"\nLoading {easy_file.name}...")
        easy_scenarios = load_json_file(easy_file)
        print(f"  ✓ Loaded {len(easy_scenarios)} scenarios")

        print(f"\nLoading {medium_file.name}...")
        medium_scenarios = load_json_file(medium_file)
        print(f"  ✓ Loaded {len(medium_scenarios)} scenarios")

        print(f"\nLoading {hard_file.name}...")
        hard_scenarios = load_json_file(hard_file)
        print(f"  ✓ Loaded {len(hard_scenarios)} scenarios")

        # Validate each scenario
        print("\nValidating easy scenarios...")
        for i, scenario in enumerate(easy_scenarios):
            validate_scenario(scenario, "issues_easy.json", i)
        print(f"  ✓ All {len(easy_scenarios)} easy scenarios valid")

        print("\nValidating medium scenarios...")
        for i, scenario in enumerate(medium_scenarios):
            validate_scenario(scenario, "issues_medium.json", i)
        print(f"  ✓ All {len(medium_scenarios)} medium scenarios valid")

        print("\nValidating hard scenarios...")
        for i, scenario in enumerate(hard_scenarios):
            validate_scenario(scenario, "issues_hard.json", i)
        print(f"  ✓ All {len(hard_scenarios)} hard scenarios valid")

        # Validate difficulty-specific rules
        print("\nValidating difficulty-level rules...")
        validate_difficulty_rules(easy_scenarios, medium_scenarios, hard_scenarios)
        print("  ✓ All difficulty rules satisfied")

        # Print coverage summary
        print_coverage_summary(easy_scenarios, medium_scenarios, hard_scenarios)

        print("\n✅ All validations passed!")
        return 0

    except ValidationError as e:
        print(f"\n❌ Validation failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

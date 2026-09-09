"""Structural/semantic validation for evaluation-suite YAML (Phase 12a).

Suites are authored in YAML, same "author in YAML, persist the parsed
config" convention agent definitions already use (see validation.py) --
but this is a much smaller, purpose-built format, so it gets a hand-rolled
validator here rather than a full JSON-schema package like
agentforge-agent-schema.
"""

import yaml

_VALID_GRADING_KINDS = {"exact_match", "judge", "unit_test"}


class EvalSuiteParseError(Exception):
    """Carries every problem found, not just the first -- same "collect all
    errors" UX agent-YAML validation gives via ValidationResult.errors.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def parse_and_validate_suite(yaml_source: str) -> dict:
    """Parses `yaml_source` and validates it against the eval-suite shape:

        tasks:
          - id: string, unique within the suite
            input: {..free-form dict, passed straight through as an
                     Execution's input..}
            grading:
              kind: exact_match | judge | unit_test
              expected: string       # exact_match only
              rubric: string         # judge only
              ground_truth: string   # judge only, optional (enables the
                                      # RAG-specific context_precision/
                                      # context_recall metrics -- see
                                      # execution-platform's grading.py)
              threshold: float       # judge only, optional, default 0.7
              script: string         # unit_test only
        judge:                       # optional suite-level override
          provider: string
          model_id: string

    Returns the parsed config dict on success. Raises EvalSuiteParseError
    (never returns a partially-valid result) otherwise.
    """
    try:
        parsed = yaml.safe_load(yaml_source)
    except yaml.YAMLError as exc:
        raise EvalSuiteParseError([f"invalid YAML: {exc}"]) from exc

    if not isinstance(parsed, dict):
        raise EvalSuiteParseError(["suite must be a YAML mapping at the top level"])

    errors: list[str] = []

    tasks = parsed.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("'tasks' must be a non-empty list")
        tasks = []

    seen_ids: set[str] = set()
    for i, task in enumerate(tasks):
        prefix = f"tasks[{i}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} must be a mapping")
            continue

        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{prefix}.id is required and must be a non-empty string")
        elif task_id in seen_ids:
            errors.append(f"{prefix}.id {task_id!r} is not unique within this suite")
        else:
            seen_ids.add(task_id)

        if not isinstance(task.get("input"), dict):
            errors.append(f"{prefix}.input is required and must be a mapping")

        grading = task.get("grading")
        if not isinstance(grading, dict):
            errors.append(f"{prefix}.grading is required and must be a mapping")
            continue

        kind = grading.get("kind")
        if kind not in _VALID_GRADING_KINDS:
            errors.append(f"{prefix}.grading.kind must be one of {sorted(_VALID_GRADING_KINDS)}, got {kind!r}")
            continue

        if kind == "exact_match" and not isinstance(grading.get("expected"), str):
            errors.append(f"{prefix}.grading.expected is required (string) for kind 'exact_match'")
        if kind == "judge" and not isinstance(grading.get("rubric"), str):
            errors.append(f"{prefix}.grading.rubric is required (string) for kind 'judge'")
        if kind == "unit_test" and not isinstance(grading.get("script"), str):
            errors.append(f"{prefix}.grading.script is required (string) for kind 'unit_test'")

    judge_cfg = parsed.get("judge")
    if judge_cfg is not None and not isinstance(judge_cfg, dict):
        errors.append("'judge' must be a mapping if present")

    if errors:
        raise EvalSuiteParseError(errors)

    return parsed

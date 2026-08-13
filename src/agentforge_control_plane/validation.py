import uuid

import yaml
from agentforge_agent_schema import load_schema
from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.models import Tool

_SCHEMA = load_schema()
_VALIDATOR = Draft202012Validator(_SCHEMA)


class ParsedValidationResult:
    def __init__(
        self,
        valid: bool,
        schema_version: str | None,
        errors: list[dict],
        parsed: dict | None,
    ) -> None:
        self.valid = valid
        self.schema_version = schema_version
        self.errors = errors
        self.parsed = parsed


def validate_yaml_source(yaml_source: str, tenant_id: uuid.UUID, db: Session) -> ParsedValidationResult:
    """Two-layer validation of an agent YAML definition.

    Layer 1: structural validation against the agent.schema.json JSON
    Schema (draft 2020-12).
    Layer 2: semantic validation -- every tools[].tool_id referenced must
    exist in the `tools` table for the caller's tenant. An empty tools list
    trivially passes with no query.
    """
    errors: list[dict] = []

    try:
        parsed = yaml.safe_load(yaml_source)
    except yaml.YAMLError as exc:
        return ParsedValidationResult(
            valid=False,
            schema_version=None,
            errors=[{"code": "invalid_yaml", "message": f"YAML parse error: {exc}", "field": None}],
            parsed=None,
        )

    if not isinstance(parsed, dict):
        return ParsedValidationResult(
            valid=False,
            schema_version=None,
            errors=[{"code": "invalid_yaml", "message": "Top-level YAML document must be a mapping.", "field": None}],
            parsed=None,
        )

    schema_version = parsed.get("schema_version")

    # Layer 1: structural
    for err in sorted(_VALIDATOR.iter_errors(parsed), key=lambda e: list(e.path)):
        field = ".".join(str(p) for p in err.path) or None
        errors.append({"code": "schema_violation", "message": err.message, "field": field})

    # Layer 2: semantic (tool_id existence), only meaningful if structurally
    # sane enough to have a tools list.
    # Agent YAML references tools by their human-readable `tool_id` (e.g.
    # "github", "kubernetes"), which maps to the `tools.name` column in the
    # registry -- there is no separate slug column on `tools`.
    tools_section = parsed.get("tools")
    if isinstance(tools_section, list) and tools_section:
        tool_ids = {t.get("tool_id") for t in tools_section if isinstance(t, dict) and t.get("tool_id")}
        if tool_ids:
            existing = set(
                db.execute(
                    select(Tool.name).where(Tool.tenant_id == tenant_id, Tool.name.in_(tool_ids))
                ).scalars()
            )
            missing = tool_ids - existing
            for tool_id in sorted(missing):
                errors.append(
                    {
                        "code": "unknown_tool_id",
                        "message": f"tool_id '{tool_id}' is not registered for this tenant.",
                        "field": "tools",
                    }
                )

    return ParsedValidationResult(
        valid=len(errors) == 0,
        schema_version=schema_version,
        errors=errors,
        parsed=parsed,
    )

import uuid

import yaml
from agentforge_agent_schema import load_schema
from jsonschema import Draft202012Validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.models import Agent, AgentVersion, KnowledgeBase, Policy, Tool

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
    exist in the `tools` table for the caller's tenant, every
    permissions.policy_refs[] name referenced must exist in the `policies`
    table for the caller's tenant, every knowledge[].knowledge_base_id
    referenced must exist in the `knowledge_bases` table for the caller's
    tenant, and every sub_agents[].agent_id referenced must exist as an
    `agents.slug` for the caller's tenant (and, if it does, must not itself
    declare a non-empty approval.checkpoints or sub_agents section -- Phase 9
    caps delegation depth at 1 and a sub-agent's approval checkpoints can
    never fire since it runs synchronously in-process). An empty/absent
    section trivially passes with no query.
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

    # Layer 2: semantic (policy_ref existence), only meaningful if
    # structurally sane enough to have a permissions.policy_refs list.
    # Agent YAML references policies by their human-readable name, which
    # maps to the `policies.name` column in the registry.
    permissions_section = parsed.get("permissions")
    if isinstance(permissions_section, dict):
        policy_refs = permissions_section.get("policy_refs")
        if isinstance(policy_refs, list) and policy_refs:
            ref_names = {p for p in policy_refs if isinstance(p, str)}
            if ref_names:
                existing_policies = set(
                    db.execute(
                        select(Policy.name).where(Policy.tenant_id == tenant_id, Policy.name.in_(ref_names))
                    ).scalars()
                )
                missing_policies = ref_names - existing_policies
                for policy_ref in sorted(missing_policies):
                    errors.append(
                        {
                            "code": "unknown_policy_ref",
                            "message": f"policy_ref '{policy_ref}' is not registered for this tenant.",
                            "field": "permissions.policy_refs",
                        }
                    )

    # Layer 2: semantic (knowledge_base_id existence), only meaningful if
    # structurally sane enough to have a knowledge list.
    # Agent YAML references knowledge bases by their human-readable name,
    # which maps to the `knowledge_bases.name` column in the registry.
    knowledge_section = parsed.get("knowledge")
    if isinstance(knowledge_section, list) and knowledge_section:
        kb_names = {
            k.get("knowledge_base_id") for k in knowledge_section if isinstance(k, dict) and k.get("knowledge_base_id")
        }
        if kb_names:
            existing_kbs = set(
                db.execute(
                    select(KnowledgeBase.name).where(
                        KnowledgeBase.tenant_id == tenant_id, KnowledgeBase.name.in_(kb_names)
                    )
                ).scalars()
            )
            missing_kbs = kb_names - existing_kbs
            for kb_name in sorted(missing_kbs):
                errors.append(
                    {
                        "code": "unknown_knowledge_base_id",
                        "message": f"knowledge_base_id '{kb_name}' is not registered for this tenant.",
                        "field": "knowledge",
                    }
                )

    # Layer 2: semantic (sub_agents[].agent_id existence + delegation-depth
    # cap), only meaningful if structurally sane enough to have a sub_agents
    # list.
    # Agent YAML references sub-agents by their human-readable `agent_id`,
    # which -- unlike tool_id/policy_ref/knowledge_base_id, which all map to
    # registry tables -- maps to the `agents.slug` column, i.e. this is the
    # first semantic check that resolves against the agents table itself.
    # Phase 9 caps delegation depth at 1: a sub-agent runs synchronously
    # in-process (never through its own Temporal workflow), so a sub-agent's
    # approval.checkpoints could never actually fire, and a sub-agent cannot
    # itself declare further sub_agents. Both are rejected here at
    # validation time rather than left to misbehave silently at runtime.
    sub_agents_section = parsed.get("sub_agents")
    if isinstance(sub_agents_section, list) and sub_agents_section:
        sub_agent_ids = {
            s.get("agent_id") for s in sub_agents_section if isinstance(s, dict) and s.get("agent_id")
        }
        if sub_agent_ids:
            existing_agents = list(
                db.execute(
                    select(Agent.slug, Agent.latest_version_id).where(
                        Agent.tenant_id == tenant_id, Agent.slug.in_(sub_agent_ids)
                    )
                ).all()
            )
            existing_slugs = {slug for slug, _ in existing_agents}
            missing_slugs = sub_agent_ids - existing_slugs
            for slug in sorted(missing_slugs):
                errors.append(
                    {
                        "code": "unknown_sub_agent",
                        "message": f"sub_agents[].agent_id '{slug}' is not registered for this tenant.",
                        "field": "sub_agents",
                    }
                )

            # Only bother checking nested approval/sub_agents constraints for
            # slugs that actually resolved.
            version_ids = [vid for _, vid in existing_agents if vid is not None]
            if version_ids:
                versions_by_id = {
                    v.id: v
                    for v in db.execute(
                        select(AgentVersion).where(AgentVersion.id.in_(version_ids))
                    ).scalars()
                }
                for slug, version_id in existing_agents:
                    if version_id is None:
                        continue
                    version = versions_by_id.get(version_id)
                    if version is None:
                        continue
                    try:
                        sub_parsed = yaml.safe_load(version.yaml_source)
                    except yaml.YAMLError:
                        continue
                    if not isinstance(sub_parsed, dict):
                        continue

                    sub_approval = sub_parsed.get("approval")
                    sub_checkpoints = (
                        sub_approval.get("checkpoints") if isinstance(sub_approval, dict) else None
                    )
                    if isinstance(sub_checkpoints, list) and sub_checkpoints:
                        errors.append(
                            {
                                "code": "unknown_sub_agent",
                                "message": (
                                    f"sub_agents[].agent_id '{slug}' is not a valid delegation target: "
                                    "it declares a non-empty approval.checkpoints section. Nested "
                                    "approval pauses are out of scope for Phase 9 (a sub-agent runs "
                                    "synchronously in-process and its approval checkpoints can never "
                                    "fire)."
                                ),
                                "field": "sub_agents",
                            }
                        )

                    nested_sub_agents = sub_parsed.get("sub_agents")
                    if isinstance(nested_sub_agents, list) and nested_sub_agents:
                        errors.append(
                            {
                                "code": "unknown_sub_agent",
                                "message": (
                                    f"sub_agents[].agent_id '{slug}' is not a valid delegation target: "
                                    "it declares a non-empty sub_agents section. Delegation depth is "
                                    "capped at 1 for Phase 9 (nested sub-sub-agent delegation is "
                                    "out of scope)."
                                ),
                                "field": "sub_agents",
                            }
                        )

    return ParsedValidationResult(
        valid=len(errors) == 0,
        schema_version=schema_version,
        errors=errors,
        parsed=parsed,
    )

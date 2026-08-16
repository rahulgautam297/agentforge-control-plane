"""seed_phase2_tools_and_policies

Idempotent data-only migration for Phase 2 (Tools/MCP). Seeds the two mock
tools (`github`, `kubernetes`) and the two example policies
(`production-read-only`, `production-rollback-requires-approval`) referenced
by the showcase agent's YAML (see agentforge-docs doc 07-agent-yaml-schema.md
and ADR-0008), under the deterministic Phase-1 dev tenant.

`policies` has no unique constraint on (tenant_id, name) (unlike `tools`,
which has uq_tools_tenant_name), so idempotency here is achieved the same
way as 0002_execution_plane_role -- check-then-insert via
conn.exec_driver_sql -- rather than INSERT ... ON CONFLICT, which requires a
matching unique/exclusion constraint to target.

Revision ID: 0003_seed_tools_and_policies
Revises: 0002_execution_plane_role
Create Date: 2026-08-14 00:00:00.000000

NOTE: revision id is intentionally shortened to "0003_seed_tools_and_policies"
(28 chars) rather than mirroring the migration's descriptive filename
exactly -- alembic_version.version_num is varchar(32) (set by alembic's own
init template) and a longer id like "0003_seed_phase2_tools_and_policies"
(35 chars) raises psycopg.errors.StringDataRightTruncation on upgrade.
Verified empirically against the live container.

"""
import json
import uuid
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_seed_tools_and_policies'
down_revision: Union[str, Sequence[str], None] = '0002_execution_plane_role'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

TOOLS = [
    {
        "name": "github",
        "description": (
            "Mock GitHub tool -- read PRs/files/issues; guarded write "
            "(comment/merge) actions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get_pr", "list_issues", "comment", "merge"]},
                "repo": {"type": "string"},
                "number": {"type": "integer"},
                "body": {"type": "string"},
            },
            "required": ["action", "repo"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "result": {"type": "object"},
            },
            "required": ["status"],
        },
    },
    {
        "name": "kubernetes",
        "description": (
            "Mock Kubernetes tool -- read pod/deployment status; guarded "
            "write (rollback/scale) actions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get_status", "list_pods", "rollback", "scale"]},
                "namespace": {"type": "string"},
                "deployment": {"type": "string"},
                "replicas": {"type": "integer"},
            },
            "required": ["action", "namespace"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "result": {"type": "object"},
            },
            "required": ["status"],
        },
    },
]

POLICIES = [
    {
        "name": "production-read-only",
        "rule": {"tool_id": "*", "action": "read", "effect": "allow"},
    },
    {
        "name": "production-rollback-requires-approval",
        "rule": {
            "tool_id": "kubernetes",
            "action": "write",
            "resource_pattern": "production/*",
            "effect": "human_approval",
        },
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for tool in TOOLS:
        exists = conn.exec_driver_sql(
            "SELECT 1 FROM tools WHERE tenant_id = %s AND name = %s",
            (DEFAULT_TENANT_ID, tool["name"]),
        ).scalar()
        if exists:
            continue
        conn.exec_driver_sql(
            """
            INSERT INTO tools (id, tenant_id, name, description, input_schema, output_schema)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                str(uuid.uuid4()),
                DEFAULT_TENANT_ID,
                tool["name"],
                tool["description"],
                json.dumps(tool["input_schema"]),
                json.dumps(tool["output_schema"]),
            ),
        )

    for policy in POLICIES:
        exists = conn.exec_driver_sql(
            "SELECT 1 FROM policies WHERE tenant_id = %s AND name = %s",
            (DEFAULT_TENANT_ID, policy["name"]),
        ).scalar()
        if exists:
            continue
        conn.exec_driver_sql(
            """
            INSERT INTO policies (id, tenant_id, name, rule)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()),
                DEFAULT_TENANT_ID,
                policy["name"],
                json.dumps(policy["rule"]),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()

    for tool in TOOLS:
        conn.exec_driver_sql(
            "DELETE FROM tools WHERE tenant_id = %s AND name = %s",
            (DEFAULT_TENANT_ID, tool["name"]),
        )

    for policy in POLICIES:
        conn.exec_driver_sql(
            "DELETE FROM policies WHERE tenant_id = %s AND name = %s",
            (DEFAULT_TENANT_ID, policy["name"]),
        )

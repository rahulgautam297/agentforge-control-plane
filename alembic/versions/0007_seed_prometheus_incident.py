"""seed_phase8_prometheus_and_incident_history

Idempotent data-only migration for Phase 8 (Flagship Demo). Seeds the
`prometheus` mock tool and the `incident-history` knowledge base, under the
deterministic Phase-1 dev tenant, both referenced by name in the Production
Incident Investigator's YAML in agentforge-docs doc
07-agent-yaml-schema.md's canonical example -- alongside the `github`/
`kubernetes` tools seeded in 0003_seed_tools_and_policies (Phase 2) and the
`engineering-docs` knowledge base seeded in 0004_seed_knowledge_base
(Phase 3).

Same idempotency pattern as 0003/0004: `tools` has a unique constraint on
(tenant_id, name) (uq_tools_tenant_name) but `knowledge_bases` does not, so
both use check-then-insert via conn.exec_driver_sql rather than
INSERT ... ON CONFLICT, for consistency across the seed migrations even
though INSERT ... ON CONFLICT would technically work for `tools` alone.

Revision ID: 0007_seed_prometheus_incident
Revises: 0006_execution_role_delete_grant
Create Date: 2026-08-15 00:00:00.000000

NOTE: revision id is 29 chars, under the varchar(32) limit on
alembic_version.version_num (see 0003's docstring for the empirical
StringDataRightTruncation finding that established this constraint).

"""
import json
import uuid
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007_seed_prometheus_incident'
down_revision: Union[str, Sequence[str], None] = '0006_execution_role_delete_grant'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

TOOLS = [
    {
        "name": "prometheus",
        "description": (
            "Mock Prometheus tool -- query deployment metrics (error rate, "
            "p99 latency) and detect anomalies."
        ),
        "input_schema": {
            "type": "object",
            "required": ["action", "resource"],
            "properties": {
                "action": {"type": "string", "enum": ["query"]},
                "resource": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "required": ["error_rate", "p99_latency_ms", "anomaly_detected"],
            "properties": {
                "error_rate": {"type": "number"},
                "p99_latency_ms": {"type": "integer"},
                "anomaly_detected": {"type": "boolean"},
            },
        },
    },
]

KNOWLEDGE_BASE = {
    "name": "incident-history",
    "source_type": "manual",
    "status": "active",
}


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

    exists = conn.exec_driver_sql(
        "SELECT 1 FROM knowledge_bases WHERE tenant_id = %s AND name = %s",
        (DEFAULT_TENANT_ID, KNOWLEDGE_BASE["name"]),
    ).scalar()
    if not exists:
        conn.exec_driver_sql(
            """
            INSERT INTO knowledge_bases (id, tenant_id, name, source_type, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                DEFAULT_TENANT_ID,
                KNOWLEDGE_BASE["name"],
                KNOWLEDGE_BASE["source_type"],
                KNOWLEDGE_BASE["status"],
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()

    for tool in TOOLS:
        conn.exec_driver_sql(
            "DELETE FROM tools WHERE tenant_id = %s AND name = %s",
            (DEFAULT_TENANT_ID, tool["name"]),
        )

    conn.exec_driver_sql(
        "DELETE FROM knowledge_bases WHERE tenant_id = %s AND name = %s",
        (DEFAULT_TENANT_ID, KNOWLEDGE_BASE["name"]),
    )

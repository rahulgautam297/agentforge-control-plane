"""seed_phase9_fraud_and_supervisor

Idempotent data-only migration for Phase 9 (Multi-agent Supervisor + Fraud
Investigation Agent). Seeds the two mock tools (`transactions`, `accounts`)
and the one new policy (`fraud-account-freeze-requires-approval`) needed by
the Fraud Investigation Agent, under the deterministic Phase-1 dev tenant.

The Fraud Investigation Agent deliberately reuses Phase 8's
`anomaly_detected` escalation mechanism as-is (no new graph code anywhere)
-- it proves that mechanism generalizes beyond the Incident Investigator, per
doc 12's Phase 9 exit criterion ("a second, independent
human-approval-gated real-world scenario").

Reads against `transactions`/`accounts` are already covered by the existing
wildcard `production-read-only` policy seeded in 0003_seed_tools_and_policies
(`rule: {tool_id: "*", action: "read", effect: allow}` -- despite its
production-sounding name, the `tool_id: "*"` match makes it generically
applicable to any tool's read calls, not just production ones -- confirmed
by re-reading that migration rather than reseeding it here). Only the
account-freeze write action needs a new policy, and unlike
production-rollback-requires-approval's path-scoped rule, this one needs no
resource_pattern: every account-freeze action requires human approval.

Same idempotency pattern as 0003/0004/0007: `tools` has a unique constraint
on (tenant_id, name) (uq_tools_tenant_name) but `policies` does not, so both
use check-then-insert via conn.exec_driver_sql rather than
INSERT ... ON CONFLICT, for consistency across the seed migrations even
though INSERT ... ON CONFLICT would technically work for `tools` alone.

Revision ID: 0008_seed_fraud_and_supervisor
Revises: 0007_seed_prometheus_incident
Create Date: 2026-08-15 00:00:00.000000

NOTE: revision id is 30 chars, under the varchar(32) limit on
alembic_version.version_num (see 0003's docstring for the empirical
StringDataRightTruncation finding that established this constraint).

"""
import json
import uuid
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0008_seed_fraud_and_supervisor'
down_revision: Union[str, Sequence[str], None] = '0007_seed_prometheus_incident'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

TOOLS = [
    {
        "name": "transactions",
        "description": (
            "Mock transactions tool -- query customer transaction history "
            "and detect anomalous patterns."
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
            "required": ["risk_score", "anomaly_detected"],
            "properties": {
                "risk_score": {"type": "number"},
                "anomaly_detected": {"type": "boolean"},
                "flagged_transactions": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "accounts",
        "description": (
            "Mock accounts tool -- freeze or unfreeze a customer account "
            "(guarded write action)."
        ),
        "input_schema": {
            "type": "object",
            "required": ["action", "resource"],
            "properties": {
                "action": {"type": "string", "enum": ["get_status", "freeze", "unfreeze"]},
                "resource": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "required": ["status"],
            "properties": {
                "status": {"type": "string"},
                "resource": {"type": "string"},
            },
        },
    },
]

POLICIES = [
    {
        "name": "fraud-account-freeze-requires-approval",
        "rule": {"tool_id": "accounts", "action": "write", "effect": "human_approval"},
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

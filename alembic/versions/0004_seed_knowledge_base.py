"""seed_phase3_knowledge_base

Idempotent data-only migration for Phase 3 (RAG). Seeds a single
`knowledge_bases` row (`engineering-docs`) under the deterministic Phase-1
dev tenant, matching the flagship demo's knowledge base name from
agentforge-docs doc 07-agent-yaml-schema.md's example.

Deliberately does NOT seed any `documents` rows -- that requires a live
cross-service call to the execution plane's ingest endpoint (per ADR-0007,
control-plane owns only document metadata; actual indexing happens on the
execution plane), which a migration can't safely make since the execution
plane may not be up yet at migration time.

Same idempotency pattern as 0003_seed_tools_and_policies: `knowledge_bases`
has no unique constraint on (tenant_id, name), so this uses check-then-insert
via conn.exec_driver_sql rather than INSERT ... ON CONFLICT.

Revision ID: 0004_seed_knowledge_base
Revises: 0003_seed_tools_and_policies
Create Date: 2026-08-14 00:00:00.000000

NOTE: revision id kept at 25 chars, well under the varchar(32) limit on
alembic_version.version_num that bit an earlier migration (see 0003's
docstring).

"""
import uuid
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004_seed_knowledge_base'
down_revision: Union[str, Sequence[str], None] = '0003_seed_tools_and_policies'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

KNOWLEDGE_BASE = {
    "name": "engineering-docs",
    "source_type": "manual",
    "status": "active",
}


def upgrade() -> None:
    conn = op.get_bind()

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

    conn.exec_driver_sql(
        "DELETE FROM knowledge_bases WHERE tenant_id = %s AND name = %s",
        (DEFAULT_TENANT_ID, KNOWLEDGE_BASE["name"]),
    )

"""memory_tables

Phase 4 (Memory). Creates the two new execution-plane-owned tables backing
an agent's optional YAML `memory: {episodic, semantic}` sections (see
agentforge-docs/docs/architecture/07-agent-yaml-schema.md). Working memory
(the third memory kind) is an in-graph scratchpad that is never persisted,
so it needs no table.

`memory_episodes` holds recall of past executions (one row per episode);
`memory_facts` holds durable per-agent key/value facts, unique per
(tenant_id, agent_id, key) so a fact upsert has a natural conflict target.

No ADR or schema previously existed for memory -- Phase 1 didn't anticipate
it -- so this is new schema design, not filling in something already
specified elsewhere. Both tables are plain relational tables, not Timescale
hypertables: low volume, no time-range query pattern that would justify
hypertable partitioning the way execution_steps has.

Same as 0002_execution_plane_role's docstring warned: any migration adding
a new execution-owned table must include its own explicit GRANT statement
for agentforge_execution. This migration does that for both new tables.

Revision ID: 0005_memory_tables
Revises: 0004_seed_knowledge_base
Create Date: 2026-08-14 00:00:00.000000

NOTE: revision id kept at 18 chars, well under the varchar(32) limit on
alembic_version.version_num that bit an earlier migration (see 0003's
docstring).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0005_memory_tables'
down_revision: Union[str, Sequence[str], None] = '0004_seed_knowledge_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_NAME = "agentforge_execution"


def upgrade() -> None:
    op.create_table(
        'memory_episodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=False),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'memory_facts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'agent_id', 'key', name='uq_memory_facts_tenant_agent_key'),
    )

    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE memory_episodes TO {ROLE_NAME};")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE memory_facts TO {ROLE_NAME};")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT, INSERT, UPDATE ON TABLE memory_episodes FROM {ROLE_NAME};")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE ON TABLE memory_facts FROM {ROLE_NAME};")

    op.drop_table('memory_facts')
    op.drop_table('memory_episodes')

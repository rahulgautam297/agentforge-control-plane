"""initial_schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-13 19:50:54.626850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic Phase-1 auth-shim identities (see
# agentforge_control_plane.config.Settings.default_tenant_id /
# default_user_id). Seeded below so both services can resolve the static
# dev bearer token to a real row.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    op.create_table('tenants',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('evaluation_suites',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('knowledge_bases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('source_type', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('models',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=64), nullable=False),
    sa.Column('model_id', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tools',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('input_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('output_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'name', name='uq_tools_tenant_name')
    )
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email')
    )
    # agents.latest_version_id -> agent_versions.id is circular (agent_versions.agent_id
    # -> agents.id). Create the column here but WITHOUT its FK constraint; the FK is
    # added via a deferred op.create_foreign_key() call below, once agent_versions exists.
    op.create_table('agents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('slug', sa.String(length=255), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('owner_user_id', sa.UUID(), nullable=True),
    sa.Column('latest_version_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'slug', name='uq_agents_tenant_slug')
    )
    op.create_table('audit_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('actor_user_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=128), nullable=False),
    sa.Column('resource_type', sa.String(length=64), nullable=False),
    sa.Column('resource_id', sa.String(length=255), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('documents',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('knowledge_base_id', sa.UUID(), nullable=False),
    sa.Column('source_uri', sa.Text(), nullable=False),
    sa.Column('title', sa.String(length=512), nullable=True),
    sa.Column('checksum', sa.String(length=128), nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('policies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('rule', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('agent_versions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('agent_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.String(length=64), nullable=False),
    sa.Column('yaml_source', sa.Text(), nullable=False),
    sa.Column('schema_version', sa.String(length=64), nullable=True),
    sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('validation_status', sa.String(length=32), nullable=False),
    sa.Column('validation_errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('agent_id', 'version', name='uq_agent_versions_agent_version')
    )

    # Deferred circular FK: now that agent_versions exists, wire up
    # agents.latest_version_id -> agent_versions.id.
    op.create_foreign_key(
        'fk_agents_latest_version_id', 'agents', 'agent_versions',
        ['latest_version_id'], ['id'],
    )

    op.create_table('deployments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('agent_version_id', sa.UUID(), nullable=False),
    sa.Column('environment', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('idempotency_key', sa.Text(), nullable=True),
    sa.Column('deployed_by', sa.UUID(), nullable=True),
    sa.Column('deployed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('rolled_back_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['agent_version_id'], ['agent_versions.id'], ),
    sa.ForeignKeyConstraint(['deployed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_deployments_version_idempotency_key', 'deployments', ['agent_version_id', 'idempotency_key'], unique=True, postgresql_where=sa.text('idempotency_key IS NOT NULL'))
    op.create_table('eval_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('evaluation_suite_id', sa.UUID(), nullable=False),
    sa.Column('agent_version_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['agent_version_id'], ['agent_versions.id'], ),
    sa.ForeignKeyConstraint(['evaluation_suite_id'], ['evaluation_suites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('executions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('deployment_id', sa.UUID(), nullable=False),
    sa.Column('agent_version_id', sa.UUID(), nullable=False),
    sa.Column('tenant_id', sa.UUID(), nullable=False),
    sa.Column('mode', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('temporal_workflow_id', sa.String(length=255), nullable=True),
    sa.Column('idempotency_key', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['agent_version_id'], ['agent_versions.id'], ),
    sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_executions_version_idempotency_key', 'executions', ['agent_version_id', 'idempotency_key'], unique=True, postgresql_where=sa.text('idempotency_key IS NOT NULL'))
    op.create_table('eval_results',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('eval_run_id', sa.UUID(), nullable=False),
    sa.Column('execution_id', sa.UUID(), nullable=True),
    sa.Column('case_id', sa.String(length=255), nullable=False),
    sa.Column('score', sa.Numeric(precision=9, scale=4), nullable=True),
    sa.Column('passed', sa.Boolean(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['eval_run_id'], ['eval_runs.id'], ),
    sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # execution_steps: Timescale hypertable partitioned on started_at. The
    # partitioning column must be part of the primary key (verified against
    # a live timescaledb:latest-pg16 container, extension v2.29.1: any
    # unique index/constraint on a hypertable that omits the partitioning
    # column is rejected outright -- "cannot create a unique index without
    # the column ... (used in partitioning)" -- in either creation order).
    # So the PK here is composite (id, started_at); there is intentionally
    # no separate UNIQUE(id). tool_calls/model_calls instead FK against the
    # composite key via their own execution_step_started_at column.
    op.create_table('execution_steps',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('execution_id', sa.UUID(), nullable=False),
    sa.Column('parent_step_id', sa.UUID(), nullable=True),
    sa.Column('step_type', sa.String(length=64), nullable=False),
    sa.Column('node_id', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('input', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('otel_span_id', sa.String(length=64), nullable=True),
    sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
    sa.PrimaryKeyConstraint('id', 'started_at')
    )
    op.create_index('ix_execution_steps_execution_started', 'execution_steps', ['execution_id', 'started_at'], unique=False)

    # Convert to a hypertable. Verified the exact function signature against
    # the timescaledb extension actually shipped in timescale/timescaledb:
    # latest-pg16 (v2.29.1 at the time of writing): `\df create_hypertable`
    # shows both the modern by_range()-dimension overload and the legacy
    # positional-string overload are present; we use the modern one.
    op.execute(
        "SELECT create_hypertable('execution_steps', by_range('started_at'), if_not_exists => TRUE);"
    )

    op.create_table('policy_decisions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('policy_id', sa.UUID(), nullable=True),
    sa.Column('execution_id', sa.UUID(), nullable=False),
    sa.Column('decision', sa.String(length=32), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
    sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('approvals',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('execution_id', sa.UUID(), nullable=False),
    sa.Column('execution_step_id', sa.UUID(), nullable=True),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('approver_user_id', sa.UUID(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('timeout_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['approver_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('model_calls',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('execution_step_id', sa.UUID(), nullable=False),
    sa.Column('execution_step_started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('provider', sa.String(length=64), nullable=False),
    sa.Column('model_id', sa.String(length=255), nullable=False),
    sa.Column('prompt_tokens', sa.Integer(), nullable=False),
    sa.Column('completion_tokens', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=False),
    sa.Column('cost_usd', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['execution_step_id', 'execution_step_started_at'], ['execution_steps.id', 'execution_steps.started_at'], name='fk_model_calls_execution_step'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tool_calls',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('execution_step_id', sa.UUID(), nullable=False),
    sa.Column('execution_step_started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('tool_id', sa.UUID(), nullable=False),
    sa.Column('permission_used', sa.String(length=32), nullable=False),
    sa.Column('request', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('policy_decision_id', sa.UUID(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['execution_step_id', 'execution_step_started_at'], ['execution_steps.id', 'execution_steps.started_at'], name='fk_tool_calls_execution_step'),
    sa.ForeignKeyConstraint(['policy_decision_id'], ['policy_decisions.id'], ),
    sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Seed the two deterministic tenant/user rows used by the Phase-1
    # static-bearer-token auth shim (see agentforge_control_plane.deps).
    op.execute(
        f"""
        INSERT INTO tenants (id, name, slug, created_at)
        VALUES ('{DEFAULT_TENANT_ID}', 'Default Tenant', 'default', now())
        ON CONFLICT (id) DO NOTHING;
        """
    )
    op.execute(
        f"""
        INSERT INTO users (id, tenant_id, email, display_name, role, created_at)
        VALUES ('{DEFAULT_USER_ID}', '{DEFAULT_TENANT_ID}', 'dev@agentforge.local', 'Dev User', 'admin', now())
        ON CONFLICT (id) DO NOTHING;
        """
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('tool_calls')
    op.drop_table('model_calls')
    op.drop_table('approvals')
    op.drop_table('policy_decisions')
    op.drop_index('ix_execution_steps_execution_started', table_name='execution_steps')
    op.drop_table('execution_steps')
    op.drop_table('eval_results')
    op.drop_index('uq_executions_version_idempotency_key', table_name='executions', postgresql_where=sa.text('idempotency_key IS NOT NULL'))
    op.drop_table('executions')
    op.drop_table('eval_runs')
    op.drop_index('uq_deployments_version_idempotency_key', table_name='deployments', postgresql_where=sa.text('idempotency_key IS NOT NULL'))
    op.drop_table('deployments')
    op.drop_constraint('fk_agents_latest_version_id', 'agents', type_='foreignkey')
    op.drop_table('agent_versions')
    op.drop_table('policies')
    op.drop_table('documents')
    op.drop_table('audit_log')
    op.drop_table('agents')
    op.drop_table('users')
    op.drop_table('tools')
    op.drop_table('models')
    op.drop_table('knowledge_bases')
    op.drop_table('evaluation_suites')
    op.drop_table('tenants')
    # ### end Alembic commands ###

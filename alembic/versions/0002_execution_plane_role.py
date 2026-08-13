"""execution_plane_role

Creates the scoped `agentforge_execution` Postgres role used by
agentforge-agent-execution-platform, and grants it SELECT/INSERT/UPDATE on
exactly the 8 execution-owned tables. This role gets zero DDL rights
anywhere, and zero grants of any kind on control-plane-owned tables
(agents, agent_versions, deployments, tenants, users, policies, tools,
models, knowledge_bases, documents, evaluation_suites, audit_log) --
Postgres enforces FK referential integrity for the inserting role
regardless of that role's own SELECT privileges on the referenced table,
so no extra grants are needed there for FKs like executions.tenant_id to
work.

NOTE on ALTER DEFAULT PRIVILEGES: Postgres's default-privileges mechanism
is scoped per (schema, creating role) and cannot filter by table name, so
there is no way to express "auto-grant on future *execution-owned* tables
only" without also auto-granting on any future control-plane table created
by the same migrating role -- which the spec for this role explicitly
forbids. Since control-plane is the only DDL-capable identity and Phase 1
creates all 8 execution-owned tables up front in 0001, we deliberately
skip a schema-wide ALTER DEFAULT PRIVILEGES here. Any future migration
that adds a new execution-owned table must include its own explicit GRANT
statement for agentforge_execution, the same way this migration does for
the initial 8.

Revision ID: 0002_execution_plane_role
Revises: 0001_initial_schema
Create Date: 2026-08-13 20:30:00.000000

"""
import os
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002_execution_plane_role'
down_revision: Union[str, Sequence[str], None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_NAME = "agentforge_execution"

# The 8 execution-plane-owned tables (see agentforge_control_plane.models
# and the matching hand-maintained models in
# agentforge-agent-execution-platform/src/agentforge_execution_platform/models.py).
EXECUTION_OWNED_TABLES = [
    "executions",
    "execution_steps",
    "tool_calls",
    "model_calls",
    "policy_decisions",
    "approvals",
    "eval_runs",
    "eval_results",
]


def upgrade() -> None:
    password = os.environ.get("EXECUTION_ROLE_PASSWORD", "execution_dev_password")
    # Escape single quotes for safe inline use in a SQL string literal.
    # This role's password is a deployment-time secret read from the
    # environment at migration-run time, not user input, so simple quote
    # doubling (the standard SQL escaping mechanism) is sufficient here.
    escaped_password = password.replace("'", "''")

    conn = op.get_bind()

    # Idempotent role creation: check pg_roles first rather than relying on
    # CREATE ROLE IF NOT EXISTS (which Postgres doesn't support) or
    # catching an exception mid-migration.
    role_exists = conn.exec_driver_sql(
        "SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE_NAME,)
    ).scalar()

    if role_exists:
        # Role may already exist from a prior partial run; keep the
        # password in sync with the current EXECUTION_ROLE_PASSWORD.
        op.execute(f"ALTER ROLE {ROLE_NAME} WITH LOGIN PASSWORD '{escaped_password}';")
    else:
        op.execute(f"CREATE ROLE {ROLE_NAME} WITH LOGIN PASSWORD '{escaped_password}';")

    op.execute(f"GRANT CONNECT ON DATABASE agentforge TO {ROLE_NAME};")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME};")

    for table in EXECUTION_OWNED_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO {ROLE_NAME};")

    # Explicitly no DDL rights (no CREATE on schema/database), no DELETE,
    # no REFERENCES, and nothing at all on control-plane-owned tables.


def downgrade() -> None:
    for table in EXECUTION_OWNED_TABLES:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE ON TABLE {table} FROM {ROLE_NAME};")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE_NAME};")
    op.execute(f"REVOKE CONNECT ON DATABASE agentforge FROM {ROLE_NAME};")
    op.execute(f"DROP ROLE IF EXISTS {ROLE_NAME};")

"""execution_role_delete_grant

Grants `agentforge_execution` DELETE on the four tables its own
wipe-and-redo retry guard (agentforge-agent-execution-platform's
execution_service.py -- see `run_graph_and_persist`'s handling of
execution.status in ("failed", "pending_approval")) actually deletes from
when a previously-failed or previously-paused execution is retried/resumed:
execution_steps, tool_calls, model_calls, policy_decisions.

0002_execution_plane_role deliberately withheld DELETE ("Explicitly no DDL
rights ... no DELETE") when only the *initial-attempt* INSERT/SELECT/UPDATE
paths existed. That guard code already existed before this migration (the
Phase 6 wipe-and-redo path for a logically-failed `durable`/`human_in_loop`
execution retry), but was apparently never exercised against a real
committed failure before Phase 7's human-approval work hit it for real --
this migration closes that gap rather than leaving the retry/resume path
broken. `approvals` is deliberately NOT included here: Phase 7's guard
never deletes from it (it's the audit record of a human's decision and
must survive the wipe -- see execution_service.py).

Revision ID: 0006_execution_role_delete_grant
Revises: 0005_memory_tables
Create Date: 2026-08-14 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0006_execution_role_delete_grant'
down_revision: Union[str, Sequence[str], None] = '0005_memory_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_NAME = "agentforge_execution"

# Exactly the tables execution_service.py's wipe-and-redo guard issues
# DELETE against -- not the full EXECUTION_OWNED_TABLES list from
# 0002_execution_plane_role (`executions` is only ever UPDATEd in place,
# never deleted; `approvals`/`eval_runs`/`eval_results` are never touched
# by this guard either).
WIPE_TABLES = [
    "execution_steps",
    "tool_calls",
    "model_calls",
    "policy_decisions",
]


def upgrade() -> None:
    for table in WIPE_TABLES:
        op.execute(f"GRANT DELETE ON TABLE {table} TO {ROLE_NAME};")


def downgrade() -> None:
    for table in WIPE_TABLES:
        op.execute(f"REVOKE DELETE ON TABLE {table} FROM {ROLE_NAME};")

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.models import Agent, AgentVersion
from agentforge_control_plane.schemas import AgentOut

router = APIRouter(prefix="/agent-versions", tags=["versions"])


@router.get("/{version_id}/agent", response_model=AgentOut)
def get_agent_for_version(
    version_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Agent:
    """Resolve an `agent_version_id` straight to its owning `Agent`, without
    the caller needing to already know `agent_id`.

    Added for agentforge-agent-execution-platform's Phase 7 `/approvals`
    enrichment path (see that service's routers/approvals.py): `Execution`
    rows only carry `agent_version_id`, by design -- "the execution-owned
    tables never learned about `agents`" (see that service's
    routers/executions.py) -- so the existing
    `GET /agents/{agent_id}/versions/{version_id}` route can't be used
    there; this is the one place a version_id-only lookup is needed.
    """
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")

    agent = db.get(Agent, version.agent_id)
    if agent is None or agent.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")

    return agent

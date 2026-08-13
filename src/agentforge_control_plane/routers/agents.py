import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.models import Agent
from agentforge_control_plane.schemas import AgentCreate, AgentListOut, AgentOut, AgentPatch

router = APIRouter(prefix="/agents", tags=["agents"])


def _encode_cursor(created_at: datetime, agent_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{agent_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = raw.split("|")
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    body: AgentCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Agent:
    agent = Agent(
        tenant_id=auth.tenant_id,
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        owner_user_id=auth.user_id,
        status="active",
    )
    db.add(agent)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Agent with slug '{body.slug}' already exists"
        ) from exc
    db.refresh(agent)
    return agent


@router.get("", response_model=AgentListOut)
def list_agents(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> AgentListOut:
    stmt = select(Agent).where(Agent.tenant_id == auth.tenant_id)
    if cursor:
        created_at, agent_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Agent.created_at < created_at) | ((Agent.created_at == created_at) & (Agent.id < agent_id))
        )
    stmt = stmt.order_by(Agent.created_at.desc(), Agent.id.desc()).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return AgentListOut(items=[AgentOut.model_validate(a) for a in rows], next_cursor=next_cursor)


def _get_agent_or_404(agent_id: uuid.UUID, auth: AuthContext, db: Session) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None or agent.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Agent:
    return _get_agent_or_404(agent_id, auth, db)


@router.patch("/{agent_id}", response_model=AgentOut)
def patch_agent(
    agent_id: uuid.UUID,
    body: AgentPatch,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Agent:
    agent = _get_agent_or_404(agent_id, auth, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}", response_model=AgentOut)
def delete_agent(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Agent:
    agent = _get_agent_or_404(agent_id, auth, db)
    agent.status = "retired"
    db.commit()
    db.refresh(agent)
    return agent

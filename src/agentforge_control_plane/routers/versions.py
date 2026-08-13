import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.models import AgentVersion
from agentforge_control_plane.routers.agents import _get_agent_or_404
from agentforge_control_plane.schemas import AgentVersionCreate, AgentVersionOut
from agentforge_control_plane.validation import validate_yaml_source

router = APIRouter(prefix="/agents", tags=["versions"])


def _next_version_label(db: Session, agent_id: uuid.UUID) -> str:
    count = db.execute(
        select(AgentVersion).where(AgentVersion.agent_id == agent_id)
    ).scalars().all()
    return f"0.0.{len(count) + 1}"


@router.get("/{agent_id}/versions", response_model=list[AgentVersionOut])
def list_versions(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[AgentVersion]:
    _get_agent_or_404(agent_id, auth, db)
    stmt = (
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.created_at.desc())
    )
    return list(db.execute(stmt).scalars())


@router.post("/{agent_id}/versions", response_model=AgentVersionOut, status_code=status.HTTP_201_CREATED)
def create_version(
    agent_id: uuid.UUID,
    body: AgentVersionCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> AgentVersion:
    agent = _get_agent_or_404(agent_id, auth, db)

    result = validate_yaml_source(body.yaml_source, auth.tenant_id, db)

    version_label = body.version
    if version_label is None and result.parsed and isinstance(result.parsed.get("agent"), dict):
        version_label = result.parsed["agent"].get("version")
    if version_label is None:
        version_label = _next_version_label(db, agent_id)

    version = AgentVersion(
        agent_id=agent_id,
        version=version_label,
        yaml_source=body.yaml_source,
        schema_version=result.schema_version,
        validated_at=datetime.now(UTC),
        validation_status="valid" if result.valid else "invalid",
        validation_errors=[e for e in result.errors] if result.errors else None,
        created_by=auth.user_id,
    )
    db.add(version)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Fall back to a guaranteed-unique version label on collision
        # (e.g. two versions saved in the same request with the same
        # agent.version in the YAML).
        version.version = f"{version_label}+{uuid.uuid4().hex[:8]}"
        db.add(version)
        db.commit()
    db.refresh(version)

    agent.latest_version_id = version.id
    db.commit()

    return version


@router.get("/{agent_id}/versions/{version_id}", response_model=AgentVersionOut)
def get_version(
    agent_id: uuid.UUID,
    version_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> AgentVersion:
    _get_agent_or_404(agent_id, auth, db)
    version = db.get(AgentVersion, version_id)
    if version is None or version.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")
    return version

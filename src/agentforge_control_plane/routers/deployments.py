import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.models import AgentVersion, Deployment
from agentforge_control_plane.routers.agents import _get_agent_or_404
from agentforge_control_plane.schemas import DeploymentCreate, DeploymentOut

router = APIRouter(prefix="/agents", tags=["deployments"])


@router.post("/{agent_id}/deploy", response_model=DeploymentOut)
def deploy_agent_version(
    agent_id: uuid.UUID,
    body: DeploymentCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Deployment:
    _get_agent_or_404(agent_id, auth, db)

    version = db.get(AgentVersion, body.agent_version_id)
    if version is None or version.agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")

    # Idempotency-Key dedup: a repeat call with the same key for the same
    # logical deploy attempt (same agent_version_id) returns the original
    # deployment rather than creating a new one.
    if idempotency_key:
        existing = db.execute(
            select(Deployment).where(
                Deployment.agent_version_id == body.agent_version_id,
                Deployment.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            response.status_code = status.HTTP_200_OK
            return existing

    if version.validation_status != "valid":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Agent version {version.id} is not valid (validation_status={version.validation_status})",
        )

    # Supersede any other active deployment of this agent in the same
    # environment so "the active deployment" is unambiguous.
    other_versions = select(AgentVersion.id).where(AgentVersion.agent_id == agent_id)
    previously_active = db.execute(
        select(Deployment).where(
            Deployment.agent_version_id.in_(other_versions),
            Deployment.environment == body.environment,
            Deployment.status == "active",
        )
    ).scalars()
    for dep in previously_active:
        dep.status = "superseded"

    deployment = Deployment(
        agent_version_id=body.agent_version_id,
        environment=body.environment,
        status="active",
        idempotency_key=idempotency_key,
        deployed_by=auth.user_id,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    response.status_code = status.HTTP_201_CREATED
    return deployment


@router.get("/{agent_id}/deployments", response_model=list[DeploymentOut])
def list_deployments(
    agent_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[Deployment]:
    _get_agent_or_404(agent_id, auth, db)
    version_ids = select(AgentVersion.id).where(AgentVersion.agent_id == agent_id)
    stmt = (
        select(Deployment)
        .where(Deployment.agent_version_id.in_(version_ids))
        .order_by(Deployment.deployed_at.desc())
    )
    return list(db.execute(stmt).scalars())

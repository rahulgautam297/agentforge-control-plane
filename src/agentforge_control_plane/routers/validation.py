import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.routers.agents import _get_agent_or_404
from agentforge_control_plane.schemas import ValidationRequest, ValidationResult
from agentforge_control_plane.validation import validate_yaml_source

router = APIRouter(prefix="/agents", tags=["validation"])


@router.post("/validate", response_model=ValidationResult)
def validate_stateless(
    body: ValidationRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ValidationResult:
    result = validate_yaml_source(body.yaml_source, auth.tenant_id, db)
    return ValidationResult(valid=result.valid, schema_version=result.schema_version, errors=result.errors)


@router.post("/{agent_id}/validate", response_model=ValidationResult)
def validate_for_agent(
    agent_id: uuid.UUID,
    body: ValidationRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ValidationResult:
    _get_agent_or_404(agent_id, auth, db)
    result = validate_yaml_source(body.yaml_source, auth.tenant_id, db)
    return ValidationResult(valid=result.valid, schema_version=result.schema_version, errors=result.errors)

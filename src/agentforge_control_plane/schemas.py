import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --------------------------------------------------------------------------
# Agents
# --------------------------------------------------------------------------


class AgentCreate(BaseModel):
    slug: str
    display_name: str
    description: str | None = None


class AgentPatch(BaseModel):
    display_name: str | None = None
    description: str | None = None
    status: str | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    slug: str
    display_name: str
    description: str | None
    owner_user_id: uuid.UUID | None
    latest_version_id: uuid.UUID | None
    status: str
    created_at: datetime
    updated_at: datetime


class AgentListOut(BaseModel):
    items: list[AgentOut]
    next_cursor: str | None = None


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


class ValidationError(BaseModel):
    code: str
    message: str
    field: str | None = None


class ValidationRequest(BaseModel):
    yaml_source: str


class ValidationResult(BaseModel):
    valid: bool
    schema_version: str | None = None
    errors: list[ValidationError] = []


# --------------------------------------------------------------------------
# Agent versions
# --------------------------------------------------------------------------


class AgentVersionCreate(BaseModel):
    yaml_source: str
    version: str | None = None


class AgentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    version: str
    yaml_source: str
    schema_version: str | None
    validated_at: datetime | None
    validation_status: str
    validation_errors: list[dict] | None
    created_by: uuid.UUID | None
    created_at: datetime


# --------------------------------------------------------------------------
# Deployments
# --------------------------------------------------------------------------


class DeploymentCreate(BaseModel):
    agent_version_id: uuid.UUID
    environment: str


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_version_id: uuid.UUID
    environment: str
    status: str
    idempotency_key: str | None
    deployed_by: uuid.UUID | None
    deployed_at: datetime
    rolled_back_at: datetime | None

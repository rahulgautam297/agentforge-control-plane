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
# Tools
# --------------------------------------------------------------------------


class ToolCreate(BaseModel):
    name: str
    description: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None


class ToolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    input_schema: dict | None
    output_schema: dict | None
    created_at: datetime


class ToolListOut(BaseModel):
    items: list[ToolOut]
    next_cursor: str | None = None


# --------------------------------------------------------------------------
# Policies
# --------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    name: str
    rule: dict


class PolicyPatch(BaseModel):
    name: str | None = None
    rule: dict | None = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    rule: dict
    created_by: uuid.UUID | None
    created_at: datetime


class PolicyListOut(BaseModel):
    items: list[PolicyOut]
    next_cursor: str | None = None


# --------------------------------------------------------------------------
# Knowledge bases / documents
# --------------------------------------------------------------------------


class KnowledgeBaseCreate(BaseModel):
    name: str
    source_type: str


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    source_type: str
    status: str
    created_at: datetime


class KnowledgeBaseListOut(BaseModel):
    items: list[KnowledgeBaseOut]
    next_cursor: str | None = None


class DocumentCreate(BaseModel):
    source_uri: str
    title: str | None = None
    content: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_uri: str
    title: str | None
    checksum: str
    indexed_at: datetime | None
    chunk_count: int | None


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

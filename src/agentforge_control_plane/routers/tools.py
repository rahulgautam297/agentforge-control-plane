import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.models import Tool
from agentforge_control_plane.schemas import ToolCreate, ToolListOut, ToolOut

router = APIRouter(prefix="/tools", tags=["tools"])


def _encode_cursor(created_at: datetime, tool_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{tool_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = raw.split("|")
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


@router.post("", response_model=ToolOut, status_code=status.HTTP_201_CREATED)
def create_tool(
    body: ToolCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Tool:
    tool = Tool(
        tenant_id=auth.tenant_id,
        name=body.name,
        description=body.description,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
    )
    db.add(tool)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Tool with name '{body.name}' already exists"
        ) from exc
    db.refresh(tool)
    return tool


@router.get("", response_model=ToolListOut)
def list_tools(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ToolListOut:
    stmt = select(Tool).where(Tool.tenant_id == auth.tenant_id)
    if cursor:
        created_at, tool_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Tool.created_at < created_at) | ((Tool.created_at == created_at) & (Tool.id < tool_id))
        )
    stmt = stmt.order_by(Tool.created_at.desc(), Tool.id.desc()).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return ToolListOut(items=[ToolOut.model_validate(t) for t in rows], next_cursor=next_cursor)


def _get_tool_or_404(tool_id: uuid.UUID, auth: AuthContext, db: Session) -> Tool:
    tool = db.get(Tool, tool_id)
    if tool is None or tool.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")
    return tool


@router.get("/{tool_id}", response_model=ToolOut)
def get_tool(
    tool_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Tool:
    return _get_tool_or_404(tool_id, auth, db)

import base64
import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.execution_plane_client import ExecutionPlaneClient, ExecutionPlaneError
from agentforge_control_plane.models import Document, KnowledgeBase
from agentforge_control_plane.schemas import (
    DocumentCreate,
    DocumentOut,
    KnowledgeBaseCreate,
    KnowledgeBaseListOut,
    KnowledgeBaseOut,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _encode_cursor(created_at: datetime, kb_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{kb_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = raw.split("|")
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    body: KnowledgeBaseCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> KnowledgeBase:
    kb = KnowledgeBase(
        tenant_id=auth.tenant_id,
        name=body.name,
        source_type=body.source_type,
        status="active",
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@router.get("", response_model=KnowledgeBaseListOut)
def list_knowledge_bases(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> KnowledgeBaseListOut:
    stmt = select(KnowledgeBase).where(KnowledgeBase.tenant_id == auth.tenant_id)
    if cursor:
        created_at, kb_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (KnowledgeBase.created_at < created_at)
            | ((KnowledgeBase.created_at == created_at) & (KnowledgeBase.id < kb_id))
        )
    stmt = stmt.order_by(KnowledgeBase.created_at.desc(), KnowledgeBase.id.desc()).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return KnowledgeBaseListOut(items=[KnowledgeBaseOut.model_validate(k) for k in rows], next_cursor=next_cursor)


def _get_knowledge_base_or_404(kb_id: uuid.UUID, auth: AuthContext, db: Session) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if kb is None or kb.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
    return kb


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseOut)
def get_knowledge_base(
    knowledge_base_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> KnowledgeBase:
    return _get_knowledge_base_or_404(knowledge_base_id, auth, db)


@router.post("/{knowledge_base_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(
    knowledge_base_id: uuid.UUID,
    body: DocumentCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Document:
    _get_knowledge_base_or_404(knowledge_base_id, auth, db)

    checksum = hashlib.sha256(body.content.encode()).hexdigest()
    document = Document(
        knowledge_base_id=knowledge_base_id,
        source_uri=body.source_uri,
        title=body.title,
        checksum=checksum,
        indexed_at=None,
        chunk_count=None,
    )
    db.add(document)
    db.flush()

    client = ExecutionPlaneClient()
    try:
        result = client.ingest_document(
            knowledge_base_id=knowledge_base_id,
            document_id=document.id,
            source_uri=body.source_uri,
            title=body.title,
            content=body.content,
        )
    except ExecutionPlaneError as exc:
        # Persist the document row as-is (un-indexed, indexed_at stays None)
        # rather than losing it -- the ingest can be retried later.
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"execution-plane ingestion failed: {exc.detail}",
        ) from exc
    finally:
        client.close()

    document.indexed_at = datetime.now(UTC)
    document.chunk_count = result["chunk_count"]
    db.commit()
    db.refresh(document)
    return document


@router.get("/{knowledge_base_id}/documents", response_model=list[DocumentOut])
def list_documents(
    knowledge_base_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[Document]:
    _get_knowledge_base_or_404(knowledge_base_id, auth, db)
    stmt = select(Document).where(Document.knowledge_base_id == knowledge_base_id)
    return list(db.execute(stmt).scalars())

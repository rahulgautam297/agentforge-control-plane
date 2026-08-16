import base64
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.models import Policy
from agentforge_control_plane.schemas import PolicyCreate, PolicyListOut, PolicyOut, PolicyPatch

router = APIRouter(prefix="/policies", tags=["policies"])

_VALID_EFFECTS = {"allow", "deny", "human_approval"}


def _validate_rule_shape(rule: dict) -> None:
    """Light structural sanity check on a policy `rule` JSONB payload.

    Per ADR-0008 / doc 07, the rule contract is a small declarative object:
    {tool_id: str, action: str, resource_pattern?: str, effect: allow|deny|human_approval}.
    This is not a full evaluation -- just enough to reject a garbage payload
    at write time. The execution plane owns actually interpreting the rule.
    """
    if not isinstance(rule, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_policy_rule", "message": "rule must be a JSON object.", "field": "rule"},
        )
    if not isinstance(rule.get("tool_id"), str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_policy_rule",
                "message": "rule.tool_id is required and must be a string.",
                "field": "rule",
            },
        )
    if not isinstance(rule.get("action"), str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_policy_rule",
                "message": "rule.action is required and must be a string.",
                "field": "rule",
            },
        )
    if rule.get("effect") not in _VALID_EFFECTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_policy_rule",
                "message": f"rule.effect is required and must be one of {sorted(_VALID_EFFECTS)}.",
                "field": "rule",
            },
        )


def _encode_cursor(created_at: datetime, policy_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{policy_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = raw.split("|")
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor") from exc


@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: PolicyCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Policy:
    _validate_rule_shape(body.rule)
    policy = Policy(
        tenant_id=auth.tenant_id,
        name=body.name,
        rule=body.rule,
        created_by=auth.user_id,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("", response_model=PolicyListOut)
def list_policies(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> PolicyListOut:
    stmt = select(Policy).where(Policy.tenant_id == auth.tenant_id)
    if cursor:
        created_at, policy_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Policy.created_at < created_at) | ((Policy.created_at == created_at) & (Policy.id < policy_id))
        )
    stmt = stmt.order_by(Policy.created_at.desc(), Policy.id.desc()).limit(limit + 1)
    rows = list(db.execute(stmt).scalars())

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return PolicyListOut(items=[PolicyOut.model_validate(p) for p in rows], next_cursor=next_cursor)


def _get_policy_or_404(policy_id: uuid.UUID, auth: AuthContext, db: Session) -> Policy:
    policy = db.get(Policy, policy_id)
    if policy is None or policy.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return policy


@router.get("/{policy_id}", response_model=PolicyOut)
def get_policy(
    policy_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Policy:
    return _get_policy_or_404(policy_id, auth, db)


@router.patch("/{policy_id}", response_model=PolicyOut)
def patch_policy(
    policy_id: uuid.UUID,
    body: PolicyPatch,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Policy:
    policy = _get_policy_or_404(policy_id, auth, db)
    updates = body.model_dump(exclude_unset=True)
    if "rule" in updates:
        _validate_rule_shape(updates["rule"])
    for field, value in updates.items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return policy

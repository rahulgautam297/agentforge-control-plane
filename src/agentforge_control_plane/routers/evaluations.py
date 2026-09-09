import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentforge_control_plane.db import get_db
from agentforge_control_plane.deps import AuthContext, get_current_auth
from agentforge_control_plane.eval_suite import (
    EvalSuiteParseError,
    parse_and_validate_suite,
)
from agentforge_control_plane.models import EvaluationSuite
from agentforge_control_plane.schemas import (
    EvaluationSuiteCreate,
    EvaluationSuiteListOut,
    EvaluationSuiteOut,
)

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

# Only suite CRUD lives here -- per doc09's "Evaluations -- control plane
# (definitions) / execution plane (runs)" split, and doc08's table
# ownership (evaluation_suites is control-plane-owned; eval_runs/
# eval_results are execution-plane-owned, alongside every other execution
# trace table). `POST /evaluations/{id}/run` and `GET /evaluations/runs/
# {run_id}` are served directly by agentforge-agent-execution-platform
# (see that service's routers/evaluations.py), the same way Executions/
# Approvals already bypass this service entirely -- it pulls a suite's
# `config` from here (GET /evaluations/{id}, below) via its own
# ControlPlaneClient rather than this service pushing a run request over
# there, since a suite's config can be large and a run can be re-triggered
# many times against it.


@router.post("", response_model=EvaluationSuiteOut, status_code=status.HTTP_201_CREATED)
def create_evaluation_suite(
    body: EvaluationSuiteCreate,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> EvaluationSuite:
    try:
        config = parse_and_validate_suite(body.yaml_source)
    except EvalSuiteParseError as exc:
        # {code, message, field} -- the "already-structured" HTTPException
        # detail shape main.py's http_exception_handler folds into doc09's
        # `{"error": {...}}` envelope (see routers/policies.py's rule-shape
        # checks for the same convention). `exc.errors` may hold several
        # independent problems at once (see parse_and_validate_suite's own
        # "collect all errors" docstring) -- joined into one message here
        # since the envelope has no list-of-errors slot of its own.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_eval_suite", "message": "; ".join(exc.errors), "field": "yaml_source"},
        ) from exc

    suite = EvaluationSuite(tenant_id=auth.tenant_id, name=body.name, config=config)
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return suite


@router.get("", response_model=EvaluationSuiteListOut)
def list_evaluation_suites(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> EvaluationSuiteListOut:
    stmt = (
        select(EvaluationSuite)
        .where(EvaluationSuite.tenant_id == auth.tenant_id)
        .order_by(EvaluationSuite.created_at.desc())
    )
    return EvaluationSuiteListOut(items=list(db.execute(stmt).scalars()))


def _get_suite_or_404(suite_id: uuid.UUID, auth: AuthContext, db: Session) -> EvaluationSuite:
    suite = db.get(EvaluationSuite, suite_id)
    if suite is None or suite.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation suite not found")
    return suite


@router.get("/{suite_id}", response_model=EvaluationSuiteOut)
def get_evaluation_suite(
    suite_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> EvaluationSuite:
    return _get_suite_or_404(suite_id, auth, db)

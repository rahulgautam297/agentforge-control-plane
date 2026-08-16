import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from agentforge_control_plane.config import get_settings
from agentforge_control_plane.db import engine
from agentforge_control_plane.routers import (
    agent_versions,
    agents,
    deployments,
    knowledge,
    policies,
    tools,
    validation,
    versions,
)

logging.basicConfig(level=logging.INFO)

settings = get_settings()

app = FastAPI(title="AgentForge Control Plane", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Status-code fallback for HTTPExceptions raised with a plain string `detail`
# (the majority of call sites) -- gives every error response a stable `code`
# even where the raising code didn't specify one explicitly.
_STATUS_CODE_SLUGS = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_failed",
}


def _error_envelope(code: str, message: str, field: str | None = None, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "field": field, "details": details or {}}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Normalize every HTTPException into the doc09 `{"error": {...}}` envelope.

    `detail` is either a plain string (most call sites -- deps.py auth
    checks, 404/409/400 lookups) or an already-structured
    `{code, message, field}` dict (routers/policies.py's rule-shape
    checks) -- both are folded into the same shape here rather than
    leaking two different error formats to callers.
    """
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", _STATUS_CODE_SLUGS.get(exc.status_code, "error"))
        message = exc.detail.get("message", "")
        field = exc.detail.get("field")
    else:
        code = _STATUS_CODE_SLUGS.get(exc.status_code, "error")
        message = str(exc.detail)
        field = None
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_envelope(code, message, field),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Normalize FastAPI/Pydantic request-body validation failures (422s
    raised before a route body even runs) into the same envelope."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    field = ".".join(str(p) for p in first.get("loc", []) if p != "body") or None
    message = first.get("msg", "Request validation failed.")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_envelope("validation_failed", message, field, {"errors": errors}),
    )

api_v1 = "/api/v1"
app.include_router(agents.router, prefix=api_v1)
app.include_router(versions.router, prefix=api_v1)
app.include_router(agent_versions.router, prefix=api_v1)
app.include_router(validation.router, prefix=api_v1)
app.include_router(deployments.router, prefix=api_v1)
app.include_router(tools.router, prefix=api_v1)
app.include_router(policies.router, prefix=api_v1)
app.include_router(knowledge.router, prefix=api_v1)


@app.get("/healthz")
def healthz() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}

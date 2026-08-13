import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from agentforge_control_plane.config import get_settings
from agentforge_control_plane.db import engine
from agentforge_control_plane.routers import agents, deployments, validation, versions

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

api_v1 = "/api/v1"
app.include_router(agents.router, prefix=api_v1)
app.include_router(versions.router, prefix=api_v1)
app.include_router(validation.router, prefix=api_v1)
app.include_router(deployments.router, prefix=api_v1)


@app.get("/healthz")
def healthz() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}

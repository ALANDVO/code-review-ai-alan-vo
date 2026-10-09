"""
Code Review AI — FastAPI application entry point.

Exports:
  app  — the ASGI application (used by uvicorn and Docker CMD)
  create_app() — factory for testing with custom database path

Demo mode: DEMO_MODE=true + ENV != production enables unauthenticated local access.
Production requires a real Keycloak OIDC provider.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, settings
from app.core.database import Database, get_db
from app.api import reviews, evals, stats
from app.models.schemas import HealthOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_VERSION = "1.0.0"


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    s: Settings = app.state.settings
    logger.info(
        "Code Review AI starting: env=%s demo=%s db=%s",
        s.env,
        s.demo_mode,
        s.database_path,
    )
    if s.demo_mode and s.env != "test":
        logger.warning(
            "DEMO MODE is active. This server must only be accessible on localhost. "
            "Do NOT expose a demo-mode server to the public internet."
        )
    yield
    logger.info("Code Review AI shutting down.")


# ── Factory ────────────────────────────────────────────────────────────────────

def create_app(override_settings: Settings | None = None) -> FastAPI:
    s = override_settings or settings

    application = FastAPI(
        title="Code Review AI",
        description=(
            "Multi-language static analysis and LLM-assisted code review engine. "
            "Deterministic rules work offline; LLM advisory is opt-in."
        ),
        version=_VERSION,
        docs_url="/docs" if s.env != "production" else None,
        redoc_url="/redoc" if s.env != "production" else None,
        lifespan=lifespan,
    )
    if s.demo_mode and (s.env == "production" or s.host not in {"127.0.0.1", "localhost", "::1"}):
        raise RuntimeError("Demo mode requires a loopback host and non-production environment")
    application.state.settings = s
    application.state.db = Database(s.database_path)

    # ── CORS ───────────────────────────────────────────────────────────────────
    allowed_origins = (
        ["http://127.0.0.1:3000", "http://localhost:3000"]
        if s.env != "production"
        else []
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health ─────────────────────────────────────────────────────────────────
    @application.get("/api/health", response_model=HealthOut, tags=["health"])
    async def health_check() -> HealthOut:
        return HealthOut(status="ok", version=_VERSION, demo_mode=s.demo_mode)

    # ── Routers ────────────────────────────────────────────────────────────────
    application.include_router(reviews.router)
    application.include_router(evals.router)
    application.include_router(stats.router)

    # ── Error handlers ─────────────────────────────────────────────────────────
    @application.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    return application


# ── Module-level app instance (used by uvicorn / Docker CMD) ───────────────────
app = create_app()

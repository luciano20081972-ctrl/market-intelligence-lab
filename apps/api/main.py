from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

from apps.api.dependencies import get_db, get_workspace_context
from apps.api.routers import (
    assets,
    backtests,
    comparisons,
    identity,
    infrastructure,
    market_data,
    operations,
    paper_portfolios,
    strategies,
    system,
    watchlists,
)
from apps.api.schemas import HealthResponse
from packages.core.config import Settings, get_settings
from packages.database.session import create_database_engine, make_session_factory
from packages.market_data.observability import correlation_middleware
from packages.observability.sentry import configure_sentry
from packages.security.tenant import install_workspace_guards


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app_engine = engine or create_database_engine(app_settings.database_url)
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.version,
        description="Historical market-data research platform with simulated trading only.",
    )
    app.state.settings = app_settings
    app.state.engine = app_engine
    app.state.session_factory = make_session_factory(app_engine)
    app.state.sentry_enabled = configure_sentry(app_settings)
    install_workspace_guards()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=app_settings.trusted_hosts)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-Workspace-ID",
            "Idempotency-Key",
        ],
    )
    app.middleware("http")(correlation_middleware)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        length = request.headers.get("content-length")
        try:
            body_size = int(length) if length else 0
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
        if body_size > app_settings.max_request_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(session: Session = Depends(get_db)) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return HealthResponse(
                status="degraded", database="unavailable", version=app_settings.version
            )
        return HealthResponse(status="healthy", database="healthy", version=app_settings.version)

    @app.get("/health/live", tags=["system"])
    def liveness() -> dict[str, str]:
        return {"status": "healthy", "version": app_settings.version}

    @app.get("/health/ready", tags=["system"])
    def readiness(session: Session = Depends(get_db)) -> dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "database_unavailable", "message": "Database is unavailable"},
            ) from exc
        return {"status": "healthy", "database": "healthy", "version": app_settings.version}

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> dict[str, str]:
        return {"name": app_settings.app_name, "docs": str(request.url_for("swagger_ui_html"))}

    protected = [Depends(get_workspace_context)]
    app.include_router(identity.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1", dependencies=protected)
    app.include_router(assets.router, prefix="/api/v1", dependencies=protected)
    app.include_router(watchlists.router, prefix="/api/v1", dependencies=protected)
    app.include_router(strategies.router, prefix="/api/v1", dependencies=protected)
    app.include_router(backtests.router, prefix="/api/v1", dependencies=protected)
    app.include_router(comparisons.router, prefix="/api/v1", dependencies=protected)
    app.include_router(infrastructure.router, prefix="/api/v1", dependencies=protected)
    app.include_router(paper_portfolios.router, prefix="/api/v1", dependencies=protected)
    app.include_router(market_data.router, prefix="/api/v1", dependencies=protected)
    app.include_router(operations.router, prefix="/api/v1", dependencies=protected)
    return app


app = create_app()

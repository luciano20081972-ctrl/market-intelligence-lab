from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse, Response

from apps.api.dependencies import get_db, get_workspace_context
from apps.api.routers import (
    adversarial_intelligence,
    analytics,
    assets,
    backtests,
    comparisons,
    economic_graph,
    hypotheses,
    identity,
    infrastructure,
    market_data,
    native_auth,
    operations,
    optimization,
    paper_portfolios,
    prospective_intelligence,
    research,
    research_intelligence,
    sec_intelligence,
    strategies,
    system,
    upstream,
    watchlists,
    world_data,
)
from apps.api.schemas import HealthResponse
from packages.auth import AuthError, native
from packages.core.config import Settings, get_settings
from packages.database.models import MaintenanceState
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

    @app.exception_handler(RequestValidationError)
    async def safe_validation(request: Request, exc: RequestValidationError) -> Response:
        if request.url.path.startswith("/api/v1/auth/"):
            return JSONResponse(
                status_code=422, content={"detail": "Invalid authentication request"}
            )
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(AuthError)
    async def auth_failure(request: Request, exc: AuthError) -> Response:
        error = native_auth.public_error(exc)
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.detail}, headers=error.headers
        )

    @app.middleware("http")
    async def native_boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if app_settings.auth_mode != "native":
            return await call_next(request)
        is_api = request.url.path.startswith("/api/v1/")
        is_auth = request.url.path.startswith("/api/v1/auth/")
        origin = request.headers.get("origin")
        if is_api and origin is not None and origin not in app_settings.auth_allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "Origin is not allowed"})
        if is_api and (
            request.headers.get("cookie")
            or any(
                key.lower()
                in {"token", "access_token", "password", "authorization", "session_token"}
                for key in request.query_params
            )
        ):
            return JSONResponse(status_code=400, content={"detail": "Unsupported credentials"})
        if is_auth and request.method == "POST":
            if origin not in app_settings.auth_allowed_origins:
                return JSONResponse(status_code=403, content={"detail": "Origin is required"})
            if request.query_params:
                return JSONResponse(status_code=400, content={"detail": "Query is not allowed"})
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 4096:
                    return JSONResponse(status_code=413, content={"detail": "Request too large"})
            request._body = bytes(body)
        try:
            response = await call_next(request)
        except SQLAlchemyError:
            return JSONResponse(status_code=503, content={"detail": "Service unavailable"})
        if is_api:
            response.headers["Cache-Control"] = "no-store"
        return response

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
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            with app.state.session_factory() as maintenance_session:
                maintenance = maintenance_session.scalar(
                    select(MaintenanceState).where(MaintenanceState.enabled.is_(True))
                )
            if maintenance is not None:
                return JSONResponse(
                    status_code=503,
                    content={
                        "detail": {
                            "code": "maintenance_mode",
                            "message": maintenance.reason or "Maintenance is in progress",
                        }
                    },
                )
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
            if app_settings.auth_mode == "native" and not native.ready(session):
                raise HTTPException(503, "Authentication not ready")
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "database_unavailable", "message": "Database is unavailable"},
            ) from exc
        if app_settings.environment.lower() in {"staging", "production"}:
            try:
                schema_revision = session.scalar(text("SELECT version_num FROM alembic_version"))
            except SQLAlchemyError as exc:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "schema_unavailable",
                        "message": "Database schema version is unavailable",
                    },
                ) from exc
            if schema_revision != app_settings.expected_schema_revision:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "schema_outdated",
                        "message": "Database schema is not at the required revision",
                    },
                )
            if app_settings.auth_mode == "supabase" and not app_settings.supabase_url:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "authentication_unconfigured",
                        "message": "Authentication is not configured",
                    },
                )
        return {"status": "healthy", "database": "healthy", "version": app_settings.version}

    @app.get("/health/dependencies", tags=["system"])
    def dependencies(session: Session = Depends(get_db)) -> dict[str, object]:
        database = "healthy"
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            database = "unavailable"
        storage = Path(app_settings.raw_object_store_root)
        storage_status = "healthy" if storage.exists() and storage.is_dir() else "unavailable"
        readiness_status = "ready" if database == storage_status == "healthy" else "not_ready"
        return {
            "status": "HEALTHY" if readiness_status == "ready" else "ACTION_NEEDED",
            "readiness": readiness_status,
            "database": database,
            "required_storage": storage_status,
            "optional_market_data_providers": "independent",
        }

    @app.get("/health/deployment", tags=["system"])
    def deployment_manifest() -> dict[str, str]:
        return {
            "application_version": app_settings.version,
            "git_sha": app_settings.git_sha,
            "alembic_revision": app_settings.expected_schema_revision,
            "build_time": app_settings.build_time,
            "environment": app_settings.environment,
            "frontend_version": app_settings.version,
        }

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> dict[str, str]:
        return {"name": app_settings.app_name, "docs": str(request.url_for("swagger_ui_html"))}

    protected = [Depends(get_workspace_context)]
    app.include_router(identity.router, prefix="/api/v1")
    app.include_router(native_auth.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1", dependencies=protected)
    app.include_router(assets.router, prefix="/api/v1", dependencies=protected)
    app.include_router(watchlists.router, prefix="/api/v1", dependencies=protected)
    app.include_router(strategies.router, prefix="/api/v1", dependencies=protected)
    app.include_router(backtests.router, prefix="/api/v1", dependencies=protected)
    app.include_router(comparisons.router, prefix="/api/v1", dependencies=protected)
    app.include_router(economic_graph.router, prefix="/api/v1", dependencies=protected)
    app.include_router(infrastructure.router, prefix="/api/v1", dependencies=protected)
    app.include_router(paper_portfolios.router, prefix="/api/v1", dependencies=protected)
    app.include_router(market_data.router, prefix="/api/v1", dependencies=protected)
    app.include_router(operations.router, prefix="/api/v1", dependencies=protected)
    app.include_router(sec_intelligence.router, prefix="/api/v1", dependencies=protected)
    app.include_router(analytics.router, prefix="/api/v1", dependencies=protected)
    app.include_router(optimization.router, prefix="/api/v1", dependencies=protected)
    app.include_router(upstream.router, prefix="/api/v1", dependencies=protected)
    app.include_router(world_data.router, prefix="/api/v1", dependencies=protected)
    app.include_router(research.router, prefix="/api/v1", dependencies=protected)
    app.include_router(research_intelligence.router, prefix="/api/v1", dependencies=protected)
    app.include_router(adversarial_intelligence.router, prefix="/api/v1", dependencies=protected)
    app.include_router(prospective_intelligence.router, prefix="/api/v1", dependencies=protected)
    app.include_router(hypotheses.router, prefix="/api/v1", dependencies=protected)
    return app


app = create_app()

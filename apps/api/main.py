from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.routers import assets, backtests, paper_portfolios, strategies, system, watchlists
from apps.api.schemas import HealthResponse
from packages.core.config import Settings, get_settings
from packages.database.session import create_database_engine, make_session_factory


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app_engine = engine or create_database_engine(app_settings.database_url)
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.version,
        description="Research foundation using clearly labeled synthetic demonstration data.",
    )
    app.state.settings = app_settings
    app.state.engine = app_engine
    app.state.session_factory = make_session_factory(app_engine)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health(session: Session = Depends(get_db)) -> HealthResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return HealthResponse(
                status="degraded", database="unavailable", version=app_settings.version
            )
        return HealthResponse(status="healthy", database="healthy", version=app_settings.version)

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> dict[str, str]:
        return {"name": app_settings.app_name, "docs": str(request.url_for("swagger_ui_html"))}

    app.include_router(system.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")
    app.include_router(watchlists.router, prefix="/api/v1")
    app.include_router(strategies.router, prefix="/api/v1")
    app.include_router(backtests.router, prefix="/api/v1")
    app.include_router(paper_portfolios.router, prefix="/api/v1")
    return app


app = create_app()

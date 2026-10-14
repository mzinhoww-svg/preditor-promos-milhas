"""Aplicacao FastAPI."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .limiter import check_rate_limit
from .security import require_api_key
from .settings import cors_allowed_origins


def _startup_check() -> None:
    if not (os.getenv("PREDITOR_API_KEY") or "").strip():
        raise RuntimeError("PREDITOR_API_KEY ausente: API recusa subir")
    if not (os.getenv("DATABASE_URL") or "").strip():
        raise RuntimeError("DATABASE_URL ausente: API recusa subir")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _startup_check()
    yield


def error_handler(_request, exc):
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "erro interno"}})


def create_app() -> FastAPI:
    app = FastAPI(title="preditor-promos-milhas", version="1.0.0", lifespan=lifespan)
    app.add_exception_handler(Exception, error_handler)
    origins = cors_allowed_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["X-API-Key"],
    )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    from .routers import accuracy, alerts, model, predictions, source_health

    deps = [Depends(require_api_key)]
    app.include_router(predictions.router, prefix="/v1", dependencies=deps)
    app.include_router(model.router, prefix="/v1", dependencies=deps)
    app.include_router(source_health.router, prefix="/v1", dependencies=deps)
    app.include_router(alerts.router, prefix="/v1", dependencies=deps)
    app.include_router(accuracy.router, prefix="/v1", dependencies=deps)

    # rate limit dependency global por rota autenticada
    @app.middleware("http")
    async def rate_limit_middleware(request, call_next):
        if request.url.path.startswith("/v1/"):
            key = request.headers.get("X-API-Key")
            if key:
                try:
                    check_rate_limit(request, key)
                except Exception as exc:
                    from fastapi.responses import JSONResponse

                    if getattr(exc, "status_code", None):
                        return JSONResponse(status_code=exc.status_code, content=exc.detail if isinstance(exc.detail, dict) else {"error": {"code": "RATE_LIMITED", "message": str(exc.detail)}})
                    raise
        return await call_next(request)

    return app


app = create_app()

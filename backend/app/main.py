"""
Application entrypoint / app factory.

Route modules stay thin (see app/api/*) -- all business logic lives in
app/services, all persistence in app/repositories. This file wires
routers, CORS, and the global exception handler and nothing else.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.evaluations import router as evaluations_router
from app.api.health import router as health_router
from app.api.job_descriptions import router as jd_router
from app.api.resumes import router as resumes_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import AppError
from app import models  # noqa: F401  (registers ORM models on Base.metadata)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smart Resume Screener API",
        description=(
            "Hybrid deterministic + LLM candidate-JD matching engine with "
            "evidence-based, requirement-level explanations."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Backstop for anything that isn't an AppError -- a bug in a route
        # or service that raised a bare Exception. Log the real error
        # server-side (with traceback) but never leak internal detail
        # (stack traces, exception messages, file paths) to the client.
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
        )

    app.include_router(health_router, prefix="/api")
    app.include_router(resumes_router, prefix="/api")
    app.include_router(jd_router, prefix="/api")
    app.include_router(evaluations_router, prefix="/api")

    return app


app = create_app()

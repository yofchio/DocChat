from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routers import auth as auth_router
from api.routers import chat as chat_router
from api.routers import config as config_router
from api.routers import sessions as sessions_router
from api.routers import notebooks as notebooks_router
from api.routers import notes as notes_router
from api.routers import podcasts as podcasts_router
from api.routers import search as search_router
from api.routers import sources as sources_router
from core.exceptions import (
    AppError,
    AuthenticationError,
    ConfigurationError,
    DatabaseOperationError,
    ExternalServiceError,
    InvalidInputError,
    NotFoundError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DocChat API...")

    try:
        from core.database.migrate import MigrationManager

        mgr = MigrationManager()
        current = await mgr.get_current_version()
        logger.info(f"Current database version: {current}")

        if await mgr.needs_migration():
            logger.warning("Running pending migrations...")
            await mgr.run_migrations()
            new_version = await mgr.get_current_version()
            logger.success(f"Migrations done. DB version: {new_version}")
        else:
            logger.info("Database is up to date")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise RuntimeError(f"Failed to run migrations: {e}") from e

    logger.success("API initialization completed")
    yield
    logger.info("API shutdown complete")


app = FastAPI(
    title="DocChat API",
    description="API for DocChat - AI Document Chat Assistant",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cors_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=_cors_headers(request),
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)}, headers=_cors_headers(request))


@app.exception_handler(InvalidInputError)
async def invalid_input_handler(request: Request, exc: InvalidInputError):
    return JSONResponse(status_code=400, content={"detail": str(exc)}, headers=_cors_headers(request))


@app.exception_handler(AuthenticationError)
async def auth_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(status_code=401, content={"detail": str(exc)}, headers=_cors_headers(request))


@app.exception_handler(ConfigurationError)
async def config_error_handler(request: Request, exc: ConfigurationError):
    return JSONResponse(status_code=422, content={"detail": str(exc)}, headers=_cors_headers(request))


@app.exception_handler(ExternalServiceError)
async def external_error_handler(request: Request, exc: ExternalServiceError):
    return JSONResponse(status_code=502, content={"detail": str(exc)}, headers=_cors_headers(request))


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=500, content={"detail": str(exc)}, headers=_cors_headers(request))


# ── Register routers ──
app.include_router(auth_router.router, prefix="/api")
app.include_router(notebooks_router.router, prefix="/api")
app.include_router(sources_router.router, prefix="/api")
app.include_router(notes_router.router, prefix="/api")
app.include_router(chat_router.router, prefix="/api")
app.include_router(sessions_router.router, prefix="/api")
app.include_router(search_router.router, prefix="/api")
app.include_router(podcasts_router.router, prefix="/api")
app.include_router(config_router.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "DocChat API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}

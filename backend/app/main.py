import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from app.services.operation_guard import ProjectMutationGuard
from app.services.errors import ProviderError, OperationConflict
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError
from sqlalchemy.exc import IntegrityError, OperationalError

from app.database import engine, Base, run_db_migrations, backup_database_before_migration
from app.config import PROJECTS_DIR, RESOURCE_DIR
from app.services.job_queue import recover_interrupted_jobs_on_startup
from app.database import SessionLocal
from app.routers import projects, script, storyboard, characters, locations, generation, render, settings, scenes, research, backup, youtube

# Initialize database tables & auto-migrate missing columns
backup_database_before_migration()
Base.metadata.create_all(bind=engine)
run_db_migrations()

# Recover interrupted jobs on startup
with SessionLocal() as db:
    recover_interrupted_jobs_on_startup(db)

app = FastAPI(
    title="StoryForge AI API",
    description="Local Windows video generation engine for automated long-form YouTube stories.",
    version="1.0.0"
)

app.add_middleware(ProjectMutationGuard)


@app.exception_handler(ProviderError)
async def provider_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.exception_handler(OperationConflict)
@app.exception_handler(ObjectDeletedError)
@app.exception_handler(StaleDataError)
@app.exception_handler(IntegrityError)
async def conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Данные изменились или были удалены. Обновите проект и повторите действие."})


@app.exception_handler(OperationalError)
async def database_error_handler(request, exc):
    import logging
    logging.getLogger(__name__).error("Database operation failed (%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "База данных временно недоступна. Повторите действие позже."})

# The backend is a localhost application. A public web page must not be able
# to read projects or trigger API-key-backed generation through the browser.
LOCAL_ORIGINS = {
    "http://127.0.0.1:8000", "http://localhost:8000",
    "http://127.0.0.1:5173", "http://localhost:5173",
}


@app.middleware("http")
async def block_foreign_browser_origins(request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in LOCAL_ORIGINS:
        return JSONResponse(status_code=403, content={"detail": "Доступ к локальному приложению с другого сайта запрещён."})
    return await call_next(request)


# Enable CORS only for the local Vite development interface.
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(LOCAL_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated project media assets (images, audio clips, video outputs)
app.mount("/media/projects", StaticFiles(directory=str(PROJECTS_DIR)), name="projects_media")

# Include Routers
app.include_router(projects.router)
app.include_router(script.router)
app.include_router(storyboard.router)
app.include_router(scenes.router)
app.include_router(characters.router)
app.include_router(locations.router)
app.include_router(generation.router)
app.include_router(render.router)
app.include_router(settings.router)
app.include_router(research.router)
app.include_router(backup.router)
app.include_router(youtube.router)

# A built frontend can run from the same localhost port; Node/Vite is not
# needed on a customer's machine once the frontend has been built.
FRONTEND_DIST = RESOURCE_DIR / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend_assets")

    @app.get("/", include_in_schema=False)
    def local_frontend():
        return FileResponse(FRONTEND_DIST / "index.html")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "StoryForge AI Backend", "version": "1.0.0"}

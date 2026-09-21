import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.config import PROJECTS_DIR
from app.routers import (
    projects, script, storyboard, characters, locations, generation, render, settings
)

from sqlalchemy import text

# Initialize database tables & auto-migrate missing columns
Base.metadata.create_all(bind=engine)

def auto_migrate_sqlite():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN active_job_id TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists

auto_migrate_sqlite()



app = FastAPI(
    title="StoryForge AI API",
    description="Local Windows video generation engine for automated long-form YouTube stories.",
    version="1.0.0"
)

# Enable CORS for local web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(characters.router)
app.include_router(locations.router)
app.include_router(generation.router)
app.include_router(render.router)
app.include_router(settings.router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "StoryForge AI Backend", "version": "1.0.0"}

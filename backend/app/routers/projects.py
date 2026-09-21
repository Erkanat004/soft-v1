import uuid
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, Script, Scene, Character, Location, Job
from app.schemas import ProjectCreate, ProjectResponse, ProjectUpdate, JobResponse
from app.services.pipeline_service import run_auto_pipeline
from app.services.job_queue import job_manager
from app.services.key_store import has_api_key

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()

@router.delete("")
def clear_all_projects(db: Session = Depends(get_db)):
    """
    Deletes all projects, cancels all jobs, and clears project media directories.
    """
    import shutil, os
    db.query(Job).delete()
    db.query(Project).delete()
    db.commit()

    projects_dir = "projects"
    if os.path.exists(projects_dir):
        for item in os.listdir(projects_dir):
            item_path = os.path.join(projects_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception:
                pass

    return {"message": "All projects and jobs cleared successfully."}

@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    
    # Auto-detect active providers with configured keys if defaults used
    active_tts = payload.active_tts_provider or "elevenlabs"
    if active_tts == "elevenlabs" and not has_api_key("elevenlabs"):
        if has_api_key("fish_audio"):
            active_tts = "fish_audio"
        elif has_api_key("openai_tts") or has_api_key("openai"):
            active_tts = "openai_tts"

    active_img = payload.active_image_provider or "gemini_image"
    if active_img == "gemini_image" and not has_api_key("gemini_image") and not has_api_key("gemini"):
        if has_api_key("openai_image") or has_api_key("openai"):
            active_img = "openai_image"

    custom_name = payload.name.strip() if payload.name and payload.name.strip() and payload.name != "Untitled Story Project" else ""
    project_name = custom_name if custom_name else f"Story ({payload.story_type})"

    project = Project(
        id=project_id,
        name=project_name,
        topic_or_script=payload.topic_or_script,
        input_type=payload.input_type,
        duration_preset=payload.duration_preset,
        language=payload.language,
        story_type=payload.story_type,
        visual_style=payload.visual_style,
        active_text_provider=payload.active_text_provider or "gemini",
        active_image_provider=active_img,
        active_tts_provider=active_tts,
        status="draft",
        current_stage="idle"
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    # Automatically launch AUTO MODE Pipeline in background
    job = job_manager.create_job(db, project_id, "auto_pipeline", 100)
    project.active_job_id = job.id
    db.commit()
    db.refresh(project)

    background_tasks.add_task(run_auto_pipeline, project_id, job.id)

    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(project, key, value)
    
    db.commit()
    db.refresh(project)
    return project

@router.post("/{project_id}/generate", response_model=JobResponse)
def trigger_auto_pipeline(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = job_manager.create_job(db, project_id, "auto_pipeline", 100)
    background_tasks.add_task(run_auto_pipeline, project_id, job.id)
    return job

@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    return {"message": f"Project {project_id} deleted."}

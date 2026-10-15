import uuid
import shutil
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, Script, Scene, Character, Location, Job
from app.schemas import ProjectCreate, ProjectResponse, ProjectUpdate, JobResponse
from app.services.pipeline_service import run_auto_remaining_pipeline
from app.services.render_service import render_full_project_video
from app.services.job_queue import job_manager
from app.services.key_store import has_api_key
from app.config import PROJECTS_DIR

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()

@router.delete("")
def clear_all_projects(db: Session = Depends(get_db)):
    """
    Deletes idle projects and owned media only. Busy projects are guarded.
    """
    projects = db.query(Project).all()
    project_ids = [p.id for p in projects]
    db.query(Job).delete()
    for project in projects:
        db.delete(project)
    db.commit()

    cleanup_warnings = []
    for project_id in project_ids:
        item_path = (PROJECTS_DIR / project_id).resolve()
        if not item_path.is_relative_to(PROJECTS_DIR) or item_path == PROJECTS_DIR:
            cleanup_warnings.append(project_id)
            continue
        try:
            if item_path.is_dir():
                shutil.rmtree(item_path)
        except OSError:
            cleanup_warnings.append(project_id)

    return {"message": "Projects and jobs cleared.", "media_cleanup_warnings": cleanup_warnings}

@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    
    # Creating a project must never start paid media requests merely because
    # unrelated credentials happen to be saved on this computer.
    active_text = payload.active_text_provider or "gemini"
    if "active_text_provider" not in payload.model_fields_set:
        if has_api_key("gemini") and has_api_key("openrouter"):
            active_text = "auto_text"
        elif not has_api_key("gemini") and has_api_key("openrouter"):
            active_text = "openrouter"

    active_tts = (payload.active_tts_provider or "windows_tts") if "active_tts_provider" in payload.model_fields_set else "windows_tts"
    active_img = (payload.active_image_provider or "local_cards") if "active_image_provider" in payload.model_fields_set else "local_cards"

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
        creative_brief=(payload.creative_brief or "").strip()[:4000] or None,
        active_text_provider=active_text,
        active_image_provider=active_img,
        active_tts_provider=active_tts,
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        status="draft",
        current_stage="idle"
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    # Note: Auto-launch removed per Requirement 1. Project is initialized in draft state.
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

    changes = payload.model_dump(exclude_unset=True)
    aspect_changed = "aspect_ratio" in changes and changes["aspect_ratio"] != project.aspect_ratio
    resolution_changed = "resolution" in changes and changes["resolution"] != project.resolution
    style_changed = "global_visual_style" in changes and changes["global_visual_style"] != project.global_visual_style
    voice_changed = "default_voice_id" in changes and changes["default_voice_id"] != project.default_voice_id
    export_settings_changed = any(
        key in changes and changes[key] != getattr(project, key)
        for key in ("subtitle_settings_json", "bg_music_path", "bg_music_volume")
    )

    for key, value in changes.items():
        setattr(project, key, value)

    if aspect_changed or resolution_changed or style_changed or voice_changed:
        for scene in db.query(Scene).filter(Scene.project_id == project_id).all():
            if aspect_changed or style_changed:
                if scene.image_status == "completed":
                    scene.image_status = "outdated"
            if voice_changed and not scene.voice_id and scene.tts_status == "completed":
                scene.tts_status = "outdated"
            if aspect_changed or resolution_changed or style_changed or (voice_changed and not scene.voice_id):
                if scene.clip_status == "completed":
                    scene.clip_status = "outdated"
    if (aspect_changed or resolution_changed or style_changed or voice_changed or export_settings_changed) and project.status == "completed":
        project.status = "draft"

    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/auto-remaining", response_model=JobResponse)
def trigger_auto_remaining(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = job_manager.create_job(db, project_id, "auto_remaining", 100)
    project.active_job_id = job.id
    project.status = "generating"
    project.current_stage = "starting"
    db.commit()
    background_tasks.add_task(job_manager.run_registered, run_auto_remaining_pipeline, project_id, job.id)
    return job


@router.post("/{project_id}/batch-tts", response_model=JobResponse)
def trigger_batch_tts(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).all()
    job = job_manager.create_job(db, project_id, "batch_tts", len(scenes))
    project.active_job_id = job.id
    db.commit()
    background_tasks.add_task(job_manager.run_registered, job_manager.execute_batch_tts_generation, project_id, job.id)
    return job


@router.post("/{project_id}/batch-images", response_model=JobResponse)
def trigger_batch_images(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).all()
    job = job_manager.create_job(db, project_id, "batch_images", len(scenes))
    project.active_job_id = job.id
    db.commit()
    background_tasks.add_task(job_manager.run_registered, job_manager.execute_batch_image_generation, project_id, job.id)
    return job


@router.post("/{project_id}/batch-clips", response_model=JobResponse)
def trigger_batch_clips(project_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).all()
    job = job_manager.create_job(db, project_id, "batch_clips", len(scenes))
    project.active_job_id = job.id
    db.commit()
    background_tasks.add_task(job_manager.run_registered, job_manager.execute_batch_clip_rendering, project_id, job.id)
    return job


@router.post("/{project_id}/export")
async def export_project_video(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        final_mp4 = await render_full_project_video(db, project, burn_subtitles=True)
        return {"message": "Export completed successfully", "video_path": final_mp4}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.query(Job).filter(Job.project_id == project_id).delete()
    db.delete(project)
    db.commit()
    return {"message": f"Project {project_id} deleted."}


@router.post("/create-test", response_model=ProjectResponse)
async def create_test_project(db: Session = Depends(get_db)):
    """
    Provisions a 100% offline inspection project with local color cards,
    local WAV test audio tracks, and verbatim script breakdown without external API calls.
    """
    project_id = f"proj_test_{uuid.uuid4().hex[:6]}"
    project = Project(
        id=project_id,
        name="🧪 Тестовый проект (Офлайн)",
        topic_or_script="[Сцена 1] Запуск офлайн-проверки StoryForge AI. Кадры и звук генерируются локально без обращения к сторонним ИИ.\n\n[Сцена 2] Проверка порядка сцен, таймингов и переходов. Изображение каждой сцены имеет свой уникальный цвет.\n\n[Сцена 3] Финальная сборка видео через FFmpeg. Все сбои API полностью смоделированы и изолированы.",
        input_type="full_script",
        duration_preset="1",
        language="Russian",
        story_type="Inspection",
        visual_style="Test Cards",
        active_text_provider="mock",
        active_image_provider="mock",
        active_tts_provider="mock",
        status="draft",
        current_stage="idle",
        is_test_project=True
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # 1. Script record
    script = Script(
        project_id=project.id,
        text=project.topic_or_script,
        is_user_provided=True
    )
    db.add(script)
    db.commit()

    # 2. Local test scenes provision (3 scenes with colored cards & wav audio)
    from app.services.providers.mock_provider import MockImageProvider, MockTTSProvider
    from app.config import get_project_dir

    scenes_data = [
        ("Establishing Shot", "slow_zoom_in", "Запуск офлайн-проверки StoryForge AI. Кадры и звук генерируются локально без обращения к сторонним ИИ."),
        ("Medium Shot", "pan_left", "Проверка порядка сцен, таймингов и переходов. Изображение каждой сцены имеет свой уникальный цвет."),
        ("Close-Up", "slow_zoom_out", "Финальная сборка видео через FFmpeg. Все сбои API полностью смоделированы и изолированы.")
    ]

    img_dir = get_project_dir(project.id, "images")
    audio_dir = get_project_dir(project.id, "audio")

    mock_img = MockImageProvider()
    mock_tts = MockTTSProvider()

    for idx, (shot, motion, narration) in enumerate(scenes_data, start=1):
        sc_uuid = uuid.uuid4().hex
        img_path = str(img_dir / f"scene_{sc_uuid}.png")
        audio_path = str(audio_dir / f"scene_{sc_uuid}.wav")

        await mock_img.generate_image(
            prompt=f"Scene #{idx}: {narration}",
            aspect_ratio="16:9",
            save_path=img_path,
            scene_order=idx
        )

        await mock_tts.generate_speech(
            text=narration,
            save_path=audio_path
        )

        scene = Scene(
            scene_uuid=sc_uuid,
            project_id=project.id,
            scene_order=idx,
            narration=narration,
            shot_type=shot,
            camera_motion=motion,
            scene_type="motion",
            transition="crossfade",
            image_prompt=f"Тестовая карточка сцены #{idx}",
            duration_target=max(4.0, round(len(narration.split()) * 0.45, 1)),
            actual_duration=max(4.0, round(len(narration.split()) * 0.45, 1)),
            audio_path=audio_path,
            image_path=img_path,
            image_status="completed",
            tts_status="completed",
            clip_status="not_created"
        )
        db.add(scene)

    db.commit()
    db.refresh(project)
    return project

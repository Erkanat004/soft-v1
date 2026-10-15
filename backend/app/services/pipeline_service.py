import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Project, Scene, Job
from app.services.script_service import prepare_project_script
from app.services.scene_service import decompose_script_to_scenes
from app.services.tts_service import generate_scene_tts, sync_and_split_scenes_post_tts
from app.services.render_service import render_full_project_video
from app.services.job_queue import job_manager

logger = logging.getLogger("pipeline_service")


class PipelineCancelled(Exception):
    pass


def ensure_job_can_continue(db: Session, job_id: str):
    job = db.query(Job).populate_existing().filter(Job.id == job_id).first()
    if not job:
        raise RuntimeError(f"Job {job_id} no longer exists")
    if job.status == "cancelled":
        raise PipelineCancelled(f"Job {job_id} was cancelled")
    if job.status == "failed":
        raise RuntimeError(job.error_message or f"Job {job_id} failed")

async def run_auto_remaining_pipeline(project_id: str, job_id: str):
    """
    Executes remaining missing steps in project creation workflow without overwriting valid assets.
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        project.status = "generating"
        project.current_stage = "starting"
        db.commit()
        ensure_job_can_continue(db, job_id)

        # Step 1: Script check / generation
        job_manager.update_job_progress(db, job_id, 0, 0, 100, "script", "Checking script...")
        script, characters, locations = await prepare_project_script(db, project)
        ensure_job_can_continue(db, job_id)

        # Step 2: Scenes check / decomposition
        scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
        if not scenes:
            job_manager.update_job_progress(db, job_id, 15, 0, 100, "scenes", "Splitting script into visual scenes...")
            scenes = await decompose_script_to_scenes(db, project, script.text)
        ensure_job_can_continue(db, job_id)

        # Step 3: Batch TTS
        job_manager.update_job_progress(db, job_id, 30, 0, 100, "tts", "Generating voiceovers for scenes...")
        await job_manager.execute_batch_tts_generation(project_id, job_id, finalize_job=False)
        ensure_job_can_continue(db, job_id)

        # Step 4: Batch Images
        job_manager.update_job_progress(db, job_id, 60, 0, 100, "images", "Generating scene images in parallel...")
        await job_manager.execute_batch_image_generation(project_id, job_id, finalize_job=False)
        ensure_job_can_continue(db, job_id)

        # Step 5: Render final video
        job_manager.update_job_progress(db, job_id, 85, 0, 100, "render", "Rendering final MP4 video...")
        final_video_path = await render_full_project_video(db, project, burn_subtitles=True)
        ensure_job_can_continue(db, job_id)

        job_manager.update_job_progress(db, job_id, 100, 0, 100, "completed", "Video rendering completed successfully!")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "completed"
            job.progress_pct = 100.0
        project.status = "completed"
        project.current_stage = "completed"
        project.active_job_id = None
        db.commit()
        logger.info(f"Auto remaining pipeline completed for project {project_id}: {final_video_path}")

    except PipelineCancelled:
        db.rollback()
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "draft"
            project.current_stage = "cancelled"
            if project.active_job_id == job_id:
                project.active_job_id = None
            db.commit()
        logger.info(f"Auto pipeline cancelled for project {project_id}")
    except Exception as e:
        logger.error(f"Auto pipeline failed for project {project_id}: {e}")
        db.rollback()
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "failed"
            project.error_message = str(e)
            project.current_stage = "failed"
            if project.active_job_id == job_id:
                project.active_job_id = None
            db.commit()
        
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status != 'cancelled':
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()

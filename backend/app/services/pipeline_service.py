import asyncio
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

async def run_auto_pipeline(project_id: str, job_id: str):
    """
    Executes the complete 13-step 100% automated video generation pipeline.
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return

        project.status = "generating"
        project.current_stage = "starting"
        db.commit()

        # Step 1-3: Script Generation + Character & Location Bibles
        job_manager.update_job_progress(db, job_id, 0, 0, 100, "script", "Generating story script and analyzing Bibles...")
        script, characters, locations = await prepare_project_script(db, project)
        project.current_stage = "bibles_ready"
        db.commit()

        # Step 4-5: Scene Splitting & Image Prompt Generation with Shot Rotation
        job_manager.update_job_progress(db, job_id, 15, 0, 100, "scenes", "Splitting script into visual scenes and prompts...")
        scenes = await decompose_script_to_scenes(db, project, script.text)
        project.current_stage = "scenes_ready"
        db.commit()

        # Step 6-7: TTS Generation per Scene & FFprobe Audio Duration Probing
        job_manager.update_job_progress(db, job_id, 30, 0, 100, "tts", "Generating TTS voiceover audio per scene...")
        for sc in scenes:
            await generate_scene_tts(db, project, sc)

        # Step 8: Post-TTS Duration Sync & Sub-Scene Splitter (Target 10-20s visual duration)
        job_manager.update_job_progress(db, job_id, 45, 0, 100, "duration_sync", "Probing audio durations via FFprobe and syncing visual scenes...")
        scenes = sync_and_split_scenes_post_tts(db, project)
        project.current_stage = "tts_ready"
        db.commit()

        # Step 9: Batch Concurrent Image Generation with 3x Retry & Resume Checkpoint
        job_manager.update_job_progress(db, job_id, 55, 0, 100, "images", "Generating scene images in parallel queue...")
        await job_manager.execute_batch_image_generation(project_id, job_id)

        # Refresh project & scenes state
        project = db.query(Project).filter(Project.id == project_id).first()
        project.current_stage = "images_ready"
        db.commit()

        # Step 10-13: FFmpeg Ken Burns Motion + Transitions + Music + Subtitles + MP4 Render
        job_manager.update_job_progress(db, job_id, 85, 0, 100, "render", "Rendering final MP4 video via local FFmpeg...")
        final_video_path = await render_full_project_video(db, project, burn_subtitles=True)

        job_manager.update_job_progress(db, job_id, 100, 0, 100, "completed", "Video rendering completed successfully!")
        project.status = "completed"
        project.current_stage = "completed"
        db.commit()
        logger.info(f"Auto pipeline completed successfully for project {project_id}: {final_video_path}")

    except Exception as e:
        logger.error(f"Auto pipeline failed for project {project_id}: {e}")
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = "failed"
            project.error_message = str(e)
            project.current_stage = "failed"
            db.commit()
        
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()

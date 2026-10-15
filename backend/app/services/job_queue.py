import os
import asyncio
import logging
import uuid
from typing import Dict
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Job, Scene, Project, ImageVariation, utc_now
from app.config import MAX_CONCURRENT_IMAGE_JOBS, DEFAULT_RETRY_COUNT, get_project_dir
from app.services.providers.factory import get_image_provider
from app.services.errors import OperationConflict, ProviderError

logger = logging.getLogger("job_queue")

def recover_interrupted_jobs_on_startup(db: Session):
    """
    Scans database for jobs that were running or pending when server was stopped/restarted,
    and marks them as interrupted.
    """
    interrupted_jobs = db.query(Job).filter(Job.status.in_(["pending", "running"])).all()
    for job in interrupted_jobs:
        job.status = "interrupted"
        job.interrupted = True
        job.error_message = "Job was interrupted due to application restart"
        job.updated_at = utc_now()
        project = db.query(Project).filter(Project.id == job.project_id).first()
        for scene in db.query(Scene).filter(Scene.project_id == job.project_id).all():
            for field in ('image_status', 'tts_status', 'clip_status'):
                if getattr(scene, field) in ('running', 'queued'):
                    setattr(scene, field, 'error')
                    scene.error_message = 'Обработка прервана перезапуском сервера. Повторите операцию.'
        if project and project.active_job_id == job.id:
            project.active_job_id = None
            project.status = "draft"
            project.current_stage = "interrupted"
    if interrupted_jobs:
        logger.info(f"Recovered {len(interrupted_jobs)} interrupted jobs on startup.")
        db.commit()


class JobManager:
    def __init__(self):
        self.active_jobs: Dict[str, asyncio.Task] = {}

    async def run_registered(self, runner, project_id: str, job_id: str):
        """Keep cancellation attached to the actual worker, not the HTTP task."""
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job or job.status not in ('pending', 'running'):
                return
        task = asyncio.create_task(runner(project_id, job_id))
        self.active_jobs[job_id] = task
        try:
            await task
        except asyncio.CancelledError:
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job and job.status in ('pending', 'running'):
                    job.status = 'cancelled'
                    job.cancelled_at = utc_now()
                project = db.get(Project, project_id)
                if project and project.active_job_id == job_id:
                    project.active_job_id = None
                    project.status = 'draft'
                    project.current_stage = 'cancelled'
                for scene in db.query(Scene).filter(Scene.project_id == project_id).all():
                    for field in ('image_status', 'tts_status', 'clip_status'):
                        if getattr(scene, field) in ('running', 'queued'):
                            setattr(scene, field, 'cancelled')
                db.commit()
        except Exception as exc:
            logger.error("Background worker failed (%s)", type(exc).__name__)
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job and job.status in ('pending', 'running'):
                    job.status = 'failed'
                    job.error_message = 'Обработка не завершена. Проверьте настройки и повторите запуск.'
                self._clear_active_project_job(db, project_id, job_id)
                db.commit()
        finally:
            if self.active_jobs.get(job_id) is task:
                self.active_jobs.pop(job_id, None)

    def create_job(self, db: Session, project_id: str, job_type: str, total_tasks: int, scene_id: int = None) -> Job:
        if db.query(Job.id).filter(Job.project_id == project_id, Job.status.in_(['pending', 'running'])).first():
            raise OperationConflict('Project already has an active job')
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = Job(
            id=job_id,
            project_id=project_id,
            scene_id=scene_id,
            job_type=job_type,
            total_tasks=total_tasks,
            completed_tasks=0,
            failed_tasks=0,
            status="pending",
            progress_pct=0.0,
            checkpoint_stage="idle",
            interrupted=False
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def cancel_job(self, db: Session, job_id: str) -> bool:
        """Cancels a running job and marks it cancelled in DB."""
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status in ('pending', 'running'):
            job.status = "cancelled"
            job.cancelled_at = utc_now()
            project = db.query(Project).filter(Project.id == job.project_id).first()
            if project and project.active_job_id == job_id:
                project.active_job_id = None
                project.status = "draft"
                project.current_stage = "cancelled"
            db.commit()

        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            task.get_loop().call_soon_threadsafe(task.cancel)
            logger.info(f"Task for job {job_id} cancelled successfully.")
        return job is not None

    def _clear_active_project_job(self, db: Session, project_id: str, job_id: str):
        project = db.query(Project).filter(Project.id == project_id).first()
        if project and project.active_job_id == job_id:
            project.active_job_id = None

    def update_job_progress(
        self,
        db: Session,
        job_id: str,
        completed: int,
        failed: int,
        total: int,
        stage: str,
        description: str = "",
        error_msg: str = "",
        progress_override: float | None = None,
    ):
        job = db.query(Job).populate_existing().filter(Job.id == job_id).first()
        if not job:
            return
        if job.status not in ('pending', 'running'):
            return
        job.status = "running"
        job.completed_tasks = completed
        job.failed_tasks = failed
        job.total_tasks = total
        calculated = (completed / max(total, 1)) * 100.0
        job.progress_pct = round(progress_override if progress_override is not None else calculated, 1)
        job.checkpoint_stage = stage
        job.current_step_description = description
        if error_msg:
            job.error_message = error_msg
        job.updated_at = utc_now()
        db.commit()

    async def execute_batch_image_generation(self, project_id: str, job_id: str, finalize_job: bool = True):
        """
        Runs batch image generation queue with max 3 concurrent requests, 3x retry resilience, and per-scene status tracking.
        """
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return

            scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
            total_scenes = len(scenes)

            img_provider = get_image_provider(db, project.active_image_provider or "gemini_image")
            img_dir = get_project_dir(project_id, "images")

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMAGE_JOBS)
            completed_count = 0
            failed_count = 0

            # Count scenes already completed
            for sc in scenes:
                if sc.image_status == "completed" and sc.image_path and os.path.isfile(sc.image_path):
                    completed_count += 1

            self.update_job_progress(
                db, job_id, completed_count, failed_count, total_scenes,
                stage="images", description=f"Image generation progress: {completed_count}/{total_scenes}",
                progress_override=(60 + 25 * completed_count / max(total_scenes, 1)) if not finalize_job else None,
            )

            async def generate_single_scene(scene: Scene):
                nonlocal completed_count, failed_count

                # Check if job was cancelled
                job_check = db.query(Job).populate_existing().filter(Job.id == job_id).first()
                if not job_check or job_check.status == "cancelled":
                    return

                # Skip if already completed and not outdated/error
                if scene.image_status == "completed" and scene.image_path and os.path.isfile(scene.image_path):
                    return

                img_path = str(img_dir / f"scene_{scene.scene_uuid}_{uuid.uuid4().hex}.png")
                tmp_path = str(img_dir / f"scene_{scene.scene_uuid}.tmp.png")

                async with semaphore:
                    success = False
                    last_error = ""

                    # Prompt building: prompt + global project visual style
                    if project.active_image_provider == "local_cards":
                        prompt = f"Scene #{scene.scene_order}: {scene.narration}"
                    else:
                        prompt = scene.enhanced_prompt or scene.image_prompt or scene.narration
                        if project.global_visual_style:
                            prompt = f"{prompt}, {project.global_visual_style}"

                    for attempt in range(1, DEFAULT_RETRY_COUNT + 1):
                        try:
                            logger.info(f"Generating image for scene {scene.scene_uuid} (Attempt {attempt})")
                            res_path = await img_provider.generate_image(
                                prompt=prompt,
                                aspect_ratio=project.aspect_ratio or "16:9",
                                save_path=tmp_path
                            )
                            if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
                                os.replace(tmp_path, img_path)
                                res_path = img_path
                            else:
                                raise RuntimeError('Image provider did not create a non-empty output file')

                            success = True
                            break
                        except Exception as e:
                            last_error = str(e)
                            logger.warning(f"Scene {scene.scene_uuid} image gen failed (attempt {attempt}): {e}")
                            if os.path.isfile(tmp_path):
                                os.remove(tmp_path)
                            if isinstance(e, ProviderError):
                                break
                            if attempt < DEFAULT_RETRY_COUNT:
                                await asyncio.sleep(attempt * 1.5)

                    with SessionLocal() as db_inner:
                        s_ref = db_inner.query(Scene).filter(Scene.id == scene.id).first()
                        if success:
                            if s_ref:
                                s_ref.image_path = img_path
                                s_ref.image_status = "completed"
                                s_ref.image_prompt_needs_review = False
                                s_ref.error_message = None
                                if s_ref.clip_status == "completed":
                                    s_ref.clip_status = "outdated"

                                # Add ImageVariation entry
                                variation = ImageVariation(
                                    scene_uuid=s_ref.scene_uuid,
                                    project_id=s_ref.project_id,
                                    image_path=img_path,
                                    prompt_used=prompt,
                                    is_active=True
                                )
                                db_inner.query(ImageVariation).filter(
                                    ImageVariation.scene_uuid == s_ref.scene_uuid,
                                    ImageVariation.is_active.is_(True),
                                ).update({ImageVariation.is_active: False}, synchronize_session=False)
                                db_inner.add(variation)
                            completed_count += 1
                        else:
                            if s_ref:
                                s_ref.image_status = "error"
                                s_ref.error_message = f"Image generation failed: {last_error}"
                            failed_count += 1

                        db_inner.commit()

                    self.update_job_progress(
                        db, job_id, completed_count, failed_count, total_scenes,
                        stage="images", description=f"Generating images: {completed_count}/{total_scenes}",
                        progress_override=(60 + 25 * (completed_count + failed_count) / max(total_scenes, 1)) if not finalize_job else None,
                    )

            target_scenes = [
                sc for sc in scenes
                if not (sc.image_status == "completed" and sc.image_path and os.path.isfile(sc.image_path))
            ]
            if target_scenes:
                results = await asyncio.gather(*[generate_single_scene(sc) for sc in target_scenes], return_exceptions=True)
                errors = [r for r in results if isinstance(r, BaseException)]
                if errors:
                    raise RuntimeError(f'Image worker failed for {len(errors)} scene(s)')

            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "cancelled":
                if failed_count:
                    job.status = "failed"
                    job.error_message = f"Image generation failed for {failed_count} scene(s)"
                elif finalize_job:
                    job.status = "completed"
                    job.progress_pct = 100.0
                job.checkpoint_stage = "images_ready"
                if finalize_job:
                    self._clear_active_project_job(db, project_id, job_id)
                db.commit()
            if failed_count and not finalize_job:
                raise RuntimeError(f"Image generation failed for {failed_count} scene(s)")

        except Exception as e:
            logger.error(f"Batch image generation job failed: {e}")
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "cancelled":
                job.status = "failed"
                job.error_message = str(e)
                if finalize_job:
                    self._clear_active_project_job(db, project_id, job_id)
                db.commit()
            if not finalize_job:
                raise
        finally:
            db.close()

    async def execute_batch_tts_generation(self, project_id: str, job_id: str, finalize_job: bool = True):
        """
        Runs batch TTS voiceover generation queue.
        """
        from app.services.tts_service import generate_scene_tts, sync_and_split_scenes_post_tts
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return

            scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
            total = len(scenes)
            completed = 0
            failed = 0

            for idx, sc in enumerate(scenes, start=1):
                job_check = db.query(Job).populate_existing().filter(Job.id == job_id).first()
                if not job_check or job_check.status == "cancelled":
                    return

                if sc.tts_status == "completed" and sc.audio_path and os.path.isfile(sc.audio_path):
                    completed += 1
                    continue

                try:
                    await generate_scene_tts(db, project, sc)
                    completed += 1
                except Exception as e:
                    db.rollback()
                    logger.error("TTS scene generation failed: %s", type(e).__name__)
                    failed += 1

                self.update_job_progress(
                    db, job_id, completed, failed, total,
                    stage="tts", description=f"Generating voiceover: {completed}/{total}",
                    progress_override=(30 + 30 * (completed + failed) / max(total, 1)) if not finalize_job else None,
                )

            # Post-TTS sync & visual scene splitting
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                sync_and_split_scenes_post_tts(db, project)

            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "cancelled":
                if failed:
                    job.status = "failed"
                    job.error_message = f"TTS generation failed for {failed} scene(s)"
                elif finalize_job:
                    job.status = "completed"
                    job.progress_pct = 100.0
                job.checkpoint_stage = "tts_ready"
                if finalize_job:
                    self._clear_active_project_job(db, project_id, job_id)
                db.commit()
            if failed and not finalize_job:
                raise RuntimeError(f"TTS generation failed for {failed} scene(s)")

        except Exception as e:
            logger.error(f"Batch TTS job failed: {e}")
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "cancelled":
                job.status = "failed"
                job.error_message = str(e)
                if finalize_job:
                    self._clear_active_project_job(db, project_id, job_id)
                db.commit()
            if not finalize_job:
                raise
        finally:
            db.close()

    async def execute_batch_clip_rendering(self, project_id: str, job_id: str, finalize_job: bool = True):
        """
        Runs batch rendering of scene motion/video clips.
        """
        from app.services.motion_service import render_single_scene_clip
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return

            scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
            total = len(scenes)
            completed = 0
            failed = 0

            for sc in scenes:
                job_check = db.query(Job).populate_existing().filter(Job.id == job_id).first()
                if not job_check or job_check.status == "cancelled":
                    return

                if sc.clip_status == "completed" and sc.video_clip_path and os.path.isfile(sc.video_clip_path):
                    completed += 1
                    continue

                try:
                    await render_single_scene_clip(db, project, sc)
                    completed += 1
                except Exception as e:
                    db.rollback()
                    logger.error("Clip rendering failed: %s", type(e).__name__)
                    failed += 1

                self.update_job_progress(
                    db, job_id, completed, failed, total,
                    stage="clips", description=f"Rendering clips: {completed}/{total}"
                )

            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "cancelled":
                if failed:
                    job.status = "failed"
                    job.error_message = f"Clip rendering failed for {failed} scene(s)"
                elif finalize_job:
                    job.status = "completed"
                    job.progress_pct = 100.0
                job.checkpoint_stage = "clips_ready"
                if finalize_job:
                    self._clear_active_project_job(db, project_id, job_id)
                db.commit()
            if failed and not finalize_job:
                raise RuntimeError(f"Clip rendering failed for {failed} scene(s)")

        except Exception as e:
            logger.error(f"Batch clip rendering job failed: {e}")
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status != "cancelled":
                job.status = "failed"
                job.error_message = str(e)
                if finalize_job:
                    self._clear_active_project_job(db, project_id, job_id)
                db.commit()
            if not finalize_job:
                raise
        finally:
            db.close()


job_manager = JobManager()

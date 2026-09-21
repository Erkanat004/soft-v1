import os
import asyncio
import logging
import uuid
import datetime
from typing import Dict, Any, Callable, Awaitable, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Job, Scene, Project
from app.config import MAX_CONCURRENT_IMAGE_JOBS, DEFAULT_RETRY_COUNT
from app.services.providers.factory import get_image_provider

logger = logging.getLogger("job_queue")

class JobManager:
    def __init__(self):
        self.active_jobs: Dict[str, asyncio.Task] = {}

    def create_job(self, db: Session, project_id: str, job_type: str, total_tasks: int) -> Job:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job = Job(
            id=job_id,
            project_id=project_id,
            job_type=job_type,
            total_tasks=total_tasks,
            completed_tasks=0,
            failed_tasks=0,
            status="pending",
            progress_pct=0.0,
            checkpoint_stage="idle"
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def update_job_progress(
        self,
        db: Session,
        job_id: str,
        completed: int,
        failed: int,
        total: int,
        stage: str,
        description: str = "",
        error_msg: str = ""
    ):
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        job.completed_tasks = completed
        job.failed_tasks = failed
        job.total_tasks = total
        job.progress_pct = round((completed / max(total, 1)) * 100.0, 1)
        job.checkpoint_stage = stage
        job.current_step_description = description
        if error_msg:
            job.error_message = error_msg
        job.updated_at = datetime.datetime.utcnow()
        db.commit()

    async def execute_batch_image_generation(self, project_id: str, job_id: str):
        """
        Runs image generation queue with max 3 concurrent requests, 3x retry resilience, and checkpoint resumption.
        """
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return

            scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
            total_scenes = len(scenes)

            img_provider = get_image_provider(db, project.active_image_provider)
            img_dir = os.path.join("projects", project_id, "images")
            os.makedirs(img_dir, exist_ok=True)

            semaphore = asyncio.Semaphore(MAX_CONCURRENT_IMAGE_JOBS)
            completed_count = 0
            failed_count = 0

            # Count existing cached images for resumption
            for sc in scenes:
                img_path = os.path.join(img_dir, f"scene_{sc.scene_order:03d}.png")
                if os.path.isfile(img_path) and os.path.getsize(img_path) > 0:
                    sc.image_path = img_path
                    sc.status = "image_done"
                    completed_count += 1
            db.commit()

            self.update_job_progress(
                db, job_id, completed_count, failed_count, total_scenes,
                stage="images", description=f"Resumed image generation: {completed_count}/{total_scenes} ready"
            )

            async def generate_single_scene_image(scene: Scene):
                nonlocal completed_count, failed_count
                
                img_path = os.path.join(img_dir, f"scene_{scene.scene_order:03d}.png")
                
                # Cache Checkpoint check
                if os.path.isfile(img_path) and os.path.getsize(img_path) > 0 and scene.status == "image_done":
                    return

                async with semaphore:
                    success = False
                    last_error = ""
                    
                    # 3x Retry loop with exponential backoff
                    for attempt in range(1, DEFAULT_RETRY_COUNT + 1):
                        try:
                            logger.info(f"Generating image for scene {scene.scene_order} (Attempt {attempt})")
                            prompt = scene.enhanced_prompt or scene.image_prompt or scene.narration
                            res_path = await img_provider.generate_image(
                                prompt=prompt,
                                aspect_ratio=project.aspect_ratio,
                                save_path=img_path
                            )
                            scene.image_path = res_path
                            scene.status = "image_done"
                            success = True
                            break
                        except Exception as e:
                            last_error = str(e)
                            logger.warning(f"Scene {scene.scene_order} image gen failed (attempt {attempt}): {e}")
                            await asyncio.sleep(attempt * 2)

                    db_inner = SessionLocal()
                    s_ref = db_inner.query(Scene).filter(Scene.id == scene.id).first()
                    if success:
                        if s_ref:
                            s_ref.image_path = img_path
                            s_ref.status = "image_done"
                        completed_count += 1
                    else:
                        if s_ref:
                            s_ref.status = "failed"
                        failed_count += 1

                    db_inner.commit()
                    db_inner.close()

                    self.update_job_progress(
                        db, job_id, completed_count, failed_count, total_scenes,
                        stage="images", description=f"Generating images: {completed_count}/{total_scenes}"
                    )

            # Gather tasks
            tasks = [generate_single_scene_image(sc) for sc in scenes if sc.status != "image_done"]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "completed"
                job.progress_pct = 100.0
                job.checkpoint_stage = "images_ready"
                db.commit()

        except Exception as e:
            logger.error(f"Batch image generation job failed: {e}")
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                db.commit()
        finally:
            db.close()

job_manager = JobManager()

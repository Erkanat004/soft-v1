from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Job, Project
from app.schemas import JobResponse
from app.services.job_queue import job_manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/{job_id}/retry_failed", response_model=JobResponse)
def retry_failed_tasks(job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    runners = {
        "generate_images": job_manager.execute_batch_image_generation,
        "batch_images": job_manager.execute_batch_image_generation,
        "batch_tts": job_manager.execute_batch_tts_generation,
        "batch_clips": job_manager.execute_batch_clip_rendering,
    }
    runner = runners.get(job.job_type)
    if not runner:
        raise HTTPException(status_code=400, detail=f"Job type {job.job_type} cannot be retried")
    if job.status not in ('failed', 'cancelled', 'interrupted'):
        raise HTTPException(status_code=409, detail="Only stopped or failed jobs can be retried")
    if db.query(Job.id).filter(Job.project_id == job.project_id, Job.status.in_(['pending', 'running'])).first():
        raise HTTPException(status_code=409, detail="Project already has an active job")
    if not db.get(Project, job.project_id):
        raise HTTPException(status_code=404, detail="Project not found")

    job.status = "pending"
    job.failed_tasks = 0
    job.error_message = None
    job.cancelled_at = None
    project = db.query(Project).filter(Project.id == job.project_id).first()
    if project:
        project.active_job_id = job.id
    db.commit()

    background_tasks.add_task(job_manager.run_registered, runner, job.project_id, job.id)

    return job

@router.post("/{job_id}/cancel")
def cancel_job_endpoint(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    success = job_manager.cancel_job(db, job_id)
    return {"message": f"Job {job_id} cancelled successfully", "success": success}

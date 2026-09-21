from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Job
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
    
    job.status = "running"
    job.failed_tasks = 0
    db.commit()

    if job.job_type == "generate_images":
        background_tasks.add_task(job_manager.execute_batch_image_generation, job.project_id, job.id)

    return job

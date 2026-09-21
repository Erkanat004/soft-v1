import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project
from app.services.render_service import render_full_project_video

router = APIRouter(prefix="/api/projects/{project_id}/render", tags=["render"])

@router.post("")
async def start_render(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    output_file = await render_full_project_video(db, project)
    return {"status": "success", "output_path": output_file}

@router.get("/output.mp4")
def download_final_video(project_id: str, db: Session = Depends(get_db)):
    mp4_path = os.path.join("projects", project_id, "output", "final.mp4")
    if not os.path.isfile(mp4_path):
        raise HTTPException(status_code=404, detail="Rendered video not found")
    return FileResponse(mp4_path, media_type="video/mp4", filename=f"storyforge_{project_id}.mp4")

import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project
from app.config import get_project_dir
from app.services.render_service import get_render_status, render_full_project_video

router = APIRouter(prefix="/api/projects/{project_id}/render", tags=["render"])

@router.get("/status")
def render_status(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return get_render_status(db, project)

from typing import Optional
from pydantic import BaseModel

class RenderRequest(BaseModel):
    burn_subtitles: bool = True
    enable_audio_ducking: bool = True
    music_volume: Optional[float] = None

@router.post("")
async def start_render(project_id: str, payload: Optional[RenderRequest] = None, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    burn_subs = payload.burn_subtitles if payload is not None else True
    ducking = payload.enable_audio_ducking if payload is not None else True
    vol = payload.music_volume if payload is not None else None

    output_file = await render_full_project_video(
        db, project,
        music_volume=vol,
        burn_subtitles=burn_subs,
        enable_audio_ducking=ducking
    )
    return {"status": "success", "output_path": output_file}

@router.get("/output.mp4")
def download_final_video(project_id: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    mp4_path = get_project_dir(project_id, "output") / "final.mp4"
    if not os.path.isfile(mp4_path):
        raise HTTPException(status_code=404, detail="Rendered video not found")
    return FileResponse(mp4_path, media_type="video/mp4", filename=f"storyforge_{project_id}.mp4")

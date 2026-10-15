"""YouTube metadata pack router for publishing packages."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.services.youtube_service import generate_youtube_pack

router = APIRouter(prefix="/api/projects/{project_id}/youtube-pack", tags=["youtube"])


@router.get("")
async def get_youtube_pack(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    pack = await generate_youtube_pack(db, project, allow_ai=False)
    return pack


@router.post("")
async def generate_ai_youtube_pack(project_id: str, db: Session = Depends(get_db)):
    """Explicit opt-in: this action may spend the buyer's API quota."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await generate_youtube_pack(db, project, allow_ai=True)


@router.get("/download")
async def download_youtube_pack_text(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    pack = await generate_youtube_pack(db, project, allow_ai=False)
    filename = f"youtube_pack_{project.id}.txt"
    return PlainTextResponse(
        content=pack["formatted_text"],
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

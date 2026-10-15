import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, Scene
from app.schemas import SceneResponse, SceneUpdate
from app.services.providers.factory import get_image_provider
from app.services.tts_service import generate_scene_tts

router = APIRouter(prefix="/api/projects/{project_id}/scenes", tags=["scenes"])

@router.patch("/{scene_id}", response_model=SceneResponse)
def update_scene(project_id: str, scene_id: int, payload: SceneUpdate, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    from app.services.scene_service import update_scene_fields
    return update_scene_fields(db, scene.scene_uuid, payload.model_dump(exclude_unset=True))

@router.post("/{scene_id}/regenerate_image", response_model=SceneResponse)
async def regenerate_scene_image(project_id: str, scene_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not project or not scene:
        raise HTTPException(status_code=404, detail="Project or scene not found")

    from app.routers.scenes import generate_single_scene_image
    return await generate_single_scene_image(scene.scene_uuid, db)

@router.post("/{scene_id}/regenerate_tts", response_model=SceneResponse)
async def regenerate_scene_tts(project_id: str, scene_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not project or not scene:
        raise HTTPException(status_code=404, detail="Project or scene not found")

    # Force pending status to bypass cache check
    scene.status = "pending"
    db.commit()

    await generate_scene_tts(db, project, scene)
    db.refresh(scene)
    return scene

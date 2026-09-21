import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, Scene
from app.schemas import SceneResponse, SceneUpdate
from app.services.providers.factory import get_image_provider, get_tts_provider
from app.services.tts_service import generate_scene_tts

router = APIRouter(prefix="/api/projects/{project_id}/scenes", tags=["scenes"])

@router.get("", response_model=List[SceneResponse])
def list_scenes(project_id: str, db: Session = Depends(get_db)):
    return db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()

@router.patch("/{scene_id}", response_model=SceneResponse)
def update_scene(project_id: str, scene_id: int, payload: SceneUpdate, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(scene, key, value)

    db.commit()
    db.refresh(scene)
    return scene

@router.post("/{scene_id}/regenerate_image", response_model=SceneResponse)
async def regenerate_scene_image(project_id: str, scene_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not project or not scene:
        raise HTTPException(status_code=404, detail="Project or scene not found")

    img_provider = get_image_provider(db, project.active_image_provider)
    img_dir = os.path.join("projects", project_id, "images")
    os.makedirs(img_dir, exist_ok=True)
    img_path = os.path.join(img_dir, f"scene_{scene.scene_order:03d}.png")

    prompt = scene.enhanced_prompt or scene.image_prompt or scene.narration
    res_path = await img_provider.generate_image(prompt, aspect_ratio=project.aspect_ratio, save_path=img_path)
    
    scene.image_path = res_path
    scene.status = "image_done"
    db.commit()
    db.refresh(scene)
    return scene

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

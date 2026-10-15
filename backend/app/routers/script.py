from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, Script
from app.schemas import ScriptResponse, ScriptCreate, SceneResponse
from app.services.providers.factory import get_text_provider

router = APIRouter(prefix="/api/projects/{project_id}/script", tags=["script"])

@router.get("", response_model=ScriptResponse | None)
def get_script(project_id: str, db: Session = Depends(get_db)):
    if not db.query(Project.id).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    script = db.query(Script).filter(Script.project_id == project_id).first()
    return script

@router.put("", response_model=ScriptResponse)
def update_script(project_id: str, payload: ScriptCreate, db: Session = Depends(get_db)):
    if not db.query(Project.id).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    script = db.query(Script).filter(Script.project_id == project_id).first()
    if not script:
        script = Script(project_id=project_id, text=payload.text, is_user_provided=True)
        db.add(script)
    else:
        script.text = payload.text
        script.is_user_provided = True
    db.commit()
    db.refresh(script)
    return script

@router.post("/enhance", response_model=ScriptResponse)
async def enhance_script_text(project_id: str, instruction: str = "Make scarier", db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    script = db.query(Script).filter(Script.project_id == project_id).first()
    if not project or not script:
        raise HTTPException(status_code=404, detail="Project or script not found")

    provider = get_text_provider(db, project.active_text_provider)
    prompt = f"Refine the following story script according to this instruction: '{instruction}'. Maintain full narrative flow.\n\nSCRIPT:\n{script.text}"
    
    draft = ScriptResponse.model_validate(script)
    draft.text = await provider.generate_text(prompt)
    return draft

@router.post("/decompose", response_model=List[SceneResponse])
async def decompose_script(project_id: str, db: Session = Depends(get_db)):
    """
    Decomposes project script into visual scenes with verbatim narration preservation.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    script = db.query(Script).filter(Script.project_id == project_id).first()
    if not script or not script.text.strip():
        script_text = project.topic_or_script
    else:
        script_text = script.text
    if not script_text.strip():
        raise HTTPException(status_code=422, detail="Добавьте текст сценария перед разбивкой на сцены")

    from app.services.scene_service import decompose_script_to_scenes
    scenes = await decompose_script_to_scenes(db, project, script_text)
    return scenes

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Project, Script
from app.schemas import ScriptResponse, ScriptCreate
from app.services.providers.factory import get_text_provider

router = APIRouter(prefix="/api/projects/{project_id}/script", tags=["script"])

@router.get("", response_model=ScriptResponse)
def get_script(project_id: str, db: Session = Depends(get_db)):
    script = db.query(Script).filter(Script.project_id == project_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found for this project")
    return script

@router.put("", response_model=ScriptResponse)
def update_script(project_id: str, payload: ScriptCreate, db: Session = Depends(get_db)):
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
    
    new_text = await provider.generate_text(prompt)
    script.text = new_text
    db.commit()
    db.refresh(script)
    return script

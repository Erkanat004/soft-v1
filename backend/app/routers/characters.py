from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Character
from app.schemas import CharacterResponse, CharacterCreate

router = APIRouter(prefix="/api/projects/{project_id}/characters", tags=["characters"])

@router.get("", response_model=List[CharacterResponse])
def list_characters(project_id: str, db: Session = Depends(get_db)):
    return db.query(Character).filter(Character.project_id == project_id).all()

@router.post("", response_model=CharacterResponse)
def create_character(project_id: str, payload: CharacterCreate, db: Session = Depends(get_db)):
    char = Character(
        project_id=project_id,
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        hair=payload.hair,
        eyes=payload.eyes,
        clothes=payload.clothes,
        appearance=payload.appearance,
        is_auto_generated=False
    )
    db.add(char)
    db.commit()
    db.refresh(char)
    return char

@router.delete("/{character_id}")
def delete_character(project_id: str, character_id: int, db: Session = Depends(get_db)):
    char = db.query(Character).filter(Character.id == character_id, Character.project_id == project_id).first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    db.delete(char)
    db.commit()
    return {"message": "Character deleted"}

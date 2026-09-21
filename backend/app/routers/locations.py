from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Location
from app.schemas import LocationResponse, LocationCreate

router = APIRouter(prefix="/api/projects/{project_id}/locations", tags=["locations"])

@router.get("", response_model=List[LocationResponse])
def list_locations(project_id: str, db: Session = Depends(get_db)):
    return db.query(Location).filter(Location.project_id == project_id).all()

@router.post("", response_model=LocationResponse)
def create_location(project_id: str, payload: LocationCreate, db: Session = Depends(get_db)):
    loc = Location(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        is_auto_generated=False
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc

@router.delete("/{location_id}")
def delete_location(project_id: str, location_id: int, db: Session = Depends(get_db)):
    loc = db.query(Location).filter(Location.id == location_id, Location.project_id == project_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    db.delete(loc)
    db.commit()
    return {"message": "Location deleted"}

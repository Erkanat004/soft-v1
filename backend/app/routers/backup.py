"""Download a complete local library snapshot without API credentials."""
from datetime import datetime, UTC
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.services.backup_service import create_library_archive

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.post("/export")
def export_library():
    try:
        archive = create_library_archive()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    name = f"storyforge-backup-{datetime.now(UTC):%Y%m%d-%H%M%S}.zip"
    return FileResponse(archive, filename=name, media_type="application/zip",
                        background=BackgroundTask(archive.unlink, missing_ok=True))

"""Local-only reference and user-supplied niche research endpoints."""
import tempfile
import subprocess
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.research_service import analyze_niche, inspect_reference_video

router = APIRouter(prefix="/api/research", tags=["research"])
MAX_VIDEO_BYTES = 250 * 1024 * 1024
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm"}


class NicheVideo(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    views: int = Field(ge=0)
    age_days: float = Field(gt=0)


class NicheRequest(BaseModel):
    videos: list[NicheVideo] = Field(min_length=1, max_length=50)


@router.post("/niche")
def research_niche(payload: NicheRequest):
    return analyze_niche([item.model_dump() for item in payload.videos])


@router.post("/reference-video")
async def research_reference_video(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(status_code=422, detail="Допустимы MP4, MOV, MKV и WebM.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="storyforge_reference_", suffix=suffix, delete=False) as target:
            temp_path = Path(target.name)
            total = 0
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise HTTPException(status_code=413, detail="Видео должно быть меньше 250 МБ.")
                target.write(chunk)
        if total == 0:
            raise HTTPException(status_code=422, detail="Файл пустой.")
        try:
            return await inspect_reference_video(temp_path)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (OSError, TimeoutError, subprocess.TimeoutExpired):
            raise HTTPException(status_code=503, detail="Локальный анализ видео не завершился. Проверьте FFmpeg и попробуйте короткий файл.") from None
    finally:
        await file.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

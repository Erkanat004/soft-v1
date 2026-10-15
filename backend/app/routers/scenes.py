import os
import io
import re
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from app.services.errors import ProviderError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project, Scene, ImageVariation
from app.config import get_project_dir
from app.services.scene_service import (
    update_scene_fields,
    split_scene_by_uuid,
    merge_scenes_by_uuids,
    reorder_scenes_by_uuids
)
from app.services.tts_service import generate_scene_tts, probe_audio_duration
from app.services.motion_service import render_single_scene_clip
from app.services.providers.factory import get_image_provider

router = APIRouter(prefix="/api", tags=["scenes"])
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_AUDIO_BYTES = 50 * 1024 * 1024


def read_upload(file: UploadFile, limit: int) -> bytes:
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail="Загруженный файл слишком большой.")
    if not content:
        raise HTTPException(status_code=422, detail="Загруженный файл пустой.")
    return content


class SceneUpdateSchema(BaseModel):
    narration: Optional[str] = None
    image_prompt: Optional[str] = None
    enhanced_prompt: Optional[str] = None
    shot_type: Optional[str] = None
    camera_motion: Optional[str] = None
    voice_id: Optional[str] = None
    duration_target: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    scene_type: Optional[str] = None


class SplitSceneSchema(BaseModel):
    split_index: Optional[int] = None
    split_text: Optional[str] = None


class MergeScenesSchema(BaseModel):
    first_scene_uuid: str
    second_scene_uuid: str


class ReorderScenesSchema(BaseModel):
    scene_uuids: List[str]


class AddSceneSchema(BaseModel):
    narration: str
    image_prompt: Optional[str] = None
    insert_after_uuid: Optional[str] = None


@router.get("/projects/{project_id}/scenes")
def get_project_scenes(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    return scenes


@router.post("/projects/{project_id}/scenes")
def create_scene(project_id: str, data: AddSceneSchema, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    import uuid
    new_uuid = str(uuid.uuid4())
    
    existing_scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    
    insert_order = len(existing_scenes) + 1
    if data.insert_after_uuid:
        for idx, sc in enumerate(existing_scenes):
            if sc.scene_uuid == data.insert_after_uuid:
                insert_order = sc.scene_order + 1
                break
        
        # Shift subsequent scenes
        for sc in existing_scenes:
            if sc.scene_order >= insert_order:
                sc.scene_order += 1

    new_scene = Scene(
        project_id=project_id,
        scene_uuid=new_uuid,
        scene_order=insert_order,
        narration=data.narration,
        image_prompt=data.image_prompt or f"Cinematic scene representing: {data.narration[:60]}",
        enhanced_prompt=data.image_prompt or f"Cinematic scene representing: {data.narration[:60]}",
        shot_type="Medium Shot",
        camera_motion="slow_zoom_in",
        transition="crossfade",
        duration_target=max(3.0, round(len(data.narration.split()) / 2.5, 2)),
        image_status="not_created",
        tts_status="not_created",
        clip_status="not_created",
        scene_type="motion"
    )
    db.add(new_scene)
    db.commit()
    db.refresh(new_scene)
    return new_scene


@router.patch("/scenes/{scene_uuid}")
def patch_scene(scene_uuid: str, updates: SceneUpdateSchema, db: Session = Depends(get_db)):
    fields = updates.model_dump(exclude_unset=True)
    if any(fields.get(name, '') is None for name in ('narration', 'shot_type', 'camera_motion', 'scene_type', 'duration_target')):
        raise HTTPException(status_code=422, detail='Обязательные поля сцены не могут быть null')
    scene = update_scene_fields(db, scene_uuid, fields)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.delete("/scenes/{scene_uuid}")
def delete_scene(scene_uuid: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    project_id = scene.project_id
    db.delete(scene)
    db.flush()

    # Re-sequence remaining scene orders
    remaining = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    for idx, sc in enumerate(remaining, start=1):
        sc.scene_order = idx
    db.commit()
    
    return {"message": "Scene deleted successfully", "scene_uuid": scene_uuid}


@router.post("/scenes/{scene_uuid}/split")
def split_scene_endpoint(scene_uuid: str, body: SplitSceneSchema, db: Session = Depends(get_db)):
    try:
        scene_a, scene_b = split_scene_by_uuid(db, scene_uuid, body.split_index, body.split_text)
        return [scene_a, scene_b]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenes/merge")
def merge_scenes_endpoint(body: MergeScenesSchema, db: Session = Depends(get_db)):
    try:
        return merge_scenes_by_uuids(db, body.first_scene_uuid, body.second_scene_uuid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/scenes/reorder")
def reorder_scenes_endpoint(project_id: str, body: ReorderScenesSchema, db: Session = Depends(get_db)):
    try:
        return reorder_scenes_by_uuids(db, project_id, body.scene_uuids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenes/{scene_uuid}/generate-image")
async def generate_single_scene_image(scene_uuid: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    project = db.query(Project).filter(Project.id == scene.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scene.image_status = "running"
    scene.error_message = None
    db.commit()

    img_dir = get_project_dir(project.id, "images")
    img_path = str(img_dir / f"scene_{scene.scene_uuid}_{uuid.uuid4().hex}.png")
    tmp_path = str(img_dir / f"scene_{scene.scene_uuid}.tmp.png")

    if project.active_image_provider == "local_cards":
        prompt = f"Scene #{scene.scene_order}: {scene.narration}"
    else:
        prompt = scene.enhanced_prompt or scene.image_prompt or scene.narration
        if project.global_visual_style:
            prompt = f"{prompt}, {project.global_visual_style}"

    try:
        img_provider = get_image_provider(db, project.active_image_provider or "gemini_image")
        res_path = await img_provider.generate_image(
            prompt=prompt,
            aspect_ratio=project.aspect_ratio or "16:9",
            save_path=tmp_path
        )
        if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, img_path)
            res_path = img_path
        else:
            raise ProviderError('Провайдер не создал изображение. Предыдущий файл сохранён.')

        scene.image_path = res_path
        scene.image_status = "completed"
        scene.image_prompt_needs_review = False
        scene.error_message = None
        if scene.clip_status == "completed":
            scene.clip_status = "outdated"

        variation = ImageVariation(
            scene_uuid=scene.scene_uuid,
            project_id=scene.project_id,
            image_path=res_path,
            prompt_used=prompt,
            is_active=True
        )
        db.query(ImageVariation).filter(
            ImageVariation.scene_uuid == scene.scene_uuid,
            ImageVariation.is_active.is_(True),
        ).update({ImageVariation.is_active: False}, synchronize_session=False)
        db.add(variation)
        db.commit()
        db.refresh(scene)
        return scene

    except Exception as e:
        db.rollback()
        scene.image_status = "error"
        scene.error_message = f"Image generation failed: {str(e)}"
        db.commit()
        raise HTTPException(status_code=e.status_code if isinstance(e, ProviderError) else 502, detail=scene.error_message)


@router.post("/scenes/{scene_uuid}/generate-tts")
async def generate_single_scene_tts(scene_uuid: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    project = db.query(Project).filter(Project.id == scene.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        duration = await generate_scene_tts(db, project, scene)
        db.refresh(scene)
        return scene
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes/{scene_uuid}/render-clip")
async def render_single_scene_clip_endpoint(scene_uuid: str, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    project = db.query(Project).filter(Project.id == scene.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        clip_path = await render_single_scene_clip(db, project, scene)
        db.refresh(scene)
        return scene
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes/{scene_uuid}/upload-image")
async def upload_scene_image(scene_uuid: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    content = read_upload(file, MAX_IMAGE_BYTES)
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(image.format)
    except (UnidentifiedImageError, OSError, ValueError):
        suffix = None
    if not suffix:
        raise HTTPException(status_code=422, detail="Поддерживаются только корректные PNG, JPEG и WebP изображения.")

    img_dir = get_project_dir(scene.project_id, "images")
    img_path = str(img_dir / f"scene_{scene.scene_uuid}_custom_{uuid.uuid4().hex}{suffix}")
    with open(img_path, "wb") as buffer:
        buffer.write(content)

    scene.image_path = img_path
    scene.image_status = "completed"
    scene.image_prompt_needs_review = False
    scene.error_message = None
    if scene.clip_status == "completed":
        scene.clip_status = "outdated"
    
    variation = ImageVariation(
        scene_uuid=scene.scene_uuid,
        project_id=scene.project_id,
        image_path=img_path,
        prompt_used="User uploaded custom image",
        is_active=True
    )
    db.query(ImageVariation).filter(
        ImageVariation.scene_uuid == scene.scene_uuid,
        ImageVariation.is_active.is_(True),
    ).update({ImageVariation.is_active: False}, synchronize_session=False)
    db.add(variation)
    db.commit()
    db.refresh(scene)
    return scene


@router.post("/scenes/{scene_uuid}/upload-audio")
async def upload_scene_audio(scene_uuid: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
        raise HTTPException(status_code=422, detail="Неподдерживаемый формат аудио.")
    content = read_upload(file, MAX_AUDIO_BYTES)
    audio_dir = get_project_dir(scene.project_id, "audio")
    audio_path = str(audio_dir / f"scene_{scene.scene_uuid}_custom_{uuid.uuid4().hex}{ext}")
    with open(audio_path, "wb") as buffer:
        buffer.write(content)

    try:
        duration = probe_audio_duration(audio_path)
    except Exception as exc:
        os.remove(audio_path)
        raise HTTPException(status_code=422, detail="Не удалось прочитать загруженный аудиофайл.") from exc
    scene.audio_path = audio_path
    scene.actual_duration = duration
    scene.audio_offset_start = 0.0
    scene.audio_offset_end = duration
    scene.tts_status = "completed"
    scene.error_message = None
    if scene.clip_status == "completed":
        scene.clip_status = "outdated"

    db.commit()
    db.refresh(scene)
    return scene


def natural_sort_key(s: str):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]


def parse_prompts_text(raw_text: str) -> List[str]:
    lines = raw_text.replace("\r\n", "\n").split("\n")
    prompts = []
    current_block = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_block:
                prompts.append(" ".join(current_block))
                current_block = []
            continue
        match = re.match(r'^(?:сцена\s*\d+[\s:\.\-]*|scene\s*\d+[\s:\.\-]*|\d+[\.\)\-:]\s*)(.*)$', stripped, re.IGNORECASE)
        if match:
            if current_block:
                prompts.append(" ".join(current_block))
                current_block = []
            content = match.group(1).strip()
            if content:
                current_block.append(content)
        else:
            current_block.append(stripped)

    if current_block:
        prompts.append(" ".join(current_block))

    return [p for p in prompts if p]


class ImportPromptsPayload(BaseModel):
    prompts_text: Optional[str] = None


@router.post("/projects/{project_id}/import-prompts")
async def import_prompts_endpoint(
    project_id: str,
    payload: Optional[ImportPromptsPayload] = None,
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    raw_text = ""
    if file:
        content = read_upload(file, 5 * 1024 * 1024)
        raw_text = content.decode("utf-8", errors="replace")
    elif payload and payload.prompts_text:
        raw_text = payload.prompts_text

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="Текст с промптами пустой.")

    parsed_prompts = parse_prompts_text(raw_text)
    if not parsed_prompts:
        raise HTTPException(status_code=422, detail="Не удалось распознать ни одного промпта в тексте.")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    updated_count = 0
    created_count = 0

    for idx, prompt_text in enumerate(parsed_prompts):
        if idx < len(scenes):
            sc = scenes[idx]
            sc.image_prompt = prompt_text
            sc.image_status = "not_created"
            sc.image_prompt_needs_review = False
            if sc.clip_status == "completed":
                sc.clip_status = "outdated"
            updated_count += 1
        else:
            new_order = len(scenes) + created_count + 1
            new_scene = Scene(
                project_id=project_id,
                scene_order=new_order,
                narration=prompt_text,
                image_prompt=prompt_text,
                shot_type="Medium Shot",
                camera_motion="slow_zoom_in",
                transition="crossfade",
                duration_target=max(3.0, round(len(prompt_text.split()) / 2.5, 2)),
                image_status="not_created",
                tts_status="not_created",
                clip_status="not_created",
                scene_type="motion"
            )
            db.add(new_scene)
            created_count += 1

    db.commit()
    all_scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    return {
        "status": "success",
        "imported_count": len(parsed_prompts),
        "updated_scenes": updated_count,
        "created_scenes": created_count,
        "total_scenes": len(all_scenes)
    }


@router.post("/projects/{project_id}/batch-upload-images")
async def batch_upload_images(
    project_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not files:
        raise HTTPException(status_code=422, detail="Файлы не выбраны.")

    sorted_files = sorted(files, key=lambda f: natural_sort_key(f.filename or ""))
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()

    if not scenes:
        raise HTTPException(status_code=400, detail="В проекте нет сцен для привязки изображений.")

    img_dir = get_project_dir(project_id, "images")
    applied_count = 0

    for idx, upload in enumerate(sorted_files):
        if idx >= len(scenes):
            break
        scene = scenes[idx]
        content = read_upload(upload, MAX_IMAGE_BYTES)
        try:
            with Image.open(io.BytesIO(content)) as img:
                img.verify()
                suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(img.format)
        except Exception:
            suffix = None
        if not suffix:
            continue

        img_path = str(img_dir / f"scene_{scene.scene_uuid}_batch_{uuid.uuid4().hex}{suffix}")
        with open(img_path, "wb") as buffer:
            buffer.write(content)

        scene.image_path = img_path
        scene.image_status = "completed"
        scene.image_prompt_needs_review = False
        scene.error_message = None
        if scene.clip_status == "completed":
            scene.clip_status = "outdated"

        variation = ImageVariation(
            scene_uuid=scene.scene_uuid,
            project_id=scene.project_id,
            image_path=img_path,
            prompt_used=f"Batch uploaded ({upload.filename})",
            is_active=True
        )
        db.query(ImageVariation).filter(
            ImageVariation.scene_uuid == scene.scene_uuid,
            ImageVariation.is_active.is_(True),
        ).update({ImageVariation.is_active: False}, synchronize_session=False)
        db.add(variation)
        applied_count += 1

    db.commit()
    return {
        "status": "success",
        "total_files": len(files),
        "applied_scenes": applied_count
    }

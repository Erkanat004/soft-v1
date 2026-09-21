import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ProviderSetting
from app.schemas import ProviderSettingCreate, ProviderSettingResponse
from app.services.key_store import set_api_key, has_api_key, delete_api_key
from app.services.providers.factory import get_text_provider, get_image_provider, get_tts_provider
from app.config import FFMPEG_PATH, FFPROBE_PATH

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULT_PROVIDERS = [
    {"name": "gemini", "type": "text", "model": "gemini-3.6-flash"},
    {"name": "gemini_image", "type": "image", "model": "imagen-3.0-generate-002"},
    {"name": "openai", "type": "text", "model": "gpt-4o", "url": "https://api.openai.com/v1"},
    {"name": "openai_image", "type": "image", "model": "dall-e-3", "url": "https://api.openai.com/v1"},
    {"name": "openai_tts", "type": "tts", "model": "tts-1", "voice": "onyx", "url": "https://api.openai.com/v1"},
    {"name": "elevenlabs", "type": "tts", "model": "eleven_multilingual_v2", "voice": "JBFqnCBsd6RMkjVDRZzb"},
    {"name": "fish_audio", "type": "tts", "model": "fish-speech-1.5", "voice": "reference_id"},
    {"name": "ai_horde", "type": "text", "model": "PHG/Pygmalion-3B", "url": "https://aihorde.net/api/v2"},
    {"name": "ai_horde_image", "type": "image", "model": "Deliberate", "url": "https://aihorde.net/api/v2"},
    {"name": "openrouter", "type": "text", "model": "anthropic/claude-3.5-sonnet", "url": "https://openrouter.ai/api/v1"},
    {"name": "deepseek", "type": "text", "model": "deepseek-chat", "url": "https://api.deepseek.com/v1"},
]



def init_default_providers(db: Session):
    for p in DEFAULT_PROVIDERS:
        name = p["name"]
        existing = db.query(ProviderSetting).filter(ProviderSetting.provider_name == name).first()
        if not existing:
            setting = ProviderSetting(
                provider_name=name,
                provider_type=p["type"],
                is_enabled=True,
                model_id=p.get("model"),
                base_url=p.get("url"),
                voice_id=p.get("voice")
            )
            db.add(setting)
        elif existing.provider_name == "gemini" and existing.model_id == "gemini-2.5-flash":
            existing.model_id = "gemini-3.6-flash"
    db.commit()


@router.get("/providers", response_model=List[ProviderSettingResponse])
def get_providers(db: Session = Depends(get_db)):
    init_default_providers(db)
    providers = db.query(ProviderSetting).all()
    res = []
    for p in providers:
        item = ProviderSettingResponse.from_orm(p)
        item.has_api_key = has_api_key(p.provider_name)
        res.append(item)
    return res

@router.post("/providers", response_model=ProviderSettingResponse)
def save_provider_setting(payload: ProviderSettingCreate, db: Session = Depends(get_db)):
    existing = db.query(ProviderSetting).filter(ProviderSetting.provider_name == payload.provider_name).first()
    if not existing:
        existing = ProviderSetting(
            provider_name=payload.provider_name,
            provider_type=payload.provider_type,
            is_enabled=payload.is_enabled,
            model_id=payload.model_id,
            base_url=payload.base_url,
            endpoint=payload.endpoint,
            voice_id=payload.voice_id,
            extra_config_json=payload.extra_config_json
        )
        db.add(existing)
    else:
        existing.is_enabled = payload.is_enabled
        existing.model_id = payload.model_id
        existing.base_url = payload.base_url
        existing.endpoint = payload.endpoint
        existing.voice_id = payload.voice_id
        existing.extra_config_json = payload.extra_config_json

    db.commit()

    # Save secret API Key securely via keyring (NEVER in database)
    if payload.api_key is not None:
        if payload.api_key.strip():
            set_api_key(payload.provider_name, payload.api_key.strip(), remember=payload.remember_key)
        else:
            delete_api_key(payload.provider_name)

    res = ProviderSettingResponse.from_orm(existing)
    res.has_api_key = has_api_key(existing.provider_name)
    return res

@router.post("/providers/{provider_name}/test")
async def test_provider_connection(provider_name: str, db: Session = Depends(get_db)):
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Provider not found")

    ptype = setting.provider_type
    try:
        if ptype in ["text", "custom"]:
            p = get_text_provider(db, provider_name)
            ok = await p.test_connection()
        elif ptype in ["image"]:
            p = get_image_provider(db, provider_name)
            ok = await p.test_connection()
        elif ptype in ["tts"]:
            p = get_tts_provider(db, provider_name)
            ok = await p.test_connection()
        else:
            ok = True

        return {"provider": provider_name, "status": "success" if ok else "failed", "connected": ok}
    except Exception as e:
        return {"provider": provider_name, "status": "error", "error": str(e), "connected": False}

@router.get("/ffmpeg")
def check_ffmpeg_status():
    ffmpeg_found = bool(shutil.which("ffmpeg") or shutil.which(FFMPEG_PATH))
    ffprobe_found = bool(shutil.which("ffprobe") or shutil.which(FFPROBE_PATH))
    return {
        "ffmpeg_installed": ffmpeg_found,
        "ffprobe_installed": ffprobe_found,
        "ffmpeg_path": FFMPEG_PATH,
        "ffprobe_path": FFPROBE_PATH
    }

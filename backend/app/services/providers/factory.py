import logging
from sqlalchemy.orm import Session
from app.models import ProviderSetting
from app.services.key_store import get_api_key, has_api_key
from app.services.providers.base import BaseTextProvider, BaseImageProvider, BaseTTSProvider
from app.services.providers.mock_provider import MockTextProvider, MockImageProvider, MockTTSProvider
from app.services.providers.gemini_provider import GeminiTextProvider, GeminiImageProvider
from app.services.providers.openai_provider import OpenAITextProvider, OpenAIImageProvider, OpenAITTSProvider
from app.services.providers.elevenlabs_provider import ElevenLabsTTSProvider
from app.services.providers.fish_audio_provider import FishAudioTTSProvider
from app.services.providers.ai_horde_provider import AIHordeTextProvider, AIHordeImageProvider
from app.services.providers.custom_provider import CustomTextProvider, CustomImageProvider

logger = logging.getLogger("provider_factory")

def get_text_provider(db: Session, provider_name: str = "gemini") -> BaseTextProvider:
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    
    # If no API key configured, use MockProvider for instant dry-run testing
    if not has_api_key(provider_name) and provider_name not in ["mock", "ai_horde"]:
        logger.info(f"No API key found for text provider '{provider_name}'. Falling back to MockTextProvider.")
        return MockTextProvider()

    model_id = setting.model_id if setting else None
    base_url = setting.base_url if setting else None

    if provider_name == "ai_horde":
        return AIHordeTextProvider(model_id=model_id)
    elif provider_name == "gemini":
        return GeminiTextProvider(model_id=model_id)
    elif provider_name in ["openai", "openrouter", "deepseek", "claude"]:
        return OpenAITextProvider(model_id=model_id, base_url=base_url, provider_name=provider_name)
    elif setting and setting.provider_type in ["custom", "text"]:
        return CustomTextProvider(
            provider_name=provider_name,
            base_url=base_url or "",
            model_id=model_id or "default",
            endpoint=setting.endpoint,
            headers_json=setting.extra_config_json
        )
    
    return MockTextProvider()

def get_image_provider(db: Session, provider_name: str = "gemini_image") -> BaseImageProvider:
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    
    key_name = provider_name
    if not has_api_key(key_name) and not has_api_key("gemini") and not has_api_key("openai") and provider_name not in ["ai_horde_image", "ai_horde"]:
        logger.info(f"No API key found for image provider '{provider_name}'. Falling back to MockImageProvider.")
        return MockImageProvider()

    model_id = setting.model_id if setting else None
    base_url = setting.base_url if setting else None

    if provider_name in ["ai_horde_image", "ai_horde"]:
        return AIHordeImageProvider(model_id=model_id)
    elif provider_name in ["gemini_image", "gemini"]:
        return GeminiImageProvider(model_id=model_id)
    elif provider_name in ["openai_image", "openai"]:
        return OpenAIImageProvider(model_id=model_id, base_url=base_url, provider_name=provider_name)
    elif setting and setting.provider_type in ["custom", "image"]:
        return CustomImageProvider(
            provider_name=provider_name,
            base_url=base_url or "",
            model_id=model_id or "default",
            endpoint=setting.endpoint,
            headers_json=setting.extra_config_json
        )

    return MockImageProvider()


def get_tts_provider(db: Session, provider_name: str = "elevenlabs") -> BaseTTSProvider:
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    
    if not has_api_key(provider_name) and not has_api_key("elevenlabs") and not has_api_key("openai") and not has_api_key("fish_audio"):
        logger.info(f"No API key found for TTS provider '{provider_name}'. Falling back to MockTTSProvider.")
        return MockTTSProvider()

    model_id = setting.model_id if setting else None
    voice_id = setting.voice_id if setting else None
    base_url = setting.base_url if setting else None

    if provider_name == "fish_audio":
        return FishAudioTTSProvider(model_id=model_id, voice_id=voice_id)
    elif provider_name == "elevenlabs":
        return ElevenLabsTTSProvider(model_id=model_id, voice_id=voice_id)
    elif provider_name in ["openai_tts", "openai"]:
        return OpenAITTSProvider(model_id=model_id, voice_id=voice_id, base_url=base_url, provider_name=provider_name)

    return MockTTSProvider()


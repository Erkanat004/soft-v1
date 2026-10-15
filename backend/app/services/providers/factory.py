import logging
from sqlalchemy.orm import Session
from app.models import ProviderSetting
from app.services.key_store import get_api_key, has_api_key
from app.services.providers.base import BaseTextProvider, BaseImageProvider, BaseTTSProvider
from app.services.providers.mock_provider import MockTextProvider, MockImageProvider, MockTTSProvider, LocalCardImageProvider
from app.services.providers.gemini_provider import GeminiTextProvider, GeminiImageProvider
from app.services.providers.openai_provider import OpenAITextProvider, OpenAIImageProvider, OpenAITTSProvider
from app.services.providers.elevenlabs_provider import ElevenLabsTTSProvider
from app.services.providers.fish_audio_provider import FishAudioTTSProvider
from app.services.providers.ai_horde_provider import AIHordeTextProvider, AIHordeImageProvider
from app.services.providers.custom_provider import CustomTextProvider, CustomImageProvider
from app.services.providers.windows_tts_provider import WindowsTTSProvider
from app.services.providers.edge_tts_provider import EdgeTTSProvider
from app.services.providers.fallback_text import FallbackTextProvider
from app.services.errors import ProviderError

logger = logging.getLogger("provider_factory")

def get_text_provider(db: Session, provider_name: str = "gemini") -> BaseTextProvider:
    if provider_name in ["mock", "mock_text"]:
        return MockTextProvider()
    if provider_name == "auto_text":
        primary = get_text_provider(db, "gemini") if has_api_key("gemini") else None
        backup = get_text_provider(db, "openrouter") if has_api_key("openrouter") else None
        if primary and backup:
            return FallbackTextProvider(primary, backup)
        if primary or backup:
            return primary or backup
        raise ProviderError("Не задан ключ Gemini или OpenRouter. Добавьте ключ в настройках.", 503)
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    
    # Placeholders must be explicitly selected, never mistaken for AI output.
    if not has_api_key(provider_name) and provider_name not in ["mock", "ai_horde"]:
        raise ProviderError('Не задан ключ текстового провайдера. Проверьте настройки или выберите mock.', 503)

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
    if provider_name in ["mock", "mock_image"]:
        return MockImageProvider()
    if provider_name == "local_cards":
        return LocalCardImageProvider()
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    
    key_names = {'gemini_image': ('gemini_image', 'gemini'), 'openai_image': ('openai_image', 'openai')}.get(provider_name, (provider_name,))
    if not any(has_api_key(name) for name in key_names) and provider_name not in ['ai_horde_image', 'ai_horde']:
        raise ProviderError('Не задан ключ провайдера изображений. Проверьте настройки или выберите mock.', 503)

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
    if provider_name in ["mock", "mock_tts"]:
        return MockTTSProvider()
    if provider_name == "windows_tts":
        return WindowsTTSProvider()
    if provider_name == "edge_tts":
        setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == "edge_tts").first()
        voice_id = setting.voice_id if setting else None
        return EdgeTTSProvider(voice_id=voice_id)
    setting = db.query(ProviderSetting).filter(ProviderSetting.provider_name == provider_name).first()
    
    key_names = ('openai_tts', 'openai') if provider_name == 'openai_tts' else (provider_name,)
    if not any(has_api_key(name) for name in key_names):
        raise ProviderError('Не задан ключ провайдера озвучки. Проверьте настройки или выберите mock.', 503)

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

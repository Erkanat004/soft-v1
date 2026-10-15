"""Free neural speech synthesis using Microsoft Edge TTS with no API keys."""
import os
import re
import logging
from pathlib import Path
from typing import Optional

from app.services.errors import ProviderError
from app.services.providers.base import BaseTTSProvider

logger = logging.getLogger("edge_tts_provider")

DEFAULT_RU_VOICE = "ru-RU-DmitryNeural"
DEFAULT_EN_VOICE = "en-US-ChristopherNeural"

POPULAR_VOICES = {
    "ru-RU-DmitryNeural": "Дмитрий (Русский, мужской)",
    "ru-RU-SvetlanaNeural": "Светлана (Русский, женский)",
    "en-US-ChristopherNeural": "Christopher (English, Male Narrative)",
    "en-US-JennyNeural": "Jenny (English, Female)",
    "en-US-GuyNeural": "Guy (English, Male)",
    "en-US-AriaNeural": "Aria (English, Expressive)",
}


class EdgeTTSProvider(BaseTTSProvider):
    def __init__(self, voice_id: Optional[str] = None):
        self.default_voice = voice_id or DEFAULT_RU_VOICE

    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        clean_text = text.strip()
        if not clean_text:
            raise ProviderError("Нельзя озвучить пустую сцену.", 422)
        if not save_path:
            raise ProviderError("Не задан путь для сохранения аудиофайла.")

        output_path = Path(save_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        chosen_voice = voice_id or self.default_voice
        if not voice_id:
            # Auto-detect language if voice not explicitly locked
            is_cyrillic = bool(re.search(r"[А-Яа-яЁё]", clean_text))
            chosen_voice = DEFAULT_RU_VOICE if is_cyrillic else DEFAULT_EN_VOICE

        try:
            import edge_tts
        except ImportError:
            raise ProviderError("Библиотека edge-tts не установлена в виртуальном окружении.", 503)

        try:
            communicate = edge_tts.Communicate(clean_text, chosen_voice)
            await communicate.save(str(output_path))
        except Exception as exc:
            logger.error("EdgeTTS generation error: %s", exc)
            raise ProviderError(f"Ошибка Edge-TTS ({chosen_voice}): {str(exc)}", 502) from exc

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise ProviderError("Edge-TTS создал пустой аудиофайл.", 502)

        return str(output_path)

    async def test_connection(self) -> bool:
        try:
            import edge_tts
            return True
        except Exception:
            return False

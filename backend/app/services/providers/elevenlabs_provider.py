import os
import logging
import httpx
from typing import Optional
from app.services.providers.base import BaseTTSProvider
from app.services.key_store import get_api_key

logger = logging.getLogger("elevenlabs_provider")

class ElevenLabsTTSProvider(BaseTTSProvider):
    def __init__(self, model_id: Optional[str] = None, voice_id: Optional[str] = None):
        self.model_id = model_id or "eleven_multilingual_v2"
        self.default_voice_id = voice_id or "JBFqnCBsd6RMkjVDRZzb"  # George voice ID fallback

    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        api_key = get_api_key("elevenlabs")
        if not api_key:
            raise ValueError("ElevenLabs API key is not configured in Settings → API Providers")

        target_voice = voice_id or self.default_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{target_voice}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"ElevenLabs API error ({resp.status_code}): {resp.text}")
            
            if not save_path:
                save_path = "elevenlabs_speech.mp3"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)

            return save_path

    async def test_connection(self) -> bool:
        api_key = get_api_key("elevenlabs")
        if not api_key:
            return False
        url = "https://api.elevenlabs.io/v1/user"
        headers = {"xi-api-key": api_key}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

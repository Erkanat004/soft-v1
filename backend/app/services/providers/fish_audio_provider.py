import os
import logging
import httpx
from typing import Optional
from app.services.providers.base import BaseTTSProvider
from app.services.key_store import get_api_key

logger = logging.getLogger("fish_audio_provider")

class FishAudioTTSProvider(BaseTTSProvider):
    def __init__(self, model_id: Optional[str] = None, voice_id: Optional[str] = None):
        self.model_id = model_id or "fish-speech-1.5"
        # Fish Audio uses reference_id for custom voice clones / models
        self.default_reference_id = voice_id or get_api_key("fish_audio_voice") or "19021b44b9a8427297bcb6dc1c872c6b"

    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        api_key = get_api_key("fish_audio")
        if not api_key:
            raise ValueError("Fish Audio API key is not configured in Settings → API Providers")

        ref_id = voice_id or self.default_reference_id
        url = "https://api.fish.audio/v1/tts"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "text": text,
            "format": "mp3",
            "latency": "normal"
        }
        if ref_id:
            payload["reference_id"] = ref_id

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Fish Audio API error ({resp.status_code}): {resp.text}")
            
            if not save_path:
                save_path = "fish_audio_speech.mp3"
            dirname = os.path.dirname(save_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)

            return save_path

    async def test_connection(self) -> bool:
        api_key = get_api_key("fish_audio")
        if not api_key:
            return False
        url = "https://api.fish.audio/model"
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

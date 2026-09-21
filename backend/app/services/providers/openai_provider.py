import os
import json
import logging
import httpx
from typing import Optional
from app.services.providers.base import BaseTextProvider, BaseImageProvider, BaseTTSProvider
from app.services.key_store import get_api_key

logger = logging.getLogger("openai_provider")

class OpenAITextProvider(BaseTextProvider):
    def __init__(self, model_id: Optional[str] = None, base_url: Optional[str] = None, provider_name: str = "openai"):
        self.model_id = model_id or "gpt-4o"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.provider_name = provider_name

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        api_key = get_api_key(self.provider_name)
        if not api_key:
            raise ValueError(f"{self.provider_name} API key is not configured in Settings → API Providers")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": 0.7
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI Text API error ({resp.status_code}): {resp.text}")
            
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def test_connection(self) -> bool:
        try:
            res = await self.generate_text("Hi")
            return bool(res)
        except Exception as e:
            logger.error(f"OpenAI Text test connection failed: {e}")
            return False

class OpenAIImageProvider(BaseImageProvider):
    def __init__(self, model_id: Optional[str] = None, base_url: Optional[str] = None, provider_name: str = "openai_image"):
        self.model_id = model_id or "dall-e-3"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.provider_name = provider_name

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        api_key = get_api_key(self.provider_name) or get_api_key("openai")
        if not api_key:
            raise ValueError(f"OpenAI Image API key is not configured in Settings → API Providers")

        url = f"{self.base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        size = "1024x1024"
        if aspect_ratio == "16:9":
            size = "1792x1024"
        elif aspect_ratio == "9:16":
            size = "1024x1792"

        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json"
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI Image API error ({resp.status_code}): {resp.text}")
            
            data = resp.json()
            import base64
            b64_data = data["data"][0]["b64_json"]
            image_bytes = base64.b64decode(b64_data)

            if not save_path:
                save_path = "openai_image.png"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(image_bytes)

            return save_path

    async def test_connection(self) -> bool:
        api_key = get_api_key(self.provider_name) or get_api_key("openai")
        return bool(api_key)

class OpenAITTSProvider(BaseTTSProvider):
    def __init__(self, model_id: Optional[str] = None, voice_id: Optional[str] = None, base_url: Optional[str] = None, provider_name: str = "openai_tts"):
        self.model_id = model_id or "tts-1"
        self.default_voice = voice_id or "onyx"
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.provider_name = provider_name

    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        api_key = get_api_key(self.provider_name) or get_api_key("openai")
        if not api_key:
            raise ValueError(f"OpenAI TTS API key is not configured in Settings → API Providers")

        url = f"{self.base_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_id,
            "input": text,
            "voice": voice_id or self.default_voice
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI TTS API error ({resp.status_code}): {resp.text}")
            
            if not save_path:
                save_path = "openai_tts.mp3"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)

            return save_path

    async def test_connection(self) -> bool:
        api_key = get_api_key(self.provider_name) or get_api_key("openai")
        return bool(api_key)

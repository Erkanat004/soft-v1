import os
import asyncio
import logging
import httpx
from typing import Optional
from app.services.providers.base import BaseTextProvider, BaseImageProvider
from app.services.key_store import get_api_key

logger = logging.getLogger("ai_horde_provider")

ANONYMOUS_KEY = "0000000000"

class AIHordeTextProvider(BaseTextProvider):
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or "PHG/Pygmalion-3B"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        api_key = get_api_key("ai_horde") or ANONYMOUS_KEY
        url = "https://aihorde.net/api/v2/generate/text/async"
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
            "Client-Agent": "StoryForgeAI:1.0:antigravity"
        }

        full_prompt = f"{system_prompt}\n{prompt}" if system_prompt else prompt
        payload = {
            "prompt": full_prompt,
            "params": {
                "max_context_length": 2048,
                "max_length": 512,
                "temperature": 0.7
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 202:
                raise RuntimeError(f"AI Horde Text submission error ({resp.status_code}): {resp.text}")
            
            job_id = resp.json().get("id")
            if not job_id:
                raise RuntimeError("AI Horde returned no job ID")

            # Poll for completion
            status_url = f"https://aihorde.net/api/v2/generate/text/status/{job_id}"
            for _ in range(30):
                await asyncio.sleep(4)
                st_resp = await client.get(status_url, headers=headers)
                if st_resp.status_code == 200:
                    st_data = st_resp.json()
                    if st_data.get("done"):
                        generations = st_data.get("generations", [])
                        if generations:
                            return generations[0].get("text", "")
                        break
            
            raise TimeoutError("AI Horde Text generation timed out")

    async def test_connection(self) -> bool:
        try:
            res = await self.generate_text("Hi")
            return bool(res)
        except Exception:
            return False

class AIHordeImageProvider(BaseImageProvider):
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or "Deliberate"

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        api_key = get_api_key("ai_horde_image") or get_api_key("ai_horde") or ANONYMOUS_KEY
        url = "https://aihorde.net/api/v2/generate/async"
        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
            "Client-Agent": "StoryForgeAI:1.0:antigravity"
        }

        width, height = 1024, 576
        if aspect_ratio == "9:16":
            width, height = 576, 1024
        elif aspect_ratio == "1:1":
            width, height = 768, 768

        payload = {
            "prompt": prompt,
            "params": {
                "width": width,
                "height": height,
                "steps": 20,
                "n": 1
            },
            "models": [self.model_id, "stable_diffusion"]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 202:
                raise RuntimeError(f"AI Horde Image submission error ({resp.status_code}): {resp.text}")

            job_id = resp.json().get("id")
            if not job_id:
                raise RuntimeError("AI Horde Image returned no job ID")

            # Poll for completion
            status_url = f"https://aihorde.net/api/v2/generate/status/{job_id}"
            for _ in range(40):
                await asyncio.sleep(5)
                st_resp = await client.get(status_url, headers=headers)
                if st_resp.status_code == 200:
                    st_data = st_resp.json()
                    if st_data.get("done"):
                        generations = st_data.get("generations", [])
                        if generations:
                            img_url = generations[0].get("img")
                            # Download image from Horde URL
                            img_resp = await client.get(img_url, timeout=30.0)
                            if not save_path:
                                save_path = "horde_image.png"
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(img_resp.content)
                            return save_path
                        break

            raise TimeoutError("AI Horde Image generation timed out")

    async def test_connection(self) -> bool:
        return True

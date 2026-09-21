import os
import json
import logging
import httpx
from typing import Optional, Dict, Any
from app.services.providers.base import BaseTextProvider, BaseImageProvider, BaseTTSProvider
from app.services.key_store import get_api_key

logger = logging.getLogger("custom_provider")

class CustomTextProvider(BaseTextProvider):
    def __init__(self, provider_name: str, base_url: str, model_id: str, endpoint: Optional[str] = None, headers_json: Optional[str] = "{}"):
        self.provider_name = provider_name
        self.base_url = (base_url or "").rstrip("/")
        self.model_id = model_id
        self.endpoint = endpoint or "/chat/completions"
        self.custom_headers = json.loads(headers_json or "{}")

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        api_key = get_api_key(self.provider_name)
        url = f"{self.base_url}{self.endpoint}"
        
        headers = {"Content-Type": "application/json", **self.custom_headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_id,
            "messages": messages
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Custom Provider '{self.provider_name}' error ({resp.status_code}): {resp.text}")
            
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            elif "output" in data:
                return str(data["output"])
            elif "text" in data:
                return str(data["text"])
            return json.dumps(data)

    async def test_connection(self) -> bool:
        try:
            res = await self.generate_text("test")
            return bool(res)
        except Exception:
            return False

class CustomImageProvider(BaseImageProvider):
    def __init__(self, provider_name: str, base_url: str, model_id: str, endpoint: Optional[str] = None, headers_json: Optional[str] = "{}"):
        self.provider_name = provider_name
        self.base_url = (base_url or "").rstrip("/")
        self.model_id = model_id
        self.endpoint = endpoint or "/images/generations"
        self.custom_headers = json.loads(headers_json or "{}")

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        api_key = get_api_key(self.provider_name)
        url = f"{self.base_url}{self.endpoint}"
        headers = {"Content-Type": "application/json", **self.custom_headers}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {"model": self.model_id, "prompt": prompt, "aspect_ratio": aspect_ratio}

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Custom Image Provider '{self.provider_name}' error ({resp.status_code}): {resp.text}")
            
            if not save_path:
                save_path = "custom_image.png"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(resp.content)
            return save_path

    async def test_connection(self) -> bool:
        return True

import os
import json
import logging
import httpx
from typing import Optional
from app.services.providers.base import BaseTextProvider, BaseImageProvider
from app.services.key_store import get_api_key

logger = logging.getLogger("gemini_provider")

class GeminiTextProvider(BaseTextProvider):
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or "gemini-3.6-flash"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        api_key = get_api_key("gemini")
        if not api_key:
            raise ValueError("Gemini API key is not configured in Settings → API Providers")

        # Candidate fallback models if primary model is 503 unavailable
        candidate_models = [self.model_id, "gemini-3.6-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        seen = set()
        models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Directive: {system_prompt}"}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        import asyncio
        last_error = ""

        for m_id in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_id}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}

            # Retry loop for 503 / 429 spikes
            for attempt in range(1, 4):
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            return data["candidates"][0]["content"]["parts"][0]["text"]
                        elif resp.status_code in [503, 429]:
                            logger.warning(f"Gemini {m_id} high demand ({resp.status_code}), retrying attempt {attempt}/3 in {attempt*3}s...")
                            await asyncio.sleep(attempt * 3)
                        else:
                            last_error = f"Gemini API error ({resp.status_code}): {resp.text}"
                            break
                except Exception as e:
                    last_error = str(e)
                    await asyncio.sleep(2)

        raise RuntimeError(f"Gemini text generation temporarily busy on Google servers: {last_error}")


    async def test_connection(self) -> bool:
        try:
            res = await self.generate_text("Respond with the word 'OK'.")
            return bool(res)
        except Exception as e:
            logger.error(f"Gemini test connection failed: {e}")
            return False

class GeminiImageProvider(BaseImageProvider):
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = model_id or "imagen-3.0-generate-002"

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        api_key = get_api_key("gemini_image") or get_api_key("gemini")
        import base64
        last_err = ""

        if api_key:
            # 1. Try Gemini OpenAI Compatibility Endpoint (gemini-2.5-flash-image)
            url_openai = "https://generativelanguage.googleapis.com/v1beta/openai/images/generations"
            headers_openai = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            payload_openai = {
                "model": "gemini-2.5-flash-image",
                "prompt": prompt,
                "response_format": "b64_json",
                "n": 1
            }
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(url_openai, headers=headers_openai, json=payload_openai)
                    if resp.status_code == 200:
                        data = resp.json()
                        if "data" in data and len(data["data"]) > 0:
                            b64_str = data["data"][0].get("b64_json")
                            if b64_str:
                                image_bytes = base64.b64decode(b64_str)
                                if not save_path:
                                    save_path = "gemini_gen_image.png"
                                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                with open(save_path, "wb") as f:
                                    f.write(image_bytes)
                                return save_path
                    else:
                        last_err = f"OpenAI endpoint ({resp.status_code}): {resp.text}"
            except Exception as e:
                last_err = f"OpenAI endpoint error: {e}"

            # 2. Try Imagen Predict Endpoint
            candidate_models = [self.model_id, "imagen-3.0-generate-002", "imagen-3.0-fast-generate-001", "imagen-4.0-generate-001"]
            seen = set()
            models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

            payload = {
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": aspect_ratio
                }
            }

            for m_id in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_id}:predict"
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key
                }

                try:
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        if resp.status_code == 200:
                            data = resp.json()
                            b64_bytes = data["predictions"][0]["bytesBase64Encoded"]
                            image_bytes = base64.b64decode(b64_bytes)

                            if not save_path:
                                save_path = "gemini_gen_image.png"
                            os.makedirs(os.path.dirname(save_path), exist_ok=True)
                            with open(save_path, "wb") as f:
                                f.write(image_bytes)
                            return save_path
                        else:
                            last_err = f"Predict {m_id} ({resp.status_code}): {resp.text}"
                except Exception as e:
                    last_err = str(e)

        logger.warning(f"Gemini Imagen API unavailable {last_err}. Falling back to AI Horde image generator...")
        
        # 3. Fallback to free AI Horde Image generator for real AI images
        try:
            from app.services.providers.ai_horde_provider import AIHordeImageProvider
            horde_p = AIHordeImageProvider()
            return await horde_p.generate_image(prompt, aspect_ratio=aspect_ratio, save_path=save_path)
        except Exception as horde_err:
            logger.warning(f"AI Horde fallback also failed ({horde_err}). Falling back to local placeholder image.")

        # 4. Final fallback to local mock image generator if both fail
        from app.services.providers.mock_provider import MockImageProvider
        mock_p = MockImageProvider()
        return await mock_p.generate_image(prompt, aspect_ratio=aspect_ratio, save_path=save_path)


    async def test_connection(self) -> bool:
        api_key = get_api_key("gemini_image") or get_api_key("gemini")
        return bool(api_key)

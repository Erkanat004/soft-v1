import base64
import io
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError
from app.services.providers.base import BaseImageProvider
from app.services.providers.gemini_text import GeminiTextProvider
from app.services.key_store import get_api_key
from app.services.errors import ProviderError


class GeminiImageProvider(GeminiTextProvider, BaseImageProvider):
    """Native Gemini image generation; no hidden cross-provider fallback."""
    image_mode = True

    def __init__(self, model_id: Optional[str] = None):
        # Imagen is retired. Resolve a supported image model rather than trying
        # a list of retired model names. Existing DB configuration is not rewritten.
        super().__init__('auto' if model_id and model_id.startswith('imagen-') else model_id)

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        key = get_api_key('gemini_image') or get_api_key('gemini')
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'responseModalities': ['TEXT', 'IMAGE'],
                                 'imageConfig': {'aspectRatio': aspect_ratio}},
        }
        data = await self.generate_content(payload, key)
        try:
            parts = data['candidates'][0]['content']['parts']
            encoded = next(p['inlineData']['data'] for p in parts
                           if p.get('inlineData', {}).get('mimeType', '').startswith('image/') and not p.get('thought'))
            content = base64.b64decode(encoded, validate=True)
            with Image.open(io.BytesIO(content)) as img:
                img.load()
                output = Path(save_path or 'gemini_gen_image.png')
                output.parent.mkdir(parents=True, exist_ok=True)
                img.save(output, format='PNG')
            return str(output)
        except (KeyError, IndexError, StopIteration, ValueError, TypeError, AttributeError, UnidentifiedImageError):
            raise ProviderError('Gemini не вернул корректное изображение. Исходные файлы сохранены.') from None

    async def test_connection(self) -> bool:
        # Validate access/model with a read-only request, not a paid image generation.
        import hashlib
        import httpx
        key = get_api_key('gemini_image') or get_api_key('gemini')
        if not key:
            return False
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                models = await self._models(client, {'x-goog-api-key': key}, hashlib.sha256(key.encode()).hexdigest())
                return self.model_id == 'auto' or self.model_id in models
        except (ProviderError, httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return False

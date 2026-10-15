"""Explicit free text route: Gemini first, OpenRouter as backup."""
import logging
from typing import Optional

from app.services.errors import ProviderError
from app.services.providers.base import BaseTextProvider


logger = logging.getLogger("fallback_text")


class FallbackTextProvider(BaseTextProvider):
    def __init__(self, primary: BaseTextProvider, backup: Optional[BaseTextProvider] = None):
        self.primary = primary
        self.backup = backup

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            return await self.primary.generate_text(prompt, system_prompt)
        except ProviderError as first_error:
            if not self.backup or first_error.status_code not in (502, 503):
                raise
            logger.warning("Primary text provider unavailable; trying configured OpenRouter backup")
            try:
                return await self.backup.generate_text(prompt, system_prompt)
            except ProviderError as backup_error:
                raise ProviderError(
                    f"Gemini: {first_error} OpenRouter: {backup_error}", 503
                ) from None

    async def test_connection(self) -> bool:
        return bool(await self.generate_text("Ответь одним словом: OK"))

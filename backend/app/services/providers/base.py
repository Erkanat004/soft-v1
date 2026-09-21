from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseTextProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

class BaseImageProvider(ABC):
    @abstractmethod
    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        """Returns path to generated image file."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

class BaseTTSProvider(ABC):
    @abstractmethod
    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        """Returns path to generated audio file."""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass

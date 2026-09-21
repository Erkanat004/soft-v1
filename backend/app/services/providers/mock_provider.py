import os
import math
import struct
import wave
import json
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from app.services.providers.base import BaseTextProvider, BaseImageProvider, BaseTTSProvider

class MockTextProvider(BaseTextProvider):
    def __init__(self, model_id: str = "mock-gpt-4"):
        self.model_id = model_id

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        prompt_lower = prompt.lower()
        
        # Check if requesting JSON scene split or bibles
        if "split" in prompt_lower or "scene" in prompt_lower or "json" in prompt_lower:
            return json.dumps({
                "characters": [
                    {
                        "name": "John",
                        "age": "34",
                        "gender": "Male",
                        "hair": "short dark brown hair",
                        "eyes": "brown",
                        "clothes": "dark gray jacket",
                        "appearance": "34-year-old Caucasian male, short dark brown hair, light stubble, tired brown eyes, dark gray jacket"
                    }
                ],
                "locations": [
                    {
                        "name": "House Basement",
                        "description": "old isolated suburban basement, concrete walls, dim lighting, flickering bulb, dusty atmosphere"
                    }
                ],
                "scenes": [
                    {
                        "scene_order": 1,
                        "narration": "It was almost midnight when John arrived home after a long shift.",
                        "shot_type": "Establishing Shot",
                        "character_names": ["John"],
                        "location_name": "House Basement",
                        "image_prompt": "Cinematic wide shot of an isolated suburban house at midnight, dark windows, warm dim porch light, suspenseful atmosphere"
                    },
                    {
                        "scene_order": 2,
                        "narration": "He stepped inside and heard faint, unsettling footsteps coming from the basement.",
                        "shot_type": "Medium Shot",
                        "character_names": ["John"],
                        "location_name": "House Basement",
                        "image_prompt": "Cinematic medium shot of John standing in a dark hallway near an open basement door, tense expression, deep shadow"
                    },
                    {
                        "scene_order": 3,
                        "narration": "A strange cold draft swept through the hallway as he reached for the flickering light switch.",
                        "shot_type": "Close-Up",
                        "character_names": ["John"],
                        "location_name": "House Basement",
                        "image_prompt": "Cinematic close-up of John reaching his hand toward an old light switch, dark moody lighting, high tension"
                    }
                ]
            }, indent=2)
        
        # Generic script generation mock
        return (
            "The rain hit the window glass like tiny needles in the quiet midnight hour. "
            "John stood in his living room, staring at the old rotatory telephone resting on the wooden table. "
            "It hadn't rung in twenty years. Not since the night his brother vanished into the black pine woods behind their home. "
            "Suddenly, the bell chimed with a harsh mechanical screech. John froze, his pulse spiking into his throat. "
            "He slowly lifted the heavy receiver to his ear. A voice crackled through the static—low, familiar, and trembling with dread. "
            "'John... don't go into the basement tonight. I made that mistake twenty years ago, and I am still trapped here.'"
        )

    async def test_connection(self) -> bool:
        return True

class MockImageProvider(BaseImageProvider):
    def __init__(self, model_id: str = "mock-sdxl"):
        self.model_id = model_id

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "") -> str:
        if not save_path:
            save_path = "mock_image.png"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        width, height = 1280, 720
        if aspect_ratio == "9:16":
            width, height = 720, 1280
        elif aspect_ratio == "1:1":
            width, height = 1080, 1080

        # Create atmospheric dark gradient placeholder
        img = Image.new("RGB", (width, height), color=(20, 24, 33))
        draw = ImageDraw.Draw(img)
        
        # Draw dark aesthetic rectangle background
        draw.rectangle([20, 20, width - 20, height - 20], outline=(60, 80, 120), width=4)
        
        # Text label
        short_prompt = (prompt[:80] + "...") if len(prompt) > 80 else prompt
        text = f"[STORYFORGE AI MOCK IMAGE]\nPrompt: {short_prompt}"
        draw.text((40, height // 2 - 20), text, fill=(200, 220, 255))
        
        img.save(save_path, "PNG")
        return save_path

    async def test_connection(self) -> bool:
        return True

class MockTTSProvider(BaseTTSProvider):
    def __init__(self, model_id: str = "mock-tts"):
        self.model_id = model_id

    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        if not save_path:
            save_path = "mock_speech.wav"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Estimate duration based on word count (~150 words per minute => ~0.4s per word)
        words = text.split()
        num_words = max(len(words), 3)
        duration_sec = num_words * 0.45
        duration_sec = max(4.0, min(duration_sec, 30.0))

        # Generate a silent/mild hum WAV file
        sample_rate = 22050
        num_samples = int(sample_rate * duration_sec)
        
        with wave.open(save_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            # Generate soft sine wave audio
            values = []
            freq = 220.0  # A3 pitch
            for i in range(num_samples):
                sample_val = int(500 * math.sin(2 * math.pi * freq * i / sample_rate))
                values.append(struct.pack('<h', sample_val))
            
            wav_file.writeframes(b''.join(values))

        return save_path

    async def test_connection(self) -> bool:
        return True

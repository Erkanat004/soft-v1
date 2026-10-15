import os
import math
import struct
import wave
import json
import re
from typing import Optional
from PIL import Image, ImageDraw, ImageFont
from app.services.providers.base import BaseTextProvider, BaseImageProvider, BaseTTSProvider

SIMULATE_API_ERROR: Optional[int] = None

def set_simulated_error(code: Optional[int]):
    global SIMULATE_API_ERROR
    SIMULATE_API_ERROR = code

def get_simulated_error() -> Optional[int]:
    return SIMULATE_API_ERROR

def check_simulated_error():
    global SIMULATE_API_ERROR
    if SIMULATE_API_ERROR == 401:
        raise Exception("HTTP 401 Unauthorized: Invalid API Key provided.")
    elif SIMULATE_API_ERROR == 408:
        raise Exception("HTTP 408 Request Timeout: Generation timed out after 30 seconds.")
    elif SIMULATE_API_ERROR == 429:
        raise Exception("HTTP 429 Rate Limit Exceeded: Provider request limit reached.")
    elif SIMULATE_API_ERROR == 500:
        raise Exception("HTTP 500 Internal Server Error: Provider service error.")


def _card_font(size: int, bold: bool = False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    paths = [os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", name),
             "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _card_lines(draw, text: str, font, width: int, limit: int):
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > limit:
        lines = lines[:limit]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


class MockTextProvider(BaseTextProvider):
    def __init__(self, model_id: str = "mock-gpt-4"):
        self.model_id = model_id

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        check_simulated_error()
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
        check_simulated_error()
        return True

class MockImageProvider(BaseImageProvider):
    def __init__(self, model_id: str = "mock-sdxl", card_mode: str = "test"):
        self.model_id = model_id
        self.card_mode = card_mode

    async def generate_image(self, prompt: str, aspect_ratio: str = "16:9", save_path: str = "", scene_order: int = 1) -> str:
        check_simulated_error()

        if not save_path:
            save_path = "mock_image.png"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        width, height = 1280, 720
        if aspect_ratio == "9:16":
            width, height = 720, 1280
        elif aspect_ratio == "1:1":
            width, height = 1080, 1080

        # Distinct color palette per scene order
        COLORS = [
            (30, 58, 138),   # Scene 1: Deep Navy Blue (#1e3a8a)
            (136, 19, 55),   # Scene 2: Crimson Red (#881337)
            (6, 95, 70),     # Scene 3: Emerald Green (#065f46)
            (120, 53, 15),   # Scene 4: Amber Orange (#78350f)
            (88, 28, 135),   # Scene 5: Deep Purple (#581c87)
            (19, 78, 74),    # Scene 6: Dark Teal (#134e4a)
            (131, 24, 67),   # Scene 7: Deep Rose (#831843)
        ]

        # Try to infer scene order from prompt if default 1 is passed
        inferred_order = scene_order
        match = re.search(r'scene\s*#?(\d+)', prompt, re.IGNORECASE)
        if match:
            inferred_order = int(match.group(1))

        bg_color = COLORS[(inferred_order - 1) % len(COLORS)]

        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)

        if self.card_mode == "story":
            margin = max(36, round(min(width, height) * 0.06))
            draw.rounded_rectangle((margin, margin, width - margin, height - margin),
                                   radius=22, fill=(15, 23, 42), outline=(245, 158, 11), width=4)
            draw.line((margin + 34, margin + 140, width - margin - 34, margin + 140),
                      fill=(245, 158, 11), width=3)
            title_font = _card_font(round(min(width, height) * 0.055), bold=True)
            label_font = _card_font(round(min(width, height) * 0.025))
            body_font = _card_font(round(min(width, height) * 0.047))
            draw.text((margin + 34, margin + 30), f"СЦЕНА {inferred_order:02d}",
                      font=title_font, fill=(255, 255, 255))
            draw.text((margin + 34, margin + 94), "ИСТОРИЯ В КАДРЕ",
                      font=label_font, fill=(245, 158, 11))
            narration = re.sub(r'^scene\s*#?\d+:\s*', '', prompt, flags=re.IGNORECASE).strip()
            max_lines = 6 if width > height else 12
            lines = _card_lines(draw, narration, body_font, width - 2 * margin - 88, max_lines)
            line_height = round(min(width, height) * 0.067)
            for index, line in enumerate(lines):
                draw.text((margin + 44, margin + 185 + index * line_height), line,
                          font=body_font, fill=(238, 242, 255))
            footer = "ЛОКАЛЬНАЯ КАРТОЧКА • ЗАМЕНИТЕ НА ИЛЛЮСТРАЦИЮ ПРИ ЖЕЛАНИИ"
            draw.text((margin + 34, height - margin - 50), footer,
                      font=label_font, fill=(148, 163, 184))
            img.save(save_path, "PNG")
            return save_path

        # Draw outer decorative double border
        draw.rectangle([15, 15, width - 15, height - 15], outline=(255, 255, 255), width=3)
        draw.rectangle([25, 25, width - 25, height - 25], outline=(245, 158, 11), width=2)  # Gold accent

        # Corner ticks
        tick_len = 30
        draw.line([25, 25, 25 + tick_len, 25], fill=(255, 255, 255), width=4)
        draw.line([25, 25, 25, 25 + tick_len], fill=(255, 255, 255), width=4)
        draw.line([width - 25 - tick_len, 25, width - 25, 25], fill=(255, 255, 255), width=4)
        draw.line([width - 25, 25, width - 25, 25 + tick_len], fill=(255, 255, 255), width=4)

        # Title box
        title_box = [40, 40, width - 40, 120]
        draw.rectangle(title_box, fill=(15, 23, 42), outline=(255, 255, 255), width=2)
        
        header_text = (f"СЦЕНА #{inferred_order}" if self.card_mode == "story"
                       else f"ТЕСТОВАЯ КАРТОЧКА СЦЕНЫ #{inferred_order}")
        mode_text = ("STORYFORGE: ЛОКАЛЬНАЯ КАРТОЧКА (НЕ AI-ИЛЛЮСТРАЦИЯ)"
                     if self.card_mode == "story" else "⚡ STORYFORGE AI: ОФЛАЙН РЕЖИМ ПРОВЕРКИ")
        
        draw.text((60, 52), header_text, fill=(255, 255, 255))
        draw.text((60, 82), mode_text, fill=(245, 158, 11))

        # Prompt content box
        short_prompt = (prompt[:160] + "...") if len(prompt) > 160 else prompt
        prompt_box = [40, 140, width - 40, height - 70]
        draw.rectangle(prompt_box, fill=(15, 23, 42), outline=(100, 116, 139), width=2)

        draw.text((60, 160), "ПРОМПТ И ОПИСАНИЕ СЦЕНЫ:", fill=(148, 163, 184))
        
        # Word wrap preview text
        words = short_prompt.split()
        lines = []
        curr_line = []
        for w in words:
            curr_line.append(w)
            if len(" ".join(curr_line)) > 55:
                lines.append(" ".join(curr_line[:-1]))
                curr_line = [w]
        if curr_line:
            lines.append(" ".join(curr_line))

        y_pos = 195
        for l in lines[:12]:
            draw.text((60, y_pos), l, fill=(226, 232, 240))
            y_pos += 24

        # Footer info
        footer_text = (f"Формат: {aspect_ratio} | {width}x{height} | Изображение можно заменить в редакторе"
                       if self.card_mode == "story" else
                       f"Формат: {aspect_ratio} | Разрешение: {width}x{height} | Офлайн PIL карточка (Без API)")
        draw.text((40, height - 45), footer_text, fill=(203, 213, 225))

        img.save(save_path, "PNG")
        return save_path

    async def test_connection(self) -> bool:
        check_simulated_error()
        return True


class LocalCardImageProvider(MockImageProvider):
    def __init__(self):
        super().__init__(model_id="local-cards", card_mode="story")

class MockTTSProvider(BaseTTSProvider):
    def __init__(self, model_id: str = "mock-tts"):
        self.model_id = model_id

    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        check_simulated_error()

        if not save_path:
            save_path = "mock_speech.wav"
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        words = text.split()
        num_words = max(len(words), 3)
        duration_sec = num_words * 0.45
        duration_sec = max(4.0, min(duration_sec, 30.0))

        sample_rate = 22050
        num_samples = int(sample_rate * duration_sec)
        
        with wave.open(save_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            values = []
            freq = 220.0  # A3 tone
            for i in range(num_samples):
                sample_val = int(600 * math.sin(2 * math.pi * freq * i / sample_rate))
                values.append(struct.pack('<h', sample_val))
            
            wav_file.writeframes(b''.join(values))

        return save_path

    async def test_connection(self) -> bool:
        check_simulated_error()
        return True

import os
import subprocess
import logging
import math
from app.services.errors import ProviderError
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import Project, Scene
from app.config import FFMPEG_PATH, FFPROBE_PATH, ALLOW_MOCK_FALLBACK, get_project_dir
from app.services.providers.factory import get_tts_provider

logger = logging.getLogger("tts_service")

def probe_audio_duration(audio_file_path: str) -> float:
    """
    Uses FFprobe via subprocess to extract exact float duration (seconds) of any audio file.
    Supports MP3, WAV, AAC, M4A, OGG, etc.
    """
    if not os.path.isfile(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_file_path
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", errors="replace", check=True, timeout=15)
        duration_str = res.stdout.strip()
        duration = float(duration_str)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('Invalid audio duration')
        return round(duration, 2)
    except (FileNotFoundError, Exception) as e:
        logger.warning(f"FFprobe execution unavailable for {audio_file_path}: {e}")
        # Try python wave module fallback if file is WAV
        try:
            import wave
            with wave.open(audio_file_path, 'r') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return round(frames / float(rate), 2)
        except Exception:
            pass
        raise ValueError('Не удалось прочитать аудио. Проверьте формат файла и установку FFprobe.') from None


def slice_audio_file(source_audio_path: str, output_path: str, start_sec: float, duration_sec: float) -> str:
    """
    Physically slices an audio file using FFmpeg into a standalone sub-clip.
    """
    if not os.path.isfile(source_audio_path):
        raise FileNotFoundError(f"Source audio file not found: {source_audio_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start_sec),
        "-i", source_audio_path,
        "-t", str(duration_sec),
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       encoding="utf-8", errors="replace", check=True, timeout=120)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to slice audio {source_audio_path} [{start_sec}:{duration_sec}]: {e.stderr}")
        raise RuntimeError(f"FFmpeg audio slice failed: {e.stderr}")


async def generate_scene_tts(db: Session, project: Project, scene: Scene, voice_id: Optional[str] = None) -> float:
    """
    Generates TTS audio for scene narration, probes exact audio duration via FFprobe,
    and updates scene actual_duration and tts_status.
    """
    scene.tts_status = "running"
    scene.error_message = None
    db.commit()

    provider_name = project.active_tts_provider or "elevenlabs"
    from app.services.key_store import has_api_key
    if provider_name == "elevenlabs" and not has_api_key("elevenlabs") and has_api_key("fish_audio"):
        provider_name = "fish_audio"
        project.active_tts_provider = "fish_audio"
        db.commit()

    active_voice = voice_id or scene.voice_id or project.default_voice_id

    audio_dir = get_project_dir(project.id, "audio")
    extension = ".wav" if provider_name == "windows_tts" else ".mp3"
    filename = f"scene_{scene.scene_uuid}{extension}"
    audio_path = str(audio_dir / filename)
    tmp_path = str(audio_dir / f"scene_{scene.scene_uuid}.tmp{extension}")

    logger.info(f"Generating TTS for scene {scene.scene_order} (uuid: {scene.scene_uuid}) in project {project.id}")

    try:
        tts_provider = get_tts_provider(db, provider_name)
        # Pass voice_id if supported by provider
        audio_file = await tts_provider.generate_speech(
            scene.narration,
            voice_id=active_voice,
            save_path=tmp_path,
        )
        if not os.path.isfile(audio_file) or os.path.getsize(audio_file) == 0:
            raise ProviderError('Провайдер озвучки вернул пустой файл.')
        duration = probe_audio_duration(audio_file)
        os.replace(audio_file, audio_path)
        audio_file = audio_path
    except Exception as e:
        logger.error(f"TTS Provider '{provider_name}' failed for scene {scene.scene_uuid}: {e}")
        if ALLOW_MOCK_FALLBACK:
            logger.warning("ALLOW_MOCK_FALLBACK=True: Falling back to Mock TTS.")
            from app.services.providers.mock_provider import MockTTSProvider
            mock_tts = MockTTSProvider()
            audio_file = await mock_tts.generate_speech(scene.narration, save_path=tmp_path)
            duration = probe_audio_duration(audio_file)
            os.replace(audio_file, audio_path)
            audio_file = audio_path
        else:
            scene.tts_status = "error"
            scene.error_message = f"TTS generation failed ({provider_name}): {str(e)}"
            db.commit()
            if isinstance(e, ProviderError):
                raise
            raise ProviderError(scene.error_message) from None
    finally:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)
    
    scene.audio_path = audio_file
    scene.actual_duration = duration
    scene.audio_offset_start = 0.0
    scene.audio_offset_end = duration
    scene.tts_status = "completed"
    if scene.clip_status == "completed":
        scene.clip_status = "outdated"
    scene.error_message = None
    db.commit()

    return duration


def sync_and_split_scenes_post_tts(db: Session, project: Project) -> List[Scene]:
    """Keep text and audio bound to the same scene without word timestamps.

    Splitting audio by equal seconds and narration by equal word counts can
    put different spoken words under the wrong subtitles. A longer scene is
    preferable until a provider supplies exact word timing for safe splits.
    """
    return db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()

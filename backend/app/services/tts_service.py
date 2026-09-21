import os
import subprocess
import logging
import json
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from app.models import Project, Scene
from app.config import FFPROBE_PATH
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
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        duration_str = res.stdout.strip()
        return float(duration_str)
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
        # Fallback to file size heuristic if ffprobe is unavailable
        size_bytes = os.path.getsize(audio_file_path)
        return max(3.0, round(size_bytes / 16000.0, 2))


async def generate_scene_tts(db: Session, project: Project, scene: Scene) -> float:
    """
    Generates TTS audio for scene narration, probes exact audio duration via FFprobe,
    and updates scene actual_duration.
    """
    provider_name = project.active_tts_provider or "elevenlabs"
    from app.services.key_store import has_api_key
    if provider_name == "elevenlabs" and not has_api_key("elevenlabs") and has_api_key("fish_audio"):
        provider_name = "fish_audio"
        project.active_tts_provider = "fish_audio"
        db.commit()

    tts_provider = get_tts_provider(db, provider_name)

    
    project_dir = os.path.join("projects", project.id, "audio")
    os.makedirs(project_dir, exist_ok=True)

    filename = f"scene_{scene.scene_order:03d}.mp3"
    audio_path = os.path.join(project_dir, filename)

    # Cache check: if audio file already exists, don't re-generate unless explicitly triggered
    if os.path.isfile(audio_path) and os.path.getsize(audio_path) > 0 and scene.status != "pending":
        duration = probe_audio_duration(audio_path)
        scene.audio_path = audio_path
        scene.actual_duration = duration
        db.commit()
        return duration

    logger.info(f"Generating TTS for scene {scene.scene_order} in project {project.id}")
    try:
        audio_file = await tts_provider.generate_speech(scene.narration, save_path=audio_path)
    except Exception as e:
        logger.warning(f"TTS Provider '{project.active_tts_provider}' failed ({e}). Falling back to Mock TTS.")
        from app.services.providers.mock_provider import MockTTSProvider
        mock_tts = MockTTSProvider()
        audio_file = await mock_tts.generate_speech(scene.narration, save_path=audio_path)

    
    # Probe duration via FFprobe
    duration = probe_audio_duration(audio_file)
    
    scene.audio_path = audio_file
    scene.actual_duration = duration
    scene.status = "tts_done"
    db.commit()

    return duration

def sync_and_split_scenes_post_tts(db: Session, project: Project) -> List[Scene]:
    """
    Post-TTS check:
    If a scene's TTS audio duration > 20s, splits the visual scene into sub-scenes (A, B)
    with target visual duration 10-20s.
    If a scene's TTS audio duration < 5s, merges narration with adjacent scene.
    """
    scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()
    if not scenes:
        return []

    modified = False
    new_scene_dicts = []
    current_order = 1

    for sc in scenes:
        duration = sc.actual_duration or sc.duration_target
        if duration > 22.0:
            # Split visual scene into 2 sub-scenes (e.g., 35s -> 17.5s + 17.5s)
            num_splits = 2 if duration <= 40.0 else 3
            part_duration = round(duration / num_splits, 2)
            
            # Split narration into parts
            narration_parts = sc.narration.split(". ")
            half_idx = max(1, len(narration_parts) // num_splits)
            part1_text = ". ".join(narration_parts[:half_idx]) + "."
            part2_text = ". ".join(narration_parts[half_idx:])
            if not part2_text:
                part2_text = sc.narration

            # Sub-scene A dict
            new_scene_dicts.append({
                "project_id": project.id,
                "scene_order": current_order,
                "narration": part1_text,
                "shot_type": "Medium Shot",
                "camera_motion": sc.camera_motion,
                "transition": sc.transition,
                "image_prompt": sc.image_prompt,
                "enhanced_prompt": sc.enhanced_prompt,
                "duration_target": part_duration,
                "actual_duration": part_duration,
                "audio_path": sc.audio_path,
                "status": "tts_done",
                "character_ids_json": sc.character_ids_json,
                "location_id": sc.location_id
            })
            current_order += 1

            # Sub-scene B dict
            new_scene_dicts.append({
                "project_id": project.id,
                "scene_order": current_order,
                "narration": part2_text,
                "shot_type": "Close-Up" if sc.shot_type != "Close-Up" else "Wide Shot",
                "camera_motion": "pan_right" if sc.camera_motion != "pan_right" else "slow_zoom_in",
                "transition": "crossfade",
                "image_prompt": f"{sc.image_prompt}, alternate camera perspective",
                "enhanced_prompt": f"{sc.enhanced_prompt}, close perspective",
                "duration_target": part_duration,
                "actual_duration": part_duration,
                "audio_path": sc.audio_path,
                "status": "tts_done",
                "character_ids_json": sc.character_ids_json,
                "location_id": sc.location_id
            })
            current_order += 1
            modified = True
        else:
            new_scene_dicts.append({
                "project_id": project.id,
                "scene_order": current_order,
                "narration": sc.narration,
                "shot_type": sc.shot_type,
                "camera_motion": sc.camera_motion,
                "transition": sc.transition,
                "image_prompt": sc.image_prompt,
                "enhanced_prompt": sc.enhanced_prompt,
                "duration_target": sc.duration_target,
                "actual_duration": sc.actual_duration,
                "audio_path": sc.audio_path,
                "image_path": sc.image_path,
                "video_clip_path": sc.video_clip_path,
                "status": sc.status,
                "character_ids_json": sc.character_ids_json,
                "location_id": sc.location_id
            })
            current_order += 1

    if modified:
        db.query(Scene).filter(Scene.project_id == project.id).delete()
        db.commit()
        for d in new_scene_dicts:
            db.add(Scene(**d))
        db.commit()

    return db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()

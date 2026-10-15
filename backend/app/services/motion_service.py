import os
import subprocess
import logging
import random
import asyncio
from app.services.media_process import run_media_process
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models import Project, Scene
from app.config import FFMPEG_PATH, get_project_dir

logger = logging.getLogger("motion_service")

MOTION_PRESETS = [
    "slow_zoom_in",
    "slow_zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "zoom_pan_left",
    "zoom_pan_right",
    "static"
]

def get_resolution_for_aspect_ratio(aspect_ratio: str = "16:9", quality: str = "1080p") -> Tuple[int, int]:
    """Returns (width, height) for aspect ratio and quality preset."""
    # Older database rows stored concrete dimensions while the UI stores a
    # quality preset. Treat all legacy Full HD dimensions as 1080p.
    normalized_quality = (quality or "1080p").lower()
    is_full_hd = normalized_quality in {
        "1080p", "1920x1080", "1080x1920", "1080x1080"
    }
    if aspect_ratio == "9:16":
        return (1080, 1920) if is_full_hd else (720, 1280)
    elif aspect_ratio == "1:1":
        return (1080, 1080) if is_full_hd else (720, 720)
    else:  # 16:9
        return (1920, 1080) if is_full_hd else (1280, 720)


def get_ffmpeg_zoompan_filter(
    motion: str,
    duration_sec: float,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080
) -> str:
    """
    Constructs an FFmpeg 'zoompan' filter string for the given motion preset and duration.
    """
    total_frames = int(max(duration_sec, 1.0) * fps)
    
    # Scale speed inversely proportional to frame count for smooth slow movement
    z_step = round(0.15 / max(total_frames, 1), 6)
    x_step = round((width * 0.1) / max(total_frames, 1), 4)
    y_step = round((height * 0.1) / max(total_frames, 1), 4)

    if motion == "slow_zoom_in":
        z_expr = f"min(zoom+{z_step},1.15)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "slow_zoom_out":
        z_expr = f"max(1.15-{z_step}*on,1.0)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "pan_left":
        z_expr = "1.10"
        x_expr = f"max(0,iw*0.1-{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "pan_right":
        z_expr = "1.10"
        x_expr = f"min(iw*0.1,0+{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "pan_up":
        z_expr = "1.10"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"max(0,ih*0.1-{y_step}*on)"

    elif motion == "pan_down":
        z_expr = "1.10"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"min(ih*0.1,0+{y_step}*on)"

    elif motion == "zoom_pan_left":
        z_expr = f"min(zoom+{z_step},1.20)"
        x_expr = f"max(0,iw*0.15-{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "zoom_pan_right":
        z_expr = f"min(zoom+{z_step},1.20)"
        x_expr = f"min(iw*0.15,0+{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    else:  # static
        z_expr = "1.0"
        x_expr = "0"
        y_expr = "0"

    return f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={width}x{height}:fps={fps}"

def select_varied_motion(previous_motion: str) -> str:
    """Select a motion preset that is different from the previous scene."""
    candidates = [m for m in MOTION_PRESETS if m != previous_motion and m != "static"]
    return random.choice(candidates)


async def render_single_scene_clip(db: Session, project: Project, scene: Scene) -> str:
    """
    Renders an individual scene .mp4 clip by applying zoompan/motion filter to scene image
    and combining with scene audio. Updates scene.video_clip_path and scene.clip_status.
    """
    if scene.image_status in {"outdated", "error"}:
        raise ValueError("Изображение сцены требует обновления перед рендером клипа.")
    if scene.tts_status in {"outdated", "error"}:
        raise ValueError("Озвучка сцены требует обновления перед рендером клипа.")

    scene.clip_status = "running"
    scene.error_message = None
    db.commit()

    width, height = get_resolution_for_aspect_ratio(project.aspect_ratio or "16:9", project.resolution or "1080p")
    duration = scene.actual_duration or scene.duration_target or 5.0

    clips_dir = get_project_dir(project.id, "clips")
    out_clip_path = str(clips_dir / f"scene_{scene.scene_uuid}.mp4")
    tmp_clip_path = str(clips_dir / f"scene_{scene.scene_uuid}.tmp.mp4")

    # Check if scene image and audio exist
    if not scene.image_path or not os.path.isfile(scene.image_path):
        scene.clip_status = "error"
        scene.error_message = f"Scene image not found at {scene.image_path}"
        db.commit()
        raise FileNotFoundError(scene.error_message)

    has_audio = bool(scene.audio_path and os.path.isfile(scene.audio_path))

    motion = scene.camera_motion or "slow_zoom_in"
    zoompan_filter = get_ffmpeg_zoompan_filter(motion, duration, fps=30, width=width, height=height)

    # FFmpeg command build
    cmd = [FFMPEG_PATH, "-y", "-loop", "1", "-i", scene.image_path]
    if has_audio:
        cmd.extend(["-i", scene.audio_path])
    else:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])

    # Filter complex with padding/scaling to guarantee target aspect ratio
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"{zoompan_filter},"
        f"format=yuv420p"
    )

    cmd.extend([
        "-vf", vf,
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22"
    ])

    cmd.extend(["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"])

    cmd.append(tmp_clip_path)

    logger.info(f"Rendering scene clip {scene.scene_uuid} ({width}x{height}, {duration}s)...")
    try:
        res = await run_media_process(cmd)
        res.check_returncode()
        # Atomic rename after verification
        if os.path.isfile(tmp_clip_path) and os.path.getsize(tmp_clip_path) > 0:
            os.replace(tmp_clip_path, out_clip_path)
        else:
            raise RuntimeError("Generated clip output file is empty")
    except BaseException as e:
        if os.path.isfile(tmp_clip_path):
            os.remove(tmp_clip_path)
        db.rollback()
        scene.clip_status = "cancelled" if isinstance(e, asyncio.CancelledError) else "error"
        scene.error_message = "Рендер отменён" if isinstance(e, asyncio.CancelledError) else "FFmpeg не смог создать клип. Проверьте медиафайлы и установку FFmpeg."
        db.commit()
        raise

    scene.video_clip_path = out_clip_path
    scene.clip_status = "completed"
    scene.error_message = None
    db.commit()

    return out_clip_path

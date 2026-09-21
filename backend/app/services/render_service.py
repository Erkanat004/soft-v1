import os
import subprocess
import logging
import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Project, Scene
from app.config import FFMPEG_PATH, FFPROBE_PATH
from app.services.motion_service import get_ffmpeg_zoompan_filter

logger = logging.getLogger("render_service")

def generate_srt_subtitles(scenes: List[Scene], output_srt_path: str) -> str:
    """
    Generates an SRT subtitle file based on scene narration and timing.
    """
    os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
    
    current_time = 0.0
    entries = []

    def format_time(seconds: float) -> str:
        millis = int((seconds % 1) * 1000)
        total_sec = int(seconds)
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        secs = total_sec % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    for idx, sc in enumerate(scenes, start=1):
        duration = sc.actual_duration or sc.duration_target
        start_str = format_time(current_time)
        end_str = format_time(current_time + duration)
        current_time += duration

        entries.append(f"{idx}\n{start_str} --> {end_str}\n{sc.narration}\n")

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entries))

    return output_srt_path

async def render_scene_clip(scene: Scene, output_clip_path: str) -> str:
    """
    Converts a single scene's image + audio into a video clip with Ken Burns motion.
    """
    os.makedirs(os.path.dirname(output_clip_path), exist_ok=True)
    
    duration = scene.actual_duration or scene.duration_target
    motion_filter = get_ffmpeg_zoompan_filter(scene.camera_motion, duration)

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-loop", "1",
        "-i", scene.image_path,
        "-i", scene.audio_path,
        "-vf", motion_filter,
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "1920k",
        "-shortest",
        output_clip_path
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            logger.error(f"FFmpeg render clip failed: {res.stderr}")
            raise RuntimeError(f"FFmpeg clip render failed: {res.stderr}")
    except FileNotFoundError:
        raise RuntimeError("FFmpeg executable not found. Please install FFmpeg or set FFmpeg path in Settings → API Providers.")


    scene.video_clip_path = output_clip_path
    scene.status = "clip_done"
    return output_clip_path

async def render_full_project_video(
    db: Session,
    project: Project,
    music_path: Optional[str] = None,
    burn_subtitles: bool = True
) -> str:
    """
    Combines all scene video clips into final MP4 with transitions, music audio mixing, and subtitles.
    """
    scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()
    if not scenes:
        raise ValueError("No scenes found to render video.")

    project_dir = os.path.join("projects", project.id)
    clips_dir = os.path.join(project_dir, "preview")
    output_dir = os.path.join(project_dir, "output")
    subtitles_dir = os.path.join(project_dir, "subtitles")
    os.makedirs(clips_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(subtitles_dir, exist_ok=True)

    # 1. Render missing scene clips
    rendered_clips = []
    for sc in scenes:
        if not sc.image_path or not os.path.exists(sc.image_path):
            raise ValueError(f"Scene {sc.scene_order} is missing an image.")
        if not sc.audio_path or not os.path.exists(sc.audio_path):
            raise ValueError(f"Scene {sc.scene_order} is missing TTS audio.")

        clip_path = os.path.join(clips_dir, f"clip_{sc.scene_order:03d}.mp4")
        if not os.path.exists(clip_path) or os.path.getsize(clip_path) == 0:
            clip_path = await render_scene_clip(sc, clip_path)
        rendered_clips.append(clip_path)

    # 2. Generate SRT Subtitles
    srt_path = os.path.join(subtitles_dir, "subtitles.srt")
    generate_srt_subtitles(scenes, srt_path)

    # 3. Concatenate video clips using FFmpeg concat demuxer
    concat_list_path = os.path.join(clips_dir, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for cpath in rendered_clips:
            # Escape path for FFmpeg concat list
            norm_path = os.path.abspath(cpath).replace("\\", "/")
            f.write(f"file '{norm_path}'\n")

    temp_concat_video = os.path.join(output_dir, "concat_raw.mp4")
    concat_cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        temp_concat_video
    ]
    
    logger.info("Concatenating all scene clips...")
    res = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg concat failed: {res.stderr}")

    final_mp4_path = os.path.join(output_dir, "final.mp4")

    # 4. Final render with subtitle burn-in & background music mix if available
    vf_filters = []
    if burn_subtitles and os.path.exists(srt_path):
        escaped_srt = os.path.abspath(srt_path).replace("\\", "/").replace(":", "\\:")
        vf_filters.append(f"subtitles='{escaped_srt}':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2'")

    render_cmd = [FFMPEG_PATH, "-y", "-i", temp_concat_video]
    
    if music_path and os.path.exists(music_path):
        # Mix background music at 8% volume with 3s Fade In and 5s Fade Out
        render_cmd.extend(["-stream_loop", "-1", "-i", music_path])
        filter_complex = "[1:a]volume=0.08,afade=t=in:ss=0:d=3[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]"
        render_cmd.extend(["-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]"])
    else:
        render_cmd.extend(["-map", "0:v", "-map", "0:a"])

    if vf_filters:
        render_cmd.extend(["-vf", ",".join(vf_filters)])

    render_cmd.extend([
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        final_mp4_path
    ])

    logger.info(f"Rendering final output MP4: {final_mp4_path}")
    res = subprocess.run(render_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        logger.error(f"Final MP4 render failed: {res.stderr}")
        raise RuntimeError(f"Final MP4 render failed: {res.stderr}")

    project.status = "completed"
    project.current_stage = "completed"
    db.commit()

    return final_mp4_path

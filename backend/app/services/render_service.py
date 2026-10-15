import os
import json
import hashlib
import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models import Project, Scene
from app.config import FFMPEG_PATH, get_project_dir
from app.services.motion_service import render_single_scene_clip
from app.services.media_process import run_media_process

logger = logging.getLogger("render_service")


def _file_signature(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    try:
        stat = os.stat(path)
        return {"path": path, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    except OSError:
        return {"path": path, "missing": True}


def render_fingerprint(
    project: Project,
    scenes: List[Scene],
    burn_subtitles: bool = True,
    music_path: Optional[str] = None,
    music_volume: Optional[float] = None,
    enable_audio_ducking: bool = True,
) -> str:
    """Fingerprint the inputs that determine the published MP4."""
    effective_music = music_path or project.bg_music_path
    effective_volume = music_volume if music_volume is not None else (project.bg_music_volume or 0.08)
    inputs = {
        "format": 4,
        "aspect_ratio": project.aspect_ratio,
        "resolution": project.resolution,
        "subtitle_settings": project.subtitle_settings_json if burn_subtitles else None,
        "burn_subtitles": burn_subtitles,
        "music": _file_signature(effective_music),
        "music_volume": effective_volume if effective_music else None,
        "audio_ducking": enable_audio_ducking if effective_music else None,
        "scenes": [
            {
                "uuid": scene.scene_uuid,
                "order": scene.scene_order,
                "narration": scene.narration if burn_subtitles else None,
                "duration": scene.actual_duration or scene.duration_target or 5.0,
                "motion": scene.camera_motion,
                "image_status": scene.image_status,
                "tts_status": scene.tts_status,
                "clip_status": scene.clip_status,
                "image": _file_signature(scene.image_path),
                "audio": _file_signature(scene.audio_path),
                "clip": _file_signature(scene.video_clip_path),
            }
            for scene in scenes
        ],
    }
    payload = json.dumps(inputs, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_render_status(db: Session, project: Project) -> dict:
    output_dir = get_project_dir(project.id, "output")
    final_path = output_dir / "final.mp4"
    manifest_path = output_dir / "final.json"
    output_signature = _file_signature(str(final_path))
    exists = bool(output_signature and output_signature.get("size", 0) > 0)
    current = False
    if exists and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()
            current = bool(scenes) and (
                manifest.get("fingerprint") == render_fingerprint(project, scenes)
                and manifest.get("output") == output_signature
            )
        except (OSError, ValueError, TypeError, AttributeError):
            current = False
    return {"exists": exists, "current": current}

def generate_srt_subtitles(scenes: List[Scene], output_srt_path: str) -> str:
    """
    Time short subtitle cues within each scene instead of showing a whole
    paragraph over the picture for its entire duration.
    """
    os.makedirs(os.path.dirname(output_srt_path), exist_ok=True)
    
    current_time = 0.0
    entries = []

    def format_time(seconds: float) -> str:
        total_millis = round(seconds * 1000)
        total_sec, millis = divmod(total_millis, 1000)
        hours = total_sec // 3600
        minutes = (total_sec % 3600) // 60
        secs = total_sec % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    for sc in scenes:
        duration = sc.actual_duration or sc.duration_target or 5.0
        words = sc.narration.split()
        if words:
            for word_start in range(0, len(words), 8):
                word_end = min(word_start + 8, len(words))
                start = current_time + duration * word_start / len(words)
                end = current_time + duration * word_end / len(words)
                entries.append(
                    f"{len(entries) + 1}\n{format_time(start)} --> {format_time(end)}\n"
                    f"{' '.join(words[word_start:word_end])}\n"
                )
        current_time += duration

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entries))

    return output_srt_path


async def render_full_project_video(
    db: Session,
    project: Project,
    music_path: Optional[str] = None,
    music_volume: Optional[float] = None,
    burn_subtitles: bool = True,
    enable_audio_ducking: bool = True,
) -> str:
    """
    Combines all scene video clips into final MP4 with transitions, background music mixing, and subtitles.
    """
    scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()
    if not scenes:
        raise ValueError("No scenes found to render video.")
    stale = [sc.scene_order for sc in scenes if sc.image_status in {"outdated", "error"}
             or sc.tts_status in {"outdated", "error"}]
    if stale:
        raise ValueError(f"Обновите изображение или озвучку сцен {', '.join(map(str, stale))} перед экспортом.")
    missing_images = [sc.scene_order for sc in scenes if not sc.image_path or not os.path.isfile(sc.image_path)]
    if missing_images:
        raise ValueError(f"Отсутствуют изображения сцен {', '.join(map(str, missing_images))}.")
    missing_audio = [sc.scene_order for sc in scenes if sc.tts_status == "completed"
                     and (not sc.audio_path or not os.path.isfile(sc.audio_path))]
    if missing_audio:
        raise ValueError(f"Отсутствует озвучка сцен {', '.join(map(str, missing_audio))}.")

    clips_dir = get_project_dir(project.id, "clips")
    output_dir = get_project_dir(project.id, "output")
    subtitles_dir = get_project_dir(project.id, "subtitles")

    # 1. Ensure all scene clips are rendered and up-to-date
    rendered_clips = []
    for sc in scenes:
        if sc.clip_status != "completed" or not sc.video_clip_path or not os.path.isfile(sc.video_clip_path):
            clip_path = await render_single_scene_clip(db, project, sc)
            rendered_clips.append(clip_path)
        else:
            rendered_clips.append(sc.video_clip_path)

    # 2. Generate SRT Subtitles
    srt_path = str(subtitles_dir / "subtitles.srt")
    generate_srt_subtitles(scenes, srt_path)

    # 3. Concatenate video clips using FFmpeg concat demuxer
    concat_list_path = str(clips_dir / "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for cpath in rendered_clips:
            norm_path = os.path.abspath(cpath).replace("\\", "/")
            f.write(f"file '{norm_path}'\n")

    temp_concat_video = str(output_dir / "concat_raw.tmp.mp4")
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
    final_mp4_path = str(output_dir / "final.mp4")
    tmp_final_mp4_path = str(output_dir / "final.tmp.mp4")

    # 4. Subtitle styling and music configuration
    vf_filters = []
    if burn_subtitles and os.path.exists(srt_path):
        escaped_srt = os.path.abspath(srt_path).replace("\\", "/").replace(":", "\\:")

        # Parse subtitle settings if present
        font_size = 13 if (project.resolution or "1080p") == "720p" else 18
        primary_color = "&H00FFFFFF"
        if project.subtitle_settings_json:
            try:
                sub_cfg = json.loads(project.subtitle_settings_json)
                font_size = max(10, min(40, int(sub_cfg.get("font_size", font_size))))
                if sub_cfg.get("color") == "yellow":
                    primary_color = "&H0000FFFF"
            except Exception:
                pass

        vf_filters.append(
            f"subtitles='{escaped_srt}':force_style='FontSize={font_size},PrimaryColour={primary_color},"
            f"OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV=60'"
        )

    render_cmd = [FFMPEG_PATH, "-y", "-i", temp_concat_video]
    
    bg_music = music_path or project.bg_music_path
    bg_vol = music_volume if music_volume is not None else (project.bg_music_volume or 0.08)

    if bg_music and os.path.exists(bg_music):
        render_cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        if enable_audio_ducking:
            # Audio ducking: dynamically attenuate background music when voice is present
            filter_complex = (
                f"[1:a]volume={bg_vol},afade=t=in:ss=0:d=3[music];"
                f"[music][0:a]sidechaincompress=threshold=0.03:ratio=5:attack=100:release=800[ducked];"
                f"[0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
        else:
            filter_complex = f"[1:a]volume={bg_vol},afade=t=in:ss=0:d=3[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]"
        render_cmd.extend(["-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]"])
    else:
        render_cmd.extend(["-map", "0:v", "-map", "0:a"])

    if vf_filters:
        render_cmd.extend(["-vf", ",".join(vf_filters)])

    render_cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        tmp_final_mp4_path
    ])

    try:
        res = await run_media_process(concat_cmd)
        if res.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {res.stderr}")

        logger.info(f"Rendering final output MP4: {final_mp4_path}")
        res = await run_media_process(render_cmd)
        if res.returncode != 0:
            logger.error(f"Final MP4 render failed: {res.stderr}")
            raise RuntimeError(f"Final MP4 render failed: {res.stderr}")

        if not os.path.isfile(tmp_final_mp4_path) or os.path.getsize(tmp_final_mp4_path) == 0:
            raise RuntimeError("FFmpeg returned an empty output file")

        # Keep the previous export until the new one is complete. A missing or
        # old manifest always makes the MP4 appear stale in the UI.
        os.replace(tmp_final_mp4_path, final_mp4_path)
        manifest_path = output_dir / "final.json"
        tmp_manifest_path = output_dir / "final.tmp.json"
        fingerprint = render_fingerprint(project, scenes, burn_subtitles, music_path, music_volume, enable_audio_ducking)
        try:
            tmp_manifest_path.write_text(json.dumps({
                "fingerprint": fingerprint,
                "output": _file_signature(final_mp4_path),
            }), encoding="utf-8")
            os.replace(tmp_manifest_path, manifest_path)
        finally:
            if tmp_manifest_path.exists():
                tmp_manifest_path.unlink()
    finally:
        for temporary_path in (temp_concat_video, tmp_final_mp4_path):
            if os.path.isfile(temporary_path):
                os.remove(temporary_path)

    project.status = "completed"
    project.current_stage = "completed"
    db.commit()

    return final_mp4_path

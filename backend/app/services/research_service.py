"""Offline research helpers. No provider calls and no reference media is retained."""
import json
import re
import statistics
from pathlib import Path

from app.config import FFMPEG_PATH, FFPROBE_PATH
from app.services.media_process import run_media_process


async def inspect_reference_video(path: Path) -> dict:
    probe = await run_media_process([
        FFPROBE_PATH, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,width,height", "-of", "json", str(path),
    ], timeout=20)
    if probe.returncode != 0:
        raise ValueError("Не удалось прочитать видео. Проверьте формат файла.")
    try:
        metadata = json.loads(probe.stdout)
        duration = float(metadata["format"]["duration"])
        video = next(item for item in metadata["streams"] if item["codec_type"] == "video")
        width, height = int(video["width"]), int(video["height"])
    except (KeyError, ValueError, TypeError, StopIteration) as exc:
        raise ValueError("В файле нет поддерживаемого видеопотока.") from exc
    if duration <= 0 or width <= 0 or height <= 0:
        raise ValueError("Видео имеет некорректную длительность или размер кадра.")

    analyzed_seconds = min(duration, 180.0)
    # Sampling is intentionally coarse: this is a structural reference, not a
    # frame extractor or a downloader for source footage.
    scan = await run_media_process([
        FFMPEG_PATH, "-hide_banner", "-nostats", "-loglevel", "info", "-i", str(path),
        "-t", str(analyzed_seconds), "-vf", "fps=2,select=gt(scene\\,0.30),showinfo",
        "-an", "-f", "null", "-",
    ], timeout=120)
    if scan.returncode == 0:
        cut_times = [float(value) for value in re.findall(r"pts_time:([0-9.]+)", scan.stderr)]
        # showinfo emits one timestamp for each selected frame.
        cut_times = sorted(set(round(value, 1) for value in cut_times if 0 < value <= analyzed_seconds))
    else:
        cut_times = []
    cuts_per_minute = round(len(cut_times) * 60 / analyzed_seconds, 1)
    pace = "недоступен" if scan.returncode != 0 else "спокойный" if cuts_per_minute < 8 else "средний" if cuts_per_minute < 18 else "быстрый"
    return {
        "duration_seconds": round(duration, 1),
        "width": width,
        "height": height,
        "analyzed_seconds": round(analyzed_seconds, 1),
        "detected_cuts": len(cut_times),
        "cuts_per_minute": cuts_per_minute,
        "pace": pace,
        "cut_times": cut_times[:30],
        "cut_detection_available": scan.returncode == 0,
    }


def analyze_niche(videos: list[dict]) -> dict:
    """Rank user-entered public metrics without claiming proprietary search volume."""
    rows = []
    for item in videos:
        title = str(item.get("title", "")).strip()
        views = int(item.get("views", 0))
        age_days = float(item.get("age_days", 0))
        if not title or views < 0 or age_days <= 0:
            raise ValueError("Для каждого ролика нужны название, просмотры и возраст больше нуля.")
        rows.append({"title": title, "views": views, "age_days": age_days,
                     "views_per_day": round(views / age_days, 1)})
    if not rows:
        raise ValueError("Добавьте хотя бы один ролик для анализа.")
    median = statistics.median(item["views_per_day"] for item in rows)
    for item in rows:
        item["relative_to_median"] = round(item["views_per_day"] / median, 2) if median else None
    rows.sort(key=lambda item: item["views_per_day"], reverse=True)
    return {"sample_size": len(rows), "median_views_per_day": round(median, 1), "ranked_videos": rows}

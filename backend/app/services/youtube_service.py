"""YouTube Metadata Pack generation: viral titles, SEO description, chapters, and tags."""
import re
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Project, Scene
from app.services.providers.factory import get_text_provider
from app.services.key_store import has_api_key

logger = logging.getLogger("youtube_service")


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS or HH:MM:SS format."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def generate_scene_chapters(scenes: List[Scene]) -> List[Dict[str, Any]]:
    """Calculate cumulative timestamps and titles for YouTube chapters."""
    chapters = []
    cumulative_sec = 0.0

    for idx, sc in enumerate(scenes):
        timestamp_str = format_timestamp(cumulative_sec)
        
        # Derive a concise chapter name from narration
        narration = (sc.narration or "").strip()
        first_sentence = re.split(r"[.!?\n]", narration)[0].strip()
        words = first_sentence.split()
        
        if idx == 0:
            title = "Начало истории"
        elif idx == len(scenes) - 1:
            title = "Финал и развязка"
        elif len(words) <= 5 and first_sentence:
            title = first_sentence
        elif len(words) > 5:
            title = " ".join(words[:5]) + "..."
        else:
            title = f"Часть {idx + 1}"

        chapters.append({
            "order": sc.scene_order,
            "timestamp": timestamp_str,
            "seconds": cumulative_sec,
            "title": title
        })

        # Advance by actual or target duration
        duration = sc.actual_duration or sc.duration_target or 6.0
        cumulative_sec += duration

    return chapters


async def generate_youtube_pack(db: Session, project: Project, allow_ai: bool = False) -> Dict[str, Any]:
    """Generates complete YouTube metadata pack using AI or smart offline fallback."""
    scenes = db.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.scene_order).all()
    chapters_data = generate_scene_chapters(scenes)
    chapters_text = "\n".join(f"{ch['timestamp']} {ch['title']}" for ch in chapters_data)

    story_type = project.story_type or "Истории"
    topic = project.name or project.topic_or_script[:80].strip()
    language = project.language or "Russian"
    is_russian = "rus" in language.lower() or bool(re.search(r"[А-Яа-яЁё]", topic))
    is_history = bool(re.search(r"histor|истори|биограф|документ", story_type, re.IGNORECASE))

    # Check if an external text LLM is configured and available
    ai_available = (
        (project.active_text_provider == "gemini" and has_api_key("gemini"))
        or (project.active_text_provider in ["openai", "openrouter"] and has_api_key(project.active_text_provider))
        or (has_api_key("gemini") or has_api_key("openrouter"))
    )

    titles = []
    description_hook = ""
    tags_list = []

    if allow_ai and ai_available:
        try:
            provider = get_text_provider(db, project.active_text_provider or "auto_text")
            prompt = (
                f"Создай маркетинговый пак для публикации видео на YouTube на основе истории.\n"
                f"Тема: {project.name or topic}\n"
                f"Жанр: {story_type}\n"
                f"Текст сценария (фрагмент): {project.topic_or_script[:1500]}\n\n"
                f"Верни СТРОГО валидный JSON в формате:\n"
                f"{{\n"
                f'  "titles": ["5 кликбейтных, цепляющих заголовков для YouTube"],\n'
                f'  "description_hook": "Интригующий текст описания из 2-3 предложений для привлечения внимания",\n'
                f'  "tags": ["10-15 релевантных тегов для поиска через запятую"]\n'
                f"}}"
            )
            raw = await provider.generate_text(prompt)
            # Extract JSON block
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                titles = parsed.get("titles", [])
                description_hook = parsed.get("description_hook", "")
                tags_list = parsed.get("tags", [])
        except Exception as err:
            logger.warning("AI YouTube pack generation failed, falling back to heuristic: %s", err)

    # Heuristic fallback if AI was unavailable or failed
    if not titles:
        if is_russian:
            if is_history:
                titles = [f"{topic} — путь к трону и цена власти", f"{topic}: главные события и решения",
                          f"Как сложилась судьба: {topic}", f"{topic} — исторический разбор",
                          f"{topic}: жизнь, политика и наследие"]
                description_hook = f"Исторический рассказ на тему «{topic}». Разбираем события, контекст и спорные вопросы."
                tags_list = ["история", "биография", "исторический разбор", topic.lower()]
            else:
                titles = [f"{topic} — ключевые события", f"Что произошло: {topic}",
                          f"{topic} | Полная история", f"{topic}: главные повороты",
                          f"{topic} ({story_type})"]
                description_hook = f"Видео на тему «{topic}». Основные события и детали — в этом выпуске."
                tags_list = ["истории", "рассказы", story_type.lower(), topic.lower()]
        else:
            titles = [f"{topic} — Key Events", f"The Story of {topic}",
                      f"{topic}: Context and Turning Points", f"Understanding {topic}",
                      f"{topic} | {story_type}"]
            description_hook = f"Explore {topic}: the key events, context, and open questions."
            tags_list = ["history", "biography", topic.lower()] if is_history else ["stories", story_type.lower(), topic.lower()]

    # Assemble structured description
    disclaimer = (
        "Проверьте факты и источники перед публикацией."
        if is_russian else
        "Verify facts and sources before publishing."
    )
    hashtags = ("#история #биография" if is_history else "#истории") if is_russian else ("#history #biography" if is_history else "#stories")

    full_description = (
        f"{description_hook}\n\n"
        f"⏱️ Таймкоды / Chapters:\n"
        f"{chapters_text}\n\n"
        f"{disclaimer}\n\n"
        f"🔔 Подписывайтесь на канал и ставьте лайк, чтобы не пропустить новые выпуски!\n\n"
        f"{hashtags}"
    )

    tags_str = ", ".join(tags_list)

    return {
        "project_id": project.id,
        "titles": titles,
        "description": full_description,
        "chapters": chapters_text,
        "chapters_detail": chapters_data,
        "tags": tags_str,
        "formatted_text": (
            f"=== ЗАГОЛОВКИ (TITLES) ===\n"
            + "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))
            + f"\n\n=== ОПИСАНИЕ (DESCRIPTION) ===\n{full_description}\n\n"
            + f"=== ТЕГИ (TAGS) ===\n{tags_str}\n"
        )
    }

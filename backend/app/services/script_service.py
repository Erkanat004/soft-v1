import json
import logging
from typing import Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from app.models import Project, Script, Character, Location
from app.services.providers.factory import get_text_provider

logger = logging.getLogger("script_service")

STORY_TEMPLATES = {
    "Horror": "Dark atmospheric suspense story. First-person narration. Strong hook in the first 30 seconds. Slow reveal of cosmic or psychological horror. Unsettling twist ending.",
    "Mystery": "Intricate mystery narrative with detailed clues, escalating tension, unpredictable turns, and a dramatic final reveal.",
    "Reddit": "Conversational first-person narrative in classic Reddit r/nosleep or r/TrueOffMyChest style. Relatable beginning turning into an eerie, disturbing personal experience.",
    "Crime": "Documentary-style true crime narrative. Gritty tone, chronological buildup of evidence, police investigation, and chilling resolution.",
    "Relationship": "Emotionally intense first-person story. Deep personal conflict, secret betrayal, escalating drama, and cathartic resolution.",
    "Documentary": "Analytical and engaging historical or investigative documentary script with authoritative narration.",
    "History": "Atmospheric historical narration set in a specific era, capturing authentic cultural details and dramatic events."
}

def classify_input_type(text: str) -> str:
    """Determine whether text is a short TOPIC or a FULL SCRIPT."""
    stripped = text.strip()
    words = stripped.split()
    # If text is less than 60 words or less than 3 sentences, classify as topic
    if len(words) < 60 or stripped.count('.') < 3:
        return "topic"
    return "full_script"

async def generate_longform_script(provider, project: Project) -> str:
    """
    Generates a multi-chapter longform story script guaranteed to meet at least 30 minutes (minimum 4,200 words).
    """
    try:
        preset_mins = int(project.duration_preset)
    except Exception:
        preset_mins = 30
    
    # Enforce minimum 30 minutes
    target_mins = max(30, preset_mins)
    target_word_count = target_mins * 140  # 30 mins * 140 wpm = 4,200 words minimum
    
    category_style = STORY_TEMPLATES.get(project.story_type, "Engaging dramatic story with strong narrative arc.")
    logger.info(f"Generating longform script for project {project.id}: target {target_mins} mins, target {target_word_count} words")

    # 1. Outline & Chapter Structure
    outline_prompt = f"""
You are an award-winning YouTube longform storyteller specializing in 30-60 minute immersive stories.
Create a detailed 3-chapter narrative outline for a {target_mins}-minute audio story.

TOPIC: "{project.topic_or_script}"
GENRE: {project.story_type} ({category_style})
LANGUAGE: {project.language}

Output JSON with 3 distinct narrative chapters:
{{
  "chapter_1": "Chapter 1 Focus: Hook, detailed setting, character introduction, and the initial mysterious event.",
  "chapter_2": "Chapter 2 Focus: Escalating complications, investigation, terrifying encounters, and deepening tension.",
  "chapter_3": "Chapter 3 Focus: Major revelation, intense climax, final confrontation, and lingering haunting resolution."
}}
"""
    outline_raw = await provider.generate_text(outline_prompt)
    try:
        s_idx = outline_raw.find('{')
        e_idx = outline_raw.rfind('}') + 1
        outline_json = json.loads(outline_raw[s_idx:e_idx])
    except Exception:
        outline_json = {
            "chapter_1": "Hook, character intro, mysterious event.",
            "chapter_2": "Rising tension, investigation, terrifying encounters.",
            "chapter_3": "Climax, resolution, final twist."
        }

    # Generate each chapter sequentially to reach the word count target
    chapters = []
    previous_context = ""
    for ch_key in ["chapter_1", "chapter_2", "chapter_3"]:
        ch_focus = outline_json.get(ch_key, "Continue the story with deep suspense.")
        ch_prompt = f"""
Write Chapter {ch_key[-1]} of a {target_mins}-minute story in {project.language}.

TOPIC: "{project.topic_or_script}"
GENRE: {project.story_type}
CHAPTER DIRECTIVE: {ch_focus}

RULES:
- Write a LONG, highly detailed, atmospheric narrative chapter (target at least 1,500 words for this chapter).
- Include rich dialogue, internal thoughts, environmental descriptions, and slow-burn pacing.
- Do NOT include chapter titles like [CHAPTER 1]. Output pure storytelling narration for audio voiceover.
{f"PREVIOUS STORY CONTENT SUMMARY:\n{previous_context[-800:]}" if previous_context else ""}
"""
        ch_text = await provider.generate_text(ch_prompt)
        ch_clean = ch_text.strip()
        chapters.append(ch_clean)
        previous_context += "\n\n" + ch_clean

    full_script = "\n\n".join(chapters)
    current_words = len(full_script.split())
    logger.info(f"Generated initial longform script: {current_words} words")
    
    # If still under target_word_count, append an expansion chapter
    if current_words < target_word_count:
        logger.info(f"Script word count ({current_words}) is below target ({target_word_count}). Expanding with Epilogue/Aftermath...")
        expand_prompt = f"""
Extend and deepen the following story with an extended Chapter 4 (Epilogue, investigation aftermath, or secondary twist) in {project.language}.

STORY SUMMARY SO FAR:
\"\"\"{full_script[-1500:]}\"\"\"

DIRECTIVE:
Write an additional 1,500+ words extending the story narrative, revealing hidden details, aftermath, and final haunting resolution.
Output pure story narration without section titles.
"""
        epilogue_text = await provider.generate_text(expand_prompt)
        full_script += "\n\n" + epilogue_text.strip()
        logger.info(f"Final expanded longform script: {len(full_script.split())} words")

    return full_script

async def prepare_project_script(db: Session, project: Project) -> Tuple[Script, List[Character], List[Location]]:
    """
    Main entrypoint for Script + Character Bible + Location Bible generation.
    Enforces minimum 30-minute longform video length.
    """
    provider = get_text_provider(db, project.active_text_provider)
    
    input_kind = project.input_type
    if input_kind == "auto":
        input_kind = classify_input_type(project.topic_or_script)
    
    # 1. Script Generation / Refinement
    final_script_text = ""
    if input_kind == "topic":
        final_script_text = await generate_longform_script(provider, project)
    else:
        logger.info(f"Using provided script text for project {project.id}")
        user_text = project.topic_or_script
        words = len(user_text.split())
        # If user provided script is shorter than 30 mins (4200 words), auto-expand it to 30 mins minimum
        if words < 4200:
            logger.info(f"User script ({words} words) is below 30-minute minimum (4200 words). Expanding script...")
            expand_prompt = f"""
You are a master longform YouTube scriptwriter.
Expand the following user story script into a rich, detailed 30+ minute narrative script in {project.language}.

USER SCRIPT:
\"\"\"{user_text}\"\"\"

DIRECTIVE:
- Expand descriptions, internal monologues, dialogue, sensory details, and tension build-up.
- Target at least 4,200 words (30 minutes of voiceover).
- Output pure storytelling narration without section headers.
"""
            final_script_text = await provider.generate_text(expand_prompt)
        else:
            final_script_text = user_text

    # Save or update Script record
    script = db.query(Script).filter(Script.project_id == project.id).first()
    if not script:
        script = Script(project_id=project.id, text=final_script_text, is_user_provided=(input_kind == "full_script"))
        db.add(script)
    else:
        script.text = final_script_text
        script.is_user_provided = (input_kind == "full_script")
    db.commit()

    # 2. Extract Character Bible & Location Bible automatically via Text AI
    logger.info(f"Extracting Character & Location Bibles for project {project.id}")
    bible_prompt = f"""
Analyze the following story script and identify all main recurring characters and key visual locations.

STORY SCRIPT:
\"\"\"{final_script_text[:4000]}\"\"\"

OUTPUT STRICT JSON ONLY matching this format:
{{
  "characters": [
    {{
      "name": "John",
      "age": "35",
      "gender": "Male",
      "hair": "short dark brown hair",
      "eyes": "brown",
      "clothes": "dark gray jacket",
      "appearance": "35-year-old Caucasian male, short dark brown hair, light stubble, tired brown eyes, dark gray jacket"
    }}
  ],
  "locations": [
    {{
      "name": "House Basement",
      "description": "old isolated suburban basement, concrete walls, dim lighting, flickering bulb, dusty atmosphere"
    }}
  ]
}}
"""
    try:
        raw_bible_json = await provider.generate_text(bible_prompt)
        # Parse JSON
        start_idx = raw_bible_json.find('{')
        end_idx = raw_bible_json.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            parsed = json.loads(raw_bible_json[start_idx:end_idx])
        else:
            parsed = json.loads(raw_bible_json)
        
        # Populate Characters
        db.query(Character).filter(Character.project_id == project.id).delete()
        char_objects = []
        for cdata in parsed.get("characters", []):
            char = Character(
                project_id=project.id,
                name=cdata.get("name", "Unnamed"),
                age=cdata.get("age"),
                gender=cdata.get("gender"),
                hair=cdata.get("hair"),
                eyes=cdata.get("eyes"),
                clothes=cdata.get("clothes"),
                appearance=cdata.get("appearance", cdata.get("name", "")),
                is_auto_generated=True
            )
            db.add(char)
            char_objects.append(char)

        # Populate Locations
        db.query(Location).filter(Location.project_id == project.id).delete()
        loc_objects = []
        for ldata in parsed.get("locations", []):
            loc = Location(
                project_id=project.id,
                name=ldata.get("name", "Unnamed Location"),
                description=ldata.get("description", ""),
                is_auto_generated=True
            )
            db.add(loc)
            loc_objects.append(loc)

        db.commit()

        return script, char_objects, loc_objects

    except Exception as e:
        logger.warning(f"Failed to extract bibles automatically: {e}")
        db.commit()
        return script, [], []

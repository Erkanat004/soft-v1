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

async def generate_script_from_topic(provider, project: Project) -> str:
    """
    Generates a story script matching the user's requested target duration preset (e.g. 1, 5, 10, 20, 30, 40, 60 min).
    """
    try:
        preset_mins = float(project.duration_preset)
    except Exception:
        preset_mins = 10.0
    
    # Target 140 words per minute of narration
    target_words = max(80, int(preset_mins * 140))
    category_style = STORY_TEMPLATES.get(project.story_type, "Engaging dramatic story with strong narrative arc.")
    logger.info(f"Generating script for project {project.id}: target {preset_mins} mins (~{target_words} words)")

    prompt = f"""
You are an expert storyteller and YouTube scriptwriter.
Create a complete, deeply immersive story script based on the following input:

TOPIC: "{project.topic_or_script}"
GENRE/TYPE: {project.story_type} ({category_style})
TARGET DURATION: {preset_mins} minutes (target approx {target_words} words)
LANGUAGE: {project.language}
VISUAL STYLE: {project.visual_style}
CREATIVE BRIEF: {project.creative_brief or 'None'}

STORY STRUCTURE RULES:
- Include a captivating HOOK in the first 2 sentences.
- Develop rich narrative tension suitable for the target duration.
- Do NOT include section titles like [HOOK] or [INTRO] in the text. Output pure storytelling narration.
- Write vivid descriptive narration suitable for rich voiceover audio.
- If a creative brief describes a reference, use only abstract observations such as pace and structure.
- Do not reproduce distinctive wording, characters, scenes, or the sequence of a reference work.
- Make the narration original to the user's topic and perspective.
"""
    return await provider.generate_text(prompt)

async def enhance_script_draft(db: Session, project: Project, instruction: str = "") -> str:
    """
    Generates a new enhanced version of the current script text for user review (accept/discard).
    Does NOT overwrite active Script.text automatically.
    """
    provider = get_text_provider(db, project.active_text_provider)
    script = db.query(Script).filter(Script.project_id == project.id).first()
    current_text = script.text if script else project.topic_or_script

    prompt = f"""
You are an expert story editor.
Refine and enhance the following story script in {project.language}.

INSTRUCTION: {instruction or "Improve atmospheric tension, dialogue, sensory details, and narrative pacing."}

CURRENT SCRIPT:
\"\"\"{current_text}\"\"\"

Output pure storytelling narration without section titles or metadata.
"""
    return await provider.generate_text(prompt)

async def prepare_project_script(db: Session, project: Project) -> Tuple[Script, List[Character], List[Location]]:
    """
    Main entrypoint for Script + Character Bible + Location Bible generation.
    Supports user scripts 100% as-is or topic-based script generation without forced 30-min minimum.
    """
    project_id = project.id
    existing = db.query(Script).filter(Script.project_id == project_id).first()
    if existing and existing.text.strip():
        return (existing,
                db.query(Character).filter(Character.project_id == project_id).all(),
                db.query(Location).filter(Location.project_id == project_id).all())
    provider = get_text_provider(db, project.active_text_provider)

    input_kind = project.input_type
    if input_kind == "auto":
        input_kind = classify_input_type(project.topic_or_script)
    
    # 1. Script Generation / Refinement
    final_script_text = ""
    if input_kind == "topic":
        final_script_text = await generate_script_from_topic(provider, project)
    else:
        logger.info(f"Using provided script text as-is for project {project.id}")
        final_script_text = project.topic_or_script

    # Save or update Script record
    script = db.query(Script).filter(Script.project_id == project.id).first()
    if not script:
        script = Script(project_id=project.id, text=final_script_text, is_user_provided=(input_kind == "full_script"))
        db.add(script)
    else:
        script.text = final_script_text
        script.is_user_provided = (input_kind == "full_script")
    db.commit()

    if project.active_image_provider == "local_cards":
        # Visual cards do not use character/location bibles. Avoid a second
        # free-tier model call that can fail or consume the remaining quota.
        return script, [], []

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
        db.rollback()
        return script, [], []

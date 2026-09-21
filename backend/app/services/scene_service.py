import json
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import Project, Scene, Character, Location
from app.config import GLOBAL_VISUAL_STYLE_DEFAULT
from app.services.providers.factory import get_text_provider

logger = logging.getLogger("scene_service")

SHOT_TYPES = [
    "Establishing Shot", "Wide Shot", "Medium Shot", "Close-Up",
    "Extreme Close-Up", "Over-the-Shoulder", "POV", "Low Angle",
    "High Angle", "Detail Shot"
]

MOTION_PRESETS = [
    "slow_zoom_in", "slow_zoom_out", "pan_left", "pan_right",
    "pan_up", "pan_down", "zoom_pan_left", "zoom_pan_right"
]

async def decompose_script_to_scenes(db: Session, project: Project, script_text: str) -> List[Scene]:
    """
    Splits story script into visual scenes with narration, prompts, character/location injection, and shot variation.
    """
    provider = get_text_provider(db, project.active_text_provider)

    # Fetch characters & locations for context
    chars = db.query(Character).filter(Character.project_id == project.id).all()
    locs = db.query(Location).filter(Location.project_id == project.id).all()

    char_summary = "\n".join([f"- CHARACTER '{c.name}': {c.appearance}" for c in chars])
    loc_summary = "\n".join([f"- LOCATION '{l.name}': {l.description}" for l in locs])

    global_style = project.global_visual_style or GLOBAL_VISUAL_STYLE_DEFAULT

    prompt = f"""
You are an expert storyboarding director and cinematic prompt engineer.
Break the following story script into a sequence of small visual scenes (target duration 10 to 20 seconds of spoken narration per scene).

KNOWN CHARACTERS:
{char_summary or "None"}

KNOWN LOCATIONS:
{loc_summary or "None"}

GLOBAL VISUAL STYLE:
{global_style}

SHOT TYPE ROTATION (Vary across scenes, do NOT repeat the same framing 3 times in a row):
Establishing Shot, Wide Shot, Medium Shot, Close-Up, Extreme Close-Up, Over-the-Shoulder, POV, Low Angle, High Angle, Detail Shot.

STORY SCRIPT:
\"\"\"{script_text}\"\"\"

OUTPUT STRICT JSON ONLY matching this format:
{{
  "scenes": [
    {{
      "scene_order": 1,
      "narration": "Exact line of story narration...",
      "shot_type": "Establishing Shot",
      "character_names": ["John"],
      "location_name": "House Basement",
      "visual_prompt": "Cinematic wide shot of an old suburban house at midnight, dark windows, warm porch light, high detail"
    }}
  ]
}}
"""

    raw_response = await provider.generate_text(prompt)
    
    start_idx = raw_response.find('{')
    end_idx = raw_response.rfind('}') + 1
    if start_idx != -1 and end_idx != 0:
        parsed = json.loads(raw_response[start_idx:end_idx])
    else:
        parsed = json.loads(raw_response)

    db.query(Scene).filter(Scene.project_id == project.id).delete()
    
    scenes = []
    char_map = {c.name.lower(): c for c in chars}
    loc_map = {l.name.lower(): l for l in locs}

    raw_scenes = parsed.get("scenes", [])
    motion_index = 0

    for idx, sdata in enumerate(raw_scenes, start=1):
        narration = sdata.get("narration", "").strip()
        if not narration:
            continue

        shot_type = sdata.get("shot_type", SHOT_TYPES[idx % len(SHOT_TYPES)])
        motion = MOTION_PRESETS[motion_index % len(MOTION_PRESETS)]
        motion_index += 1

        # Resolve characters & locations
        c_names = sdata.get("character_names", [])
        c_objs = [char_map[cn.lower()] for cn in c_names if cn.lower() in char_map]
        c_ids = [c.id for c in c_objs]

        l_name = sdata.get("location_name", "")
        l_obj = loc_map.get(l_name.lower()) if l_name else None

        # Build enhanced prompt
        base_visual = sdata.get("visual_prompt", narration)
        
        char_desc_str = ", ".join([c.appearance for c in c_objs])
        loc_desc_str = l_obj.description if l_obj else ""

        prompt_parts = [
            f"{shot_type}",
            base_visual
        ]
        if char_desc_str:
            prompt_parts.append(f"featuring {char_desc_str}")
        if loc_desc_str:
            prompt_parts.append(f"set in {loc_desc_str}")
        prompt_parts.append(global_style)

        full_prompt = ", ".join(prompt_parts)

        scene = Scene(
            project_id=project.id,
            scene_order=idx,
            narration=narration,
            shot_type=shot_type,
            camera_motion=motion,
            transition="crossfade",
            image_prompt=base_visual,
            enhanced_prompt=full_prompt,
            duration_target=15.0,
            status="pending",
            character_ids_json=json.dumps(c_ids),
            location_id=l_obj.id if l_obj else None
        )
        db.add(scene)
        scenes.append(scene)

    db.commit()
    logger.info(f"Decomposed script into {len(scenes)} scenes for project {project.id}")
    return scenes

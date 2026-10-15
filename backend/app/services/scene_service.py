import uuid
import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Project, Scene, Character, Location
from app.config import GLOBAL_VISUAL_STYLE_DEFAULT
from app.services.providers.factory import get_text_provider
from app.services.errors import OperationConflict, ProviderError

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

def parse_explicit_scene_markers(script_text: str) -> List[str]:
    """
    Parses scenes if the script contains explicit markers like [Scene 1], Scene 1:, or ---.
    """
    pattern = r'(?:\[(?:Scene|Сцена)\s*\d+\]|(?:Scene|Сцена)\s*\d+:|---|===|\n{3,})'
    parts = re.split(pattern, script_text, flags=re.IGNORECASE)
    cleaned = [p.strip() for p in parts if p.strip()]
    return cleaned if len(cleaned) > 1 else []


def local_scene_breakdown(text: str, start_order: int = 1) -> List[dict]:
    """Keep every spoken word while grouping sentences into usable scenes."""
    sentences = [item.strip() for item in re.split(r'(?<=[.!?])\s+', text) if item.strip()]
    if not sentences:
        sentences = [text.strip()]
    groups, current = [], []
    for sentence in sentences:
        current.append(sentence)
        if len(' '.join(current).split()) >= 30:
            groups.append(' '.join(current))
            current = []
    if current:
        if groups and len(' '.join(current).split()) < 12:
            groups[-1] += ' ' + ' '.join(current)
        else:
            groups.append(' '.join(current))
    return [{
        'scene_order': start_order + index,
        'narration': narration,
        'shot_type': SHOT_TYPES[(start_order + index) % len(SHOT_TYPES)],
        'visual_prompt': f'Cinematic scene depicting: {narration[:120]}',
        'character_names': [],
        'location_name': '',
    } for index, narration in enumerate(groups)]

async def decompose_script_to_scenes(db: Session, project: Project, script_text: str) -> List[Scene]:
    """
    Splits story script into visual scenes with 100% narration preservation and permanent UUIDs.
    """
    project_id = project.id
    provider_name = project.active_text_provider
    if not script_text.strip():
        raise ValueError("Сценарий не должен быть пустым")
    had_existing_scenes = db.query(Scene.id).filter(Scene.project_id == project_id).first() is not None

    chars = db.query(Character).filter(Character.project_id == project.id).all()
    locs = db.query(Location).filter(Location.project_id == project.id).all()

    char_summary = "\n".join([f"- CHARACTER '{c.name}': {c.appearance}" for c in chars])
    loc_summary = "\n".join([f"- LOCATION '{l.name}': {l.description}" for l in locs])
    global_style = project.global_visual_style or GLOBAL_VISUAL_STYLE_DEFAULT

    char_map = {c.name.lower(): (c.id, c.appearance) for c in chars}
    loc_map = {l.name.lower(): (l.id, l.description) for l in locs}

    # 1. Check for explicit scene markers
    explicit_parts = parse_explicit_scene_markers(script_text)
    raw_scenes = []

    if explicit_parts:
        logger.info(f"Found {len(explicit_parts)} explicit scene markers in script.")
        for idx, part in enumerate(explicit_parts, start=1):
            raw_scenes.append({
                "scene_order": idx,
                "narration": part,
                "shot_type": SHOT_TYPES[idx % len(SHOT_TYPES)],
                "visual_prompt": f"Cinematic shot: {part[:100]}"
            })
    elif project.active_image_provider == 'local_cards':
        # Local cards need the scene narration, not another metered AI request.
        raw_scenes.extend(local_scene_breakdown(script_text))
    else:
        provider = get_text_provider(db, provider_name)
        # 2. Chunk long script into ~1,000 word blocks to prevent token truncation
        paragraphs = script_text.split("\n\n")
        blocks = []
        current_block = []
        curr_words = 0
        for p in paragraphs:
            p_words = len(p.split())
            if curr_words + p_words > 1000 and current_block:
                blocks.append("\n\n".join(current_block))
                current_block = [p]
                curr_words = p_words
            else:
                current_block.append(p)
                curr_words += p_words
        if current_block:
            blocks.append("\n\n".join(current_block))

        logger.info(f"Processing script in {len(blocks)} block(s) for scene decomposition...")

        current_order = 1
        provider_failed = False
        for b_idx, block in enumerate(blocks):
            if provider_failed:
                fallback = local_scene_breakdown(block, current_order)
                raw_scenes.extend(fallback)
                current_order += len(fallback)
                continue
            prompt = f"""
You are an expert storyboarding director and cinematic prompt engineer.
Break the following script block into sequential visual scenes (target duration 10 to 20 seconds of spoken narration per scene, ~25-40 words each).

CRITICAL RULE: DO NOT OMIT, PARAPHRASE, OR ALTER ANY WORDS FROM THE SCRIPT. Every spoken word in the script block MUST be preserved in order.

KNOWN CHARACTERS:
{char_summary or "None"}

KNOWN LOCATIONS:
{loc_summary or "None"}

GLOBAL VISUAL STYLE:
{global_style}

SCRIPT BLOCK:
\"\"\"{block}\"\"\"

OUTPUT STRICT JSON ONLY:
{{
  "scenes": [
    {{
      "narration": "Exact verbatim narration text...",
      "shot_type": "Establishing Shot",
      "character_names": ["John"],
      "location_name": "House Basement",
      "visual_prompt": "Cinematic visual description of scene"
    }}
  ]
}}
"""
            try:
                raw_response = await provider.generate_text(prompt)
            except ProviderError:
                if had_existing_scenes:
                    raise
                logger.warning("Scene decomposition provider unavailable; preserving narration with local grouping")
                provider_failed = True
                fallback = local_scene_breakdown(block, current_order)
                raw_scenes.extend(fallback)
                current_order += len(fallback)
                continue
            try:
                start_idx = raw_response.find('{')
                end_idx = raw_response.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    parsed = json.loads(raw_response[start_idx:end_idx])
                else:
                    parsed = json.loads(raw_response)

                b_scenes = parsed.get("scenes", []) if isinstance(parsed, dict) else []
                if not isinstance(b_scenes, list) or not b_scenes:
                    raise ValueError("No scenes list returned in JSON")

                for sdata in b_scenes:
                    if not isinstance(sdata, dict) or not isinstance(sdata.get('narration'), str):
                        raise ValueError('Invalid narration')
                    for field in ('shot_type', 'location_name', 'visual_prompt', 'image_prompt'):
                        if field in sdata and not isinstance(sdata[field], str):
                            raise ValueError('Invalid scene field')
                    names = sdata.get('character_names', [])
                    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
                        raise ValueError('Invalid character names')
                if ' '.join(' '.join(s['narration'] for s in b_scenes).split()) != ' '.join(block.split()):
                    raise ValueError('AI changed or omitted narration')

                for sdata in b_scenes:
                    sdata["scene_order"] = current_order
                    raw_scenes.append(sdata)
                    current_order += 1
            except (ValueError, TypeError, KeyError, AttributeError) as parse_err:
                logger.warning("Invalid scene breakdown for block %s; preserving narration with local splitting.", b_idx)
                fallback = local_scene_breakdown(block, current_order)
                raw_scenes.extend(fallback)
                current_order += len(fallback)

    if not raw_scenes:
        import re
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script_text) if s.strip()]
        if not sentences:
            sentences = [script_text.strip()]
        for idx, s in enumerate(sentences, start=1):
            raw_scenes.append({
                "scene_order": idx,
                "narration": s,
                "shot_type": SHOT_TYPES[idx % len(SHOT_TYPES)],
                "visual_prompt": f"Cinematic scene depicting: {s[:120]}",
                "character_names": [],
                "location_name": ""
            })

    scenes = []
    motion_index = 0

    for idx, sdata in enumerate(raw_scenes, start=1):
        narration = sdata.get("narration", "").strip()
        if not narration:
            continue

        shot_type = sdata.get("shot_type", SHOT_TYPES[idx % len(SHOT_TYPES)])
        motion = MOTION_PRESETS[motion_index % len(MOTION_PRESETS)]
        motion_index += 1

        c_names = sdata.get("character_names", [])
        c_objs = [char_map[cn.lower()] for cn in c_names if cn.lower() in char_map]
        c_ids = [c[0] for c in c_objs]

        l_name = sdata.get("location_name", "")
        l_obj = loc_map.get(l_name.lower()) if l_name else None

        base_visual = sdata.get("visual_prompt") or sdata.get("image_prompt") or narration
        char_desc_str = ", ".join([c[1] for c in c_objs])
        loc_desc_str = l_obj[1] if l_obj else ""

        prompt_parts = [shot_type, base_visual]
        if char_desc_str:
            prompt_parts.append(f"featuring {char_desc_str}")
        if loc_desc_str:
            prompt_parts.append(f"set in {loc_desc_str}")
        prompt_parts.append(global_style)

        full_prompt = ", ".join(prompt_parts)
        sc_uuid = uuid.uuid4().hex

        scene = Scene(
            scene_uuid=sc_uuid,
            project_id=project_id,
            scene_order=idx,
            narration=narration,
            shot_type=shot_type,
            camera_motion=motion,
            scene_type="motion",
            transition="crossfade",
            image_prompt=base_visual,
            enhanced_prompt=full_prompt,
            duration_target=max(3.0, round(len(narration.split()) / 2.5, 1)),
            status="pending",
            image_status="not_created",
            tts_status="not_created",
            clip_status="not_created",
            input_version=1,
            character_ids_json=json.dumps(c_ids),
            location_id=l_obj[0] if l_obj else None
        )
        scenes.append(scene)

    # Validate/build everything before replacing any existing scene. A deleted
    # project must never be resurrected via orphan scene records.
    db.rollback()
    if not db.query(Project.id).filter(Project.id == project_id).first():
        raise OperationConflict('Project was deleted during scene decomposition')
    try:
        for old_scene in db.query(Scene).filter(Scene.project_id == project_id).all():
            db.delete(old_scene)
        db.add_all(scenes)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    logger.info(f"Decomposed script into {len(scenes)} scenes with permanent UUIDs for project {project_id}")
    return scenes


# --- Scene CRUD Functions ---

def update_scene_fields(db: Session, scene_uuid: str, payload: dict) -> Optional[Scene]:
    """Updates fields on a scene and automatically marks dependent statuses as outdated."""
    scene = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not scene:
        return None

    narration_changed = False
    prompt_changed = False
    voice_changed = False
    motion_changed = False

    if "narration" in payload and payload["narration"] != scene.narration:
        scene.narration = payload["narration"]
        narration_changed = True

    if "image_prompt" in payload and payload["image_prompt"] != scene.image_prompt:
        scene.image_prompt = payload["image_prompt"]
        if "enhanced_prompt" not in payload:
            # A manual prompt edit must take precedence over the old AI expansion.
            scene.enhanced_prompt = None
        prompt_changed = True

    if "enhanced_prompt" in payload and payload["enhanced_prompt"] != scene.enhanced_prompt:
        scene.enhanced_prompt = payload["enhanced_prompt"]
        prompt_changed = True

    if "camera_motion" in payload and payload["camera_motion"] != scene.camera_motion:
        scene.camera_motion = payload["camera_motion"]
        motion_changed = True

    if "scene_type" in payload and payload["scene_type"] != scene.scene_type:
        scene.scene_type = payload["scene_type"]
        motion_changed = True

    if "voice_id" in payload and payload["voice_id"] != scene.voice_id:
        scene.voice_id = payload["voice_id"]
        voice_changed = True

    if "shot_type" in payload:
        scene.shot_type = payload["shot_type"]

    if "duration_target" in payload and payload["duration_target"] != scene.duration_target:
        scene.duration_target = payload["duration_target"]
        motion_changed = True

    # Apply dependency tracking rules
    if narration_changed:
        scene.tts_status = "outdated"
        scene.clip_status = "outdated"
        scene.image_prompt_needs_review = True
        scene.input_version = (scene.input_version or 0) + 1

    if voice_changed:
        scene.tts_status = "outdated"
        scene.clip_status = "outdated"

    if prompt_changed:
        scene.image_status = "outdated"

    if motion_changed:
        scene.clip_status = "outdated"

    db.commit()
    db.refresh(scene)
    return scene

def split_scene_by_uuid(
    db: Session,
    scene_uuid: str,
    split_index: Optional[int] = None,
    split_text: Optional[str] = None,
) -> Tuple[Scene, Scene]:
    """Split a scene into two non-empty parts and return the two scenes."""
    parent = db.query(Scene).filter(Scene.scene_uuid == scene_uuid).first()
    if not parent:
        raise ValueError(f"Scene {scene_uuid} not found")

    narration = (parent.narration or "").strip()
    if len(narration) < 2:
        raise ValueError("Scene narration is too short to split")

    split_at: Optional[int] = None
    if split_index is not None:
        if split_index <= 0 or split_index >= len(narration):
            raise ValueError("split_index must be inside the narration text")
        split_at = split_index
    elif split_text:
        candidate = split_text.strip()
        found_at = narration.find(candidate)
        if candidate and found_at > 0:
            split_at = found_at

    if split_at is None:
        midpoint = len(narration) // 2
        boundaries = [m.end() for m in re.finditer(r"[.!?]\s+", narration)]
        if boundaries:
            split_at = min(boundaries, key=lambda pos: abs(pos - midpoint))
        else:
            left_space = narration.rfind(" ", 0, midpoint + 1)
            right_space = narration.find(" ", midpoint)
            split_at = left_space if left_space > 0 else right_space

    if split_at is None or split_at <= 0 or split_at >= len(narration):
        raise ValueError("Could not find a valid split point")

    text_part1 = narration[:split_at].strip()
    text_part2 = narration[split_at:].strip()
    if not text_part1 or not text_part2:
        raise ValueError("Both split parts must contain text")

    proj_id = parent.project_id
    order = parent.scene_order

    # Shift all subsequent scenes up by 1
    db.query(Scene).filter(Scene.project_id == proj_id, Scene.scene_order > order).update(
        {Scene.scene_order: Scene.scene_order + 1}
    )

    parent.narration = text_part1.strip()
    parent.tts_status = "outdated"
    parent.clip_status = "outdated"
    parent.image_prompt_needs_review = True
    parent.input_version = (parent.input_version or 0) + 1
    parent.duration_target = max(3.0, round(len(text_part1.split()) / 2.5, 1))

    sub_uuid = uuid.uuid4().hex
    new_sub = Scene(
        scene_uuid=sub_uuid,
        project_id=proj_id,
        scene_order=order + 1,
        narration=text_part2.strip(),
        shot_type="Close-Up" if parent.shot_type != "Close-Up" else "Medium Shot",
        camera_motion="slow_zoom_in",
        scene_type=parent.scene_type,
        transition="crossfade",
        image_prompt=f"{parent.image_prompt}, alternate angle",
        enhanced_prompt=parent.enhanced_prompt,
        duration_target=max(3.0, round(len(text_part2.split()) / 2.5, 1)),
        image_status="not_created",
        tts_status="not_created",
        clip_status="not_created",
        input_version=1,
        character_ids_json=parent.character_ids_json,
        location_id=parent.location_id
    )
    db.add(new_sub)
    db.commit()

    db.refresh(parent)
    db.refresh(new_sub)
    return parent, new_sub

def merge_scenes_by_uuids(db: Session, scene_uuid_1: str, scene_uuid_2: str) -> Scene:
    """Merges scene 2 into scene 1 and deletes scene 2."""
    if scene_uuid_1 == scene_uuid_2:
        raise ValueError('Нельзя объединить сцену с самой собой')
    s1 = db.query(Scene).filter(Scene.scene_uuid == scene_uuid_1).first()
    s2 = db.query(Scene).filter(Scene.scene_uuid == scene_uuid_2).first()
    if not s1 or not s2:
        raise ValueError("One or both scenes not found")
    if s1.project_id != s2.project_id:
        raise ValueError("Scenes from different projects cannot be merged")

    s1.narration = f"{s1.narration}\n{s2.narration}"
    s1.tts_status = "outdated"
    s1.clip_status = "outdated"
    s1.image_prompt_needs_review = True
    s1.input_version = (s1.input_version or 0) + 1

    proj_id = s1.project_id
    db.delete(s2)
    db.flush()

    # Re-index remaining scenes
    remaining = db.query(Scene).filter(Scene.project_id == proj_id).order_by(Scene.scene_order).all()
    for idx, sc in enumerate(remaining, start=1):
        sc.scene_order = idx
    db.commit()
    db.refresh(s1)
    return s1

def reorder_scenes_by_uuids(db: Session, project_id: str, scene_uuid_list: List[str]) -> List[Scene]:
    """Reorders scenes according to ordered list of UUIDs without touching media file bindings."""
    scenes = db.query(Scene).filter(Scene.project_id == project_id).all()
    scenes_map = {sc.scene_uuid: sc for sc in scenes}
    if len(scene_uuid_list) != len(set(scene_uuid_list)):
        raise ValueError("Scene order contains duplicate UUIDs")
    if set(scene_uuid_list) != set(scenes_map):
        raise ValueError("Scene order must contain every project scene exactly once")
    for order, sc_uuid in enumerate(scene_uuid_list, start=1):
        if sc_uuid in scenes_map:
            scenes_map[sc_uuid].scene_order = order
    db.commit()
    return db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()

import sys
import os
import tempfile
import atexit
import asyncio
import uuid
import io
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Keep integration tests away from the user's real database and media files.
_test_workspace = tempfile.TemporaryDirectory(prefix="storyforge-tests-")
os.environ["STORYFORGE_DB_PATH"] = os.path.join(_test_workspace.name, "storyforge-test.db")
os.environ["STORYFORGE_PROJECTS_DIR"] = os.path.join(_test_workspace.name, "projects")
os.environ["STORYFORGE_DEV_TOOLS"] = "1"

from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.database import SessionLocal, engine
from app.models import ImageVariation, Job, Project, Scene
from app.services.job_queue import job_manager
from app.services.motion_service import get_resolution_for_aspect_ratio
from app.services import tts_service


def _cleanup_test_workspace():
    engine.dispose()
    _test_workspace.cleanup()


atexit.register(_cleanup_test_workspace)

def test_offline_inspection_mode():
    client = TestClient(app, raise_server_exceptions=False)
    
    print("\n--- 1. Testing Create Test Project (100% Offline) ---")
    res = client.post("/api/projects/create-test")
    assert res.status_code == 200, f"Failed to create test project: {res.text}"
    data = res.json()
    project_id = data["id"]
    print(f"Created Test Project ID: {project_id}")
    assert data["is_test_project"] is True
    assert data["name"] == "🧪 Тестовый проект (Офлайн)"

    # Get project scenes
    scenes_res = client.get(f"/api/projects/{project_id}/scenes")
    assert scenes_res.status_code == 200
    scenes = scenes_res.json()
    assert len(scenes) == 3, f"Expected 3 test scenes, got {len(scenes)}"
    
    for sc in scenes:
        print(f"Scene #{sc['scene_order']}: image_path={sc['image_path']}, audio_path={sc['audio_path']}")
        assert sc["image_status"] == "completed"
        assert sc["tts_status"] == "completed"
        assert sc["image_path"] and os.path.isfile(sc["image_path"]), f"Image file missing for scene {sc['scene_order']}"
        assert sc["audio_path"] and os.path.isfile(sc["audio_path"]), f"Audio file missing for scene {sc['scene_order']}"

    # Test Script Decomposition Endpoint (POST /api/projects/{project_id}/script/decompose)
    dec_res = client.post(f"/api/projects/{project_id}/script/decompose")
    assert dec_res.status_code == 200, f"Decompose failed with status {dec_res.status_code}: {dec_res.text}"
    dec_scenes = dec_res.json()
    assert len(dec_scenes) >= 1, "Decomposition should return decomposed scenes"
    print(f"Decomposition test passed: returned {len(dec_scenes)} scenes!")

    print("\n--- 2. Testing API Error Simulation (401, 408, 429) ---")
    # Simulate 401
    sim_res = client.post("/api/settings/simulate-error", json={"error_code": 401})
    assert sim_res.status_code == 200
    assert sim_res.json()["simulated_error"] == 401

    # Fetch fresh scenes after decomposition
    fresh_scenes = client.get(f"/api/projects/{project_id}/scenes").json()

    # Attempt scene image generation under 401 error
    err_gen_res = client.post(f"/api/scenes/{fresh_scenes[0]['scene_uuid']}/generate-image")
    print(f"Error generation response: status={err_gen_res.status_code}, text={err_gen_res.text}")
    # Provider failures are upstream failures, not application crashes.
    assert err_gen_res.status_code == 502
    assert "401" in err_gen_res.text or "Unauthorized" in err_gen_res.text
    print("Received expected 401 error simulation on scene generation!")

    # Reset simulation
    clear_res = client.post("/api/settings/simulate-error", json={"error_code": None})
    assert clear_res.status_code == 200
    assert clear_res.json()["simulated_error"] is None
    print("API Error Simulation successfully cleared.")

    print("\n[OK] All Offline Inspection Mode tests passed successfully!")


def test_project_video_settings_and_scene_crud():
    client = TestClient(app, raise_server_exceptions=False)
    create_res = client.post("/api/projects", json={
        "name": "Vertical test",
        "topic_or_script": "A short test story",
        "aspect_ratio": "9:16",
        "resolution": "1080p",
    })
    assert create_res.status_code == 200, create_res.text
    project = create_res.json()
    assert project["aspect_ratio"] == "9:16"
    assert project["resolution"] == "1080p"

    scene_res = client.post(f"/api/projects/{project['id']}/scenes", json={
        "narration": "Первая половина сцены описывает героя. Вторая половина показывает его решение."
    })
    assert scene_res.status_code == 200, scene_res.text
    scene = scene_res.json()

    split_res = client.post(f"/api/scenes/{scene['scene_uuid']}/split", json={})
    assert split_res.status_code == 200, split_res.text
    split_scenes = split_res.json()
    assert len(split_scenes) == 2
    assert all(item["narration"].strip() for item in split_scenes)

    list_res = client.get(f"/api/projects/{project['id']}/scenes")
    assert list_res.status_code == 200
    listed_scenes = list_res.json()
    assert len(listed_scenes) == 2
    assert "input_version" in listed_scenes[0]
    assert "audio_offset_start" in listed_scenes[0]
    assert "error_message" in listed_scenes[0]

    image_buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "blue").save(image_buffer, format="PNG")
    upload_res = client.post(
        f"/api/scenes/{listed_scenes[0]['scene_uuid']}/upload-image",
        files={"file": ("test.png", image_buffer.getvalue(), "image/png")},
    )
    assert upload_res.status_code == 200, upload_res.text

    with SessionLocal() as db:
        variation = db.query(ImageVariation).filter(
            ImageVariation.scene_uuid == listed_scenes[0]["scene_uuid"]
        ).one()
        assert variation.project_id == project["id"]


def test_resolution_presets_and_legacy_values():
    assert get_resolution_for_aspect_ratio("16:9", "1080p") == (1920, 1080)
    assert get_resolution_for_aspect_ratio("9:16", "1080p") == (1080, 1920)
    assert get_resolution_for_aspect_ratio("1:1", "1080x1080") == (1080, 1080)
    assert get_resolution_for_aspect_ratio("16:9", "720p") == (1280, 720)


def test_batch_image_job_records_variation_and_finishes():
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    scene_uuid = uuid.uuid4().hex
    with SessionLocal() as db:
        project = Project(
            id=project_id,
            name="Batch image test",
            topic_or_script="Test",
            active_image_provider="mock",
        )
        scene = Scene(
            scene_uuid=scene_uuid,
            project_id=project_id,
            scene_order=1,
            narration="A local image generation test scene.",
            image_prompt="Blue cinematic test card",
        )
        db.add_all([project, scene])
        db.commit()
        job = job_manager.create_job(db, project_id, "batch_images", 1)
        project.active_job_id = job.id
        db.commit()
        job_id = job.id

    asyncio.run(job_manager.execute_batch_image_generation(project_id, job_id))

    with SessionLocal() as db:
        job = db.query(Job).filter(Job.id == job_id).one()
        project = db.query(Project).filter(Project.id == project_id).one()
        variation = db.query(ImageVariation).filter(ImageVariation.scene_uuid == scene_uuid).one()
        assert job.status == "completed"
        assert project.active_job_id is None
        assert variation.project_id == project_id


def test_scene_voice_is_forwarded_to_tts_provider(monkeypatch):
    captured = {}

    class FakeTTSProvider:
        async def generate_speech(self, text, voice_id=None, save_path=""):
            captured["voice_id"] = voice_id
            Path(save_path).write_bytes(b"fake-audio")
            return save_path

    monkeypatch.setattr(tts_service, "get_tts_provider", lambda db, name: FakeTTSProvider())
    monkeypatch.setattr(tts_service, "probe_audio_duration", lambda path: 1.5)

    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        project = Project(
            id=project_id,
            name="Voice test",
            topic_or_script="Test",
            active_tts_provider="mock",
            default_voice_id="project-voice",
        )
        scene = Scene(
            scene_uuid=uuid.uuid4().hex,
            project_id=project_id,
            scene_order=1,
            narration="Voice forwarding test.",
            voice_id="scene-voice",
        )
        db.add_all([project, scene])
        db.commit()
        asyncio.run(tts_service.generate_scene_tts(db, project, scene))

    assert captured["voice_id"] == "scene-voice"

if __name__ == "__main__":
    test_offline_inspection_mode()

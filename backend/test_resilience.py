"""Regression tests use the isolated offline workspace, never the user's database."""
import asyncio
import json
import subprocess
import sqlite3
import shutil
import sys
import uuid
import base64
import io
import os
import wave
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
import test_offline_mode as offline
from app.database import SessionLocal
from app.main import app
from app.models import Project, Script, Scene, Job, ProviderSetting, Character, Location, ImageVariation
from app.services import scene_service, script_service, media_process
from app.services.errors import OperationConflict, ProviderError
from app.services.job_queue import job_manager
from app.services.providers import gemini_text
from app.routers.settings import init_default_providers


@pytest.fixture
def project_id():
    pid = 'proj_' + uuid.uuid4().hex
    with SessionLocal() as db:
        db.add(Project(id=pid, name='Regression', topic_or_script='Original story.',
                       active_text_provider='mock', active_image_provider='mock', active_tts_provider='mock'))
        db.commit()
    return pid


def add_scene(pid):
    with SessionLocal() as db:
        scene = Scene(project_id=pid, scene_order=1, narration='Existing scene.', scene_uuid=uuid.uuid4().hex)
        db.add(scene)
        db.commit()
        return scene.scene_uuid


def test_new_script_is_empty_and_missing_project_is_404(project_id):
    with offline.TestClient(app) as client:
        res = client.get(f'/api/projects/{project_id}/script')
        assert res.status_code == 200 and res.json() is None
        assert client.get('/api/projects/missing/script').status_code == 404
        assert client.put('/api/projects/missing/script', json={'text': 'No orphan'}).status_code == 404


def test_error_simulation_disabled_for_customers(monkeypatch):
    monkeypatch.delenv('STORYFORGE_DEV_TOOLS', raising=False)
    with offline.TestClient(app) as client:
        response = client.post('/api/settings/simulate-error', json={'error_code': 500})
        assert response.status_code == 404


def test_youtube_pack_reads_never_call_paid_provider(project_id, monkeypatch):
    from app.services import youtube_service

    def unexpected_provider(*args, **kwargs):
        raise AssertionError('GET/download must not contact an AI provider')

    monkeypatch.setattr(youtube_service, 'has_api_key', lambda name: True)
    monkeypatch.setattr(youtube_service, 'get_text_provider', unexpected_provider)
    with offline.TestClient(app) as client:
        response = client.get(f'/api/projects/{project_id}/youtube-pack')
        download = client.get(f'/api/projects/{project_id}/youtube-pack/download')
        assert response.status_code == 200
        assert download.status_code == 200
        assert 'Проверьте факты' in response.json()['description'] or 'Verify facts' in response.json()['description']


def test_history_youtube_pack_does_not_invent_horror_or_fiction(project_id):
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        project.name = 'Мария Стюарт'
        project.story_type = 'История'
        project.language = 'Russian'
        db.commit()
    with offline.TestClient(app) as client:
        response = client.get(f'/api/projects/{project_id}/youtube-pack')
    assert response.status_code == 200
    pack = response.json()
    assert '#история' in pack['description']
    assert 'совпадения с реальными' not in pack['description']
    assert 'хоррор' not in pack['tags']


def test_new_project_uses_explicit_local_free_media_when_no_paid_keys(monkeypatch):
    from app.routers import projects
    monkeypatch.setattr(projects, 'has_api_key', lambda name: False)
    with offline.TestClient(app) as client:
        result = client.post('/api/projects', json={
            'topic_or_script': 'Мария Стюарт: история королевы Шотландии',
            'language': 'Russian', 'story_type': 'History',
        })
        assert result.status_code == 200, result.text
        item = result.json()
        assert item['active_image_provider'] == 'local_cards'
        assert item['active_tts_provider'] == 'windows_tts'
        assert item['active_text_provider'] == 'gemini'


def test_research_niche_is_offline_and_project_keeps_original_brief():
    with offline.TestClient(app) as client:
        niche = client.post('/api/research/niche', json={'videos': [
            {'title': 'One', 'views': 1200, 'age_days': 2},
            {'title': 'Two', 'views': 1000, 'age_days': 10},
        ]})
        assert niche.status_code == 200
        assert niche.json()['median_views_per_day'] == 350
        assert niche.json()['ranked_videos'][0]['title'] == 'One'
        assert client.post('/api/research/niche', json={'videos': []}).status_code == 422
        result = client.post('/api/projects', json={
            'topic_or_script': 'История другого человека',
            'creative_brief': 'Самостоятельная перспектива; средний темп.',
        })
        assert result.status_code == 200
        assert result.json()['creative_brief'] == 'Самостоятельная перспектива; средний темп.'


def test_reference_video_analysis_does_not_store_source(tmp_path):
    from app.config import FFMPEG_PATH
    import tempfile
    if not shutil.which(FFMPEG_PATH):
        pytest.skip('FFmpeg is not installed')
    video = tmp_path / 'reference.mp4'
    subprocess.run([
        FFMPEG_PATH, '-y', '-f', 'lavfi', '-i', 'color=c=red:s=320x180:d=1',
        '-f', 'lavfi', '-i', 'color=c=blue:s=320x180:d=1',
        '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0',
        '-c:v', 'mpeg4', str(video),
    ], check=True, capture_output=True, timeout=30)
    before = set(Path(tempfile.gettempdir()).glob('storyforge_reference_*'))
    with offline.TestClient(app) as client:
        response = client.post('/api/research/reference-video',
                               files={'file': ('reference.mp4', video.read_bytes(), 'video/mp4')})
    after = set(Path(tempfile.gettempdir()).glob('storyforge_reference_*'))
    assert response.status_code == 200, response.text
    assert response.json()['width'] == 320
    assert response.json()['duration_seconds'] >= 1.9
    assert response.json()['detected_cuts'] >= 1
    assert before == after


def test_local_app_rejects_foreign_browser_origin():
    with offline.TestClient(app) as client:
        denied = client.get('/api/projects', headers={'Origin': 'https://unrelated.example'})
        assert denied.status_code == 403
        allowed = client.get('/api/projects', headers={'Origin': 'http://127.0.0.1:8000'})
        assert allowed.status_code == 200


def test_built_frontend_is_served_on_backend_port():
    from app.main import FRONTEND_DIST
    if not (FRONTEND_DIST / 'index.html').is_file():
        pytest.skip('Frontend has not been built')
    with offline.TestClient(app) as client:
        response = client.get('/')
        assert response.status_code == 200
        assert 'StoryForge' in response.text


def test_full_backup_restores_to_new_directory_without_keys(tmp_path, monkeypatch):
    from app.services import backup_service
    from app.config import DB_PATH
    from restore_backup import restore_archive

    pid = 'proj_' + uuid.uuid4().hex
    source_projects = tmp_path / 'source-projects'
    media = source_projects / pid / 'images' / 'card.png'
    media.parent.mkdir(parents=True)
    media.write_bytes(b'local image')
    with SessionLocal() as db:
        db.add(Project(id=pid, name='Backup check', topic_or_script='Original topic',
                       active_text_provider='mock', active_image_provider='mock', active_tts_provider='mock'))
        db.add(Scene(project_id=pid, scene_uuid=uuid.uuid4().hex, scene_order=1,
                     narration='Own story.', image_path=str(media)))
        db.commit()
    monkeypatch.setattr(backup_service, 'PROJECTS_DIR', source_projects)
    monkeypatch.setattr(backup_service, 'BACKUPS_DIR', tmp_path / 'backups')
    monkeypatch.setattr(backup_service, 'DB_PATH', DB_PATH)
    archive = backup_service.create_library_archive()
    with zipfile.ZipFile(archive) as source:
        assert f'projects/{pid}/images/card.png' in source.namelist()
        assert all('key' not in name.lower() for name in source.namelist())
    target = restore_archive(archive, tmp_path / 'restored')
    assert (target / 'projects' / pid / 'images' / 'card.png').read_bytes() == b'local image'
    with sqlite3.connect(target / 'storyforge.db') as restored:
        image_path = restored.execute('SELECT image_path FROM scenes WHERE project_id=?', (pid,)).fetchone()[0]
    assert image_path == str(target / 'projects' / pid / 'images' / 'card.png')
    with pytest.raises(ValueError):
        restore_archive(archive, target)


def test_restore_rejects_zip_path_traversal(tmp_path):
    from restore_backup import restore_archive
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('manifest.json', json.dumps({'format': 'storyforge-library', 'version': 1, 'projects_root': 'C:/old/projects'}))
        output.writestr('database.sqlite3', b'not a database')
        output.writestr('projects/proj_bad/../../outside.txt', b'bad')
    with pytest.raises(ValueError):
        restore_archive(archive, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()


def test_backup_download_deletes_server_temp_archive(tmp_path, monkeypatch):
    from app.services import backup_service
    from app.config import DB_PATH
    monkeypatch.setattr(backup_service, 'BACKUPS_DIR', tmp_path / 'backups')
    monkeypatch.setattr(backup_service, 'PROJECTS_DIR', tmp_path / 'no-projects')
    monkeypatch.setattr(backup_service, 'DB_PATH', DB_PATH)
    with offline.TestClient(app) as client:
        response = client.post('/api/backup/export')
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert 'database.sqlite3' in archive.namelist()
        assert json.loads(archive.read('manifest.json'))['api_keys_included'] is False
    assert not list((tmp_path / 'backups').glob('storyforge-export-*'))


def test_preflight_never_calls_external_provider(monkeypatch):
    from app.services.providers.windows_tts_provider import WindowsTTSProvider
    monkeypatch.setattr(WindowsTTSProvider, 'test_connection', AsyncMock(return_value=True))
    with offline.TestClient(app) as client:
        response = client.get('/api/settings/preflight')
    assert response.status_code == 200
    assert response.json()['windows_voice_ready'] is True
    assert response.json()['external_api_calls_made'] is False


def test_old_database_is_snapshotted_once_before_schema_upgrade(tmp_path, monkeypatch):
    from app import database
    old_database = tmp_path / 'old.sqlite3'
    with sqlite3.connect(old_database) as connection:
        connection.execute('CREATE TABLE projects (id TEXT PRIMARY KEY)')
        connection.execute("INSERT INTO projects (id) VALUES ('original')")
    monkeypatch.setattr(database, 'DB_PATH', old_database)
    monkeypatch.setattr(database, 'BACKUPS_DIR', tmp_path / 'backups')
    snapshot = database.backup_database_before_migration()
    assert snapshot is not None and snapshot.is_file()
    with sqlite3.connect(snapshot) as connection:
        assert connection.execute('SELECT id FROM projects').fetchone()[0] == 'original'
    with sqlite3.connect(old_database) as connection:
        connection.execute('PRAGMA user_version=1')
    assert database.backup_database_before_migration() is None


def test_new_project_uses_configured_text_backup_but_never_paid_media_by_default(monkeypatch):
    from app.routers import projects
    monkeypatch.setattr(projects, 'has_api_key', lambda name: name in {'gemini', 'openrouter', 'gemini_image', 'fish_audio'})
    with offline.TestClient(app) as client:
        result = client.post('/api/projects', json={'topic_or_script': 'Historical test topic.'})
        assert result.status_code == 200, result.text
        item = result.json()
        assert item['active_text_provider'] == 'auto_text'
        assert item['active_image_provider'] == 'local_cards'
        assert item['active_tts_provider'] == 'windows_tts'


@pytest.mark.skipif(os.name != 'nt', reason='Windows System.Speech is required')
def test_windows_local_tts_produces_real_russian_wav(tmp_path):
    from app.services.providers.windows_tts_provider import WindowsTTSProvider
    from app.services.tts_service import probe_audio_duration
    output = tmp_path / 'Мария' / 'voice.wav'
    asyncio.run(WindowsTTSProvider().generate_speech('Мария Стюарт, королева Шотландии.', save_path=str(output)))
    with wave.open(str(output), 'rb') as audio:
        assert audio.getnframes() > 1000
        assert audio.getframerate() > 0
    assert probe_audio_duration(str(output)) > 0


def test_local_card_font_supports_russian():
    from app.services.providers.mock_provider import _card_font
    font = _card_font(32)
    assert bytes(font.getmask('М')) != bytes(font.getmask('□'))


def test_long_tts_scene_is_not_split_without_word_timestamps(project_id, tmp_path):
    from app.services.tts_service import sync_and_split_scenes_post_tts
    audio = tmp_path / 'narration.wav'
    audio.write_bytes(b'placeholder')
    uid = add_scene(project_id)
    with SessionLocal() as db:
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        scene.narration = 'Первое предложение. Второе предложение.'
        scene.audio_path = str(audio)
        scene.actual_duration = 35.0
        scene.tts_status = 'completed'
        db.commit()
        result = sync_and_split_scenes_post_tts(db, db.get(Project, project_id))
        assert len(result) == 1
        assert result[0].narration == 'Первое предложение. Второе предложение.'
        assert result[0].audio_path == str(audio)


def test_enhance_does_not_overwrite_original(project_id, monkeypatch):
    from app.routers import script
    provider = AsyncMock()
    provider.generate_text.return_value = 'Improved draft.'
    monkeypatch.setattr(script, 'get_text_provider', lambda *a: provider)
    with offline.TestClient(app) as client:
        client.put(f'/api/projects/{project_id}/script', json={'text': 'Keep original.'})
        res = client.post(f'/api/projects/{project_id}/script/enhance')
        assert res.status_code == 200 and res.json()['text'] == 'Improved draft.'
        assert client.get(f'/api/projects/{project_id}/script').json()['text'] == 'Keep original.'


def test_auto_preserves_existing_script(project_id, monkeypatch):
    def fail(*args):
        raise AssertionError('Existing script must not trigger provider')
    monkeypatch.setattr(script_service, 'get_text_provider', fail)
    with SessionLocal() as db:
        db.add(Script(project_id=project_id, text='User edits.', is_user_provided=True))
        db.commit()
        script, _, _ = asyncio.run(script_service.prepare_project_script(db, db.get(Project, project_id)))
        assert script.text == 'User edits.'


@pytest.mark.parametrize('response', [
    'not JSON', '{"scenes":[null]}', '{"scenes":[{"narration":null}]}',
    '{"scenes":[{"narration":"Invented story."}]}',
    '{"scenes":[{"narration":"First. Second.","character_names":[null]}]}',
])
def test_malformed_ai_preserves_words(project_id, monkeypatch, response):
    provider = AsyncMock()
    provider.generate_text.return_value = response
    monkeypatch.setattr(scene_service, 'get_text_provider', lambda *a: provider)
    add_scene(project_id)
    with SessionLocal() as db:
        scenes = asyncio.run(scene_service.decompose_script_to_scenes(db, db.get(Project, project_id), 'First. Second.'))
        assert ' '.join(s.narration for s in scenes) == 'First. Second.'
        assert db.query(Scene).filter_by(project_id=project_id).count() == len(scenes)


def test_upstream_error_preserves_scenes(project_id, monkeypatch):
    original = add_scene(project_id)
    provider = AsyncMock()
    provider.generate_text.side_effect = ProviderError('Quota exhausted', 503)
    monkeypatch.setattr(scene_service, 'get_text_provider', lambda *a: provider)
    with SessionLocal() as db:
        with pytest.raises(ProviderError):
            asyncio.run(scene_service.decompose_script_to_scenes(db, db.get(Project, project_id), 'New text.'))
        assert db.query(Scene).filter_by(scene_uuid=original).one().narration == 'Existing scene.'


def test_free_local_scene_breakdown_preserves_all_words_without_ai(project_id, monkeypatch):
    text = 'Мария стала королевой Шотландии. Её детство прошло во Франции. ' * 9
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        project.active_image_provider = 'local_cards'
        db.commit()
        monkeypatch.setattr(scene_service, 'get_text_provider',
                            lambda *a: (_ for _ in ()).throw(AssertionError('No AI call needed')))
        scenes = asyncio.run(scene_service.decompose_script_to_scenes(db, project, text))
        assert len(scenes) >= 2
        assert ' '.join(' '.join(s.narration for s in scenes).split()) == ' '.join(text.split())


def test_first_decomposition_can_fallback_when_ai_unavailable(project_id, monkeypatch):
    provider = AsyncMock()
    provider.generate_text.side_effect = ProviderError('Temporarily unavailable', 503)
    monkeypatch.setattr(scene_service, 'get_text_provider', lambda *a: provider)
    text = 'First sentence. Second sentence. Third sentence.'
    with SessionLocal() as db:
        scenes = asyncio.run(scene_service.decompose_script_to_scenes(db, db.get(Project, project_id), text))
        assert ' '.join(' '.join(s.narration for s in scenes).split()) == text


def test_project_deleted_during_await(project_id, monkeypatch):
    class Provider:
        async def generate_text(self, prompt):
            with SessionLocal() as other:
                other.delete(other.get(Project, project_id))
                other.commit()
            return '{"scenes":[{"narration":"Original story."}]}'
    monkeypatch.setattr(scene_service, 'get_text_provider', lambda *a: Provider())
    with SessionLocal() as db:
        with pytest.raises(OperationConflict):
            asyncio.run(scene_service.decompose_script_to_scenes(db, db.get(Project, project_id), 'Original story.'))
        assert db.query(Scene).filter_by(project_id=project_id).count() == 0


def test_atomic_scene_replacement(project_id, monkeypatch):
    original = add_scene(project_id)
    with SessionLocal() as db:
        def fail():
            db.flush()
            raise RuntimeError('Simulated disk failure')
        monkeypatch.setattr(db, 'commit', fail)
        with pytest.raises(RuntimeError):
            asyncio.run(scene_service.decompose_script_to_scenes(db, db.get(Project, project_id), '[Scene 1] A. [Scene 2] B.'))
    with SessionLocal() as db:
        assert [s.scene_uuid for s in db.query(Scene).filter_by(project_id=project_id)] == [original]


def test_concurrent_mutations_rejected_reads_available(project_id, monkeypatch):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        class Provider:
            async def generate_text(self, prompt):
                started.set()
                await release.wait()
                return '{"scenes":[{"narration":"Original story."}]}'
        monkeypatch.setattr(scene_service, 'get_text_provider', lambda *a: Provider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            pending = asyncio.create_task(client.post(f'/api/projects/{project_id}/script/decompose'))
            await asyncio.wait_for(started.wait(), 2)
            try:
                assert (await client.get(f'/api/projects/{project_id}')).status_code == 200
                assert (await client.delete(f'/api/projects/{project_id}')).status_code == 409
                assert (await client.delete('/api/projects')).status_code == 409
                assert (await client.post(f'/api/projects/{project_id}/auto-remaining')).status_code == 409
            finally:
                release.set()
                result = await asyncio.wait_for(pending, 2)
            assert result.status_code == 200, result.text
            assert (await client.patch(f'/api/projects/{project_id}', json={'name': 'Unlocked'})).status_code == 200
    asyncio.run(scenario())


def test_job_cancellation_stops_worker(project_id):
    async def scenario():
        started, stopped = asyncio.Event(), asyncio.Event()
        async def runner(pid, jid):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        with SessionLocal() as db:
            jid = job_manager.create_job(db, project_id, 'batch_images', 1).id
            db.get(Project, project_id).active_job_id = jid
            db.commit()
        task = asyncio.create_task(job_manager.run_registered(runner, project_id, jid))
        await asyncio.wait_for(started.wait(), 2)
        with SessionLocal() as db:
            assert job_manager.cancel_job(db, jid)
        await asyncio.wait_for(task, 2)
        assert stopped.is_set() and jid not in job_manager.active_jobs
        with SessionLocal() as db:
            job_manager.update_job_progress(db, jid, 1, 0, 1, 'done')
            assert db.get(Job, jid).status == 'cancelled'
            assert db.get(Project, project_id).active_job_id is None
    asyncio.run(scenario())


def test_duplicate_jobs_rejected(project_id):
    with SessionLocal() as db:
        job_manager.create_job(db, project_id, 'batch_images', 1)
        with pytest.raises(OperationConflict):
            job_manager.create_job(db, project_id, 'batch_tts', 1)


def test_completed_job_cannot_be_cancelled(project_id):
    with SessionLocal() as db:
        job = job_manager.create_job(db, project_id, 'batch_images', 1)
        job.status = 'completed'
        jid = job.id
        db.commit()
        job_manager.cancel_job(db, jid)
        assert db.get(Job, jid).status == 'completed'


def test_settings_preserve_user_model():
    with SessionLocal() as db:
        init_default_providers(db)
        setting = db.query(ProviderSetting).filter_by(provider_name='gemini').one()
        setting.model_id = 'gemini-3.6-flash'
        db.commit()
        init_default_providers(db)
        assert setting.model_id == 'gemini-3.6-flash'


@pytest.fixture
def gemini_transport(monkeypatch):
    gemini_text._model_cache.clear()
    gemini_text._cooldowns.clear()
    monkeypatch.setattr(gemini_text, 'get_api_key', lambda _: 'test-key-not-a-secret')
    real_client = httpx.AsyncClient
    calls = []
    def install(statuses):
        statuses = iter(statuses)
        def handler(request):
            calls.append(request)
            assert 'key=' not in str(request.url)
            assert request.headers['x-goog-api-key'] == 'test-key-not-a-secret'
            if request.method == 'GET':
                return httpx.Response(200, json={'models': [{
                    'name': 'models/gemini-test-flash', 'supportedGenerationMethods': ['generateContent']
                }]})
            status, body = next(statuses)
            return httpx.Response(status, json=body)
        monkeypatch.setattr(gemini_text.httpx, 'AsyncClient',
                            lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
        return calls
    yield install
    gemini_text._model_cache.clear()
    gemini_text._cooldowns.clear()


def test_gemini_model_discovery_and_text_parts(gemini_transport):
    calls = gemini_transport([(200, {'candidates': [{'content': {'parts': [{'text': 'A'}, {'text': 'B'}]}}]})])
    assert asyncio.run(gemini_text.GeminiTextProvider().generate_text('Prompt', 'System')) == 'AB'
    assert len(calls) == 2 and 'gemini-test-flash:generateContent' in str(calls[-1].url)
    assert 'systemInstruction' in json.loads(calls[-1].content)


def test_gemini_auto_prefers_newest_stable_flash_and_skips_retired(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'models': [
                {'name': f'models/{name}', 'supportedGenerationMethods': ['generateContent']}
                for name in ('gemini-2.5-flash', 'gemini-3.7-flash', 'gemini-3.8-flash')
            ]})
        if 'gemini-3.8-flash:' in str(request.url):
            return httpx.Response(404, json={'error': {'message': 'retired'}})
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': 'OK'}]}}]})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(gemini_text, 'get_api_key', lambda _: 'test-key')
    monkeypatch.setattr(gemini_text.httpx, 'AsyncClient',
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
    gemini_text._model_cache.clear()
    assert asyncio.run(gemini_text.GeminiTextProvider('auto').generate_text('Test')) == 'OK'
    assert 'gemini-3.8-flash:' in str(calls[1].url)
    assert 'gemini-3.7-flash:' in str(calls[2].url)
    assert len(calls) == 3
    gemini_text._model_cache.clear()


def test_missing_model_no_generation(gemini_transport):
    calls = gemini_transport([])
    with pytest.raises(ProviderError, match='модель'):
        asyncio.run(gemini_text.GeminiTextProvider('gemini-deleted').generate_text('Prompt'))
    assert len(calls) == 1


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429])
def test_permanent_api_errors_not_retried(gemini_transport, status):
    calls = gemini_transport([(status, {'error': {'message': 'raw response should stay private'}})])
    with pytest.raises(ProviderError) as exc:
        asyncio.run(gemini_text.GeminiTextProvider().generate_text('Prompt'))
    assert 'raw response' not in str(exc.value)
    assert len(calls) == 2
    if status == 429:
        with pytest.raises(ProviderError):
            asyncio.run(gemini_text.GeminiTextProvider().generate_text('Prompt'))
        assert len(calls) == 2


def test_transient_retries_bounded(gemini_transport, monkeypatch):
    calls = gemini_transport([(503, {})] * 3)
    sleeper = AsyncMock()
    monkeypatch.setattr(gemini_text.asyncio, 'sleep', sleeper)
    with pytest.raises(ProviderError):
        asyncio.run(gemini_text.GeminiTextProvider().generate_text('Prompt'))
    assert len(calls) == 4 and sleeper.await_count == 2


def test_empty_response_is_error(gemini_transport):
    gemini_transport([(200, {'candidates': []})])
    with pytest.raises(ProviderError):
        asyncio.run(gemini_text.GeminiTextProvider().generate_text('Prompt'))


def test_openrouter_errors_are_actionable_and_do_not_expose_response(monkeypatch):
    from app.services.providers import openai_provider
    real_client = httpx.AsyncClient
    monkeypatch.setattr(openai_provider, 'get_api_key', lambda _: 'test-secret')
    def handler(request):
        assert request.headers['Authorization'] == 'Bearer test-secret'
        assert json.loads(request.content)['model'] == 'qwen/qwen3.8-27b:free'
        return httpx.Response(429, json={'error': {'message': 'private upstream detail'}})
    monkeypatch.setattr(openai_provider.httpx, 'AsyncClient',
                        lambda **kwargs: real_client(transport=httpx.MockTransport(handler)))
    provider = openai_provider.OpenAITextProvider('qwen/qwen3.8-27b:free',
                                                  'https://openrouter.ai/api/v1', 'openrouter')
    with pytest.raises(ProviderError, match='Лимит') as exc:
        asyncio.run(provider.generate_text('Test'))
    assert 'private upstream detail' not in str(exc.value)


def test_explicit_gemini_to_openrouter_fallback():
    from app.services.providers.fallback_text import FallbackTextProvider
    primary, backup = AsyncMock(), AsyncMock()
    primary.generate_text.side_effect = ProviderError('Gemini unavailable', 503)
    backup.generate_text.return_value = 'История Марии Стюарт.'
    provider = FallbackTextProvider(primary, backup)
    assert asyncio.run(provider.generate_text('Prompt')) == 'История Марии Стюарт.'
    backup.generate_text.assert_awaited_once_with('Prompt', None)


def test_missing_image_output_fails_job(project_id, monkeypatch):
    from app.services import job_queue
    provider = AsyncMock()
    provider.generate_image.return_value = 'nonexistent.png'
    monkeypatch.setattr(job_queue, 'get_image_provider', lambda *a: provider)
    monkeypatch.setattr(job_queue, 'DEFAULT_RETRY_COUNT', 1)
    add_scene(project_id)
    with SessionLocal() as db:
        jid = job_manager.create_job(db, project_id, 'batch_images', 1).id
    asyncio.run(job_manager.execute_batch_image_generation(project_id, jid))
    with SessionLocal() as db:
        assert db.get(Job, jid).status == 'failed'
        assert db.query(Scene).filter_by(project_id=project_id).one().image_status == 'error'


@pytest.mark.parametrize('cancel', [False, True])
def test_media_process_reaped(monkeypatch, cancel):
    processes = []
    real_popen = subprocess.Popen
    def track(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(media_process.subprocess, 'Popen', track)
    async def scenario():
        task = asyncio.create_task(media_process.run_media_process(
            [sys.executable, '-c', 'import time; time.sleep(60)'], timeout=60 if cancel else 0.1))
        if cancel:
            await asyncio.sleep(0.1)
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else subprocess.TimeoutExpired):
            await task
    asyncio.run(scenario())
    assert processes and processes[0].poll() is not None


def test_delete_project_cleans_owned_rows(project_id):
    add_scene(project_id)
    with SessionLocal() as db:
        db.add_all([Script(project_id=project_id, text='Text'),
                    Character(project_id=project_id, name='C', appearance='C'),
                    Location(project_id=project_id, name='L', description='L')])
        job = job_manager.create_job(db, project_id, 'batch_images', 1)
        job.status = 'failed'
        db.commit()
    with offline.TestClient(app) as client:
        assert client.delete(f'/api/projects/{project_id}').status_code == 200
    with SessionLocal() as db:
        for model in (Script, Scene, Job, Character, Location):
            assert db.query(model).filter_by(project_id=project_id).count() == 0


def test_gemini_native_image_model_and_payload(monkeypatch, tmp_path):
    from PIL import Image
    from app.services.providers import gemini_provider
    image_bytes = io.BytesIO()
    Image.new('RGB', (8, 8), 'blue').save(image_bytes, format='PNG')
    calls = []
    def handler(request):
        calls.append(request)
        assert 'key=' not in str(request.url)
        if request.method == 'GET':
            return httpx.Response(200, json={'models': [
                {'name': 'models/gemini-test-flash', 'supportedGenerationMethods': ['generateContent']},
                {'name': 'models/gemini-test-flash-image', 'supportedGenerationMethods': ['generateContent']},
            ]})
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [
            {'inlineData': {'mimeType': 'image/png', 'data': base64.b64encode(image_bytes.getvalue()).decode()}}
        ]}}]})
    real_client = httpx.AsyncClient
    monkeypatch.setattr(gemini_provider, 'get_api_key', lambda _: 'test-image-key')
    monkeypatch.setattr(gemini_text.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    gemini_text._model_cache.clear()
    provider = gemini_provider.GeminiImageProvider('imagen-retired')
    output = tmp_path / 'image.png'
    asyncio.run(provider.generate_image('Test image', '9:16', str(output)))
    assert Image.open(output).size == (8, 8)
    assert 'gemini-test-flash-image:generateContent' in str(calls[-1].url)
    assert json.loads(calls[-1].content)['generationConfig']['imageConfig']['aspectRatio'] == '9:16'
    gemini_text._model_cache.clear()


def test_invalid_image_response_preserves_existing_file(monkeypatch, tmp_path):
    from app.services.providers import gemini_provider
    provider = gemini_provider.GeminiImageProvider()
    monkeypatch.setattr(provider, 'generate_content', AsyncMock(return_value={'candidates': []}))
    monkeypatch.setattr(gemini_provider, 'get_api_key', lambda _: 'fake')
    output = tmp_path / 'existing.png'
    output.write_bytes(b'keep original')
    with pytest.raises(ProviderError):
        asyncio.run(provider.generate_image('Test', save_path=str(output)))
    assert output.read_bytes() == b'keep original'


def test_missing_provider_keys_never_report_mock_success(monkeypatch):
    from app.services.providers import factory
    monkeypatch.setattr(factory, 'has_api_key', lambda _: False)
    with SessionLocal() as db:
        for provider in (factory.get_text_provider, factory.get_image_provider, factory.get_tts_provider):
            with pytest.raises(ProviderError):
                provider(db)
            assert provider(db, 'mock') is not None


@pytest.mark.parametrize('payload', [{'narration': None}, {'duration_target': -1}, {'duration_target': 0}])
def test_invalid_scene_patch_rejected_without_data_loss(project_id, payload):
    uid = add_scene(project_id)
    with offline.TestClient(app) as client:
        assert client.patch(f'/api/scenes/{uid}', json=payload).status_code == 422
    with SessionLocal() as db:
        assert db.query(Scene).filter_by(scene_uuid=uid).one().narration == 'Existing scene.'


def test_cannot_merge_scene_with_itself(project_id):
    uid = add_scene(project_id)
    with offline.TestClient(app) as client:
        res = client.post('/api/scenes/merge', json={'first_scene_uuid': uid, 'second_scene_uuid': uid})
        assert res.status_code == 400
    with SessionLocal() as db:
        assert db.query(Scene).filter_by(scene_uuid=uid).count() == 1


def test_media_path_cannot_escape_storage():
    from app.config import get_project_dir
    for name in ('..', '../outside', 'C:/outside'):
        with pytest.raises(ValueError):
            get_project_dir(name)
    with pytest.raises(ValueError):
        get_project_dir('safe-project', '../../outside')


def test_startup_recovers_jobs_and_scene_status(project_id):
    from app.services.job_queue import recover_interrupted_jobs_on_startup
    uid = add_scene(project_id)
    with SessionLocal() as db:
        jid = job_manager.create_job(db, project_id, 'batch_images', 1).id
        db.get(Project, project_id).active_job_id = jid
        db.query(Scene).filter_by(scene_uuid=uid).one().image_status = 'running'
        db.commit()
        recover_interrupted_jobs_on_startup(db)
        assert db.get(Job, jid).status == 'interrupted'
        assert db.get(Project, project_id).active_job_id is None
        assert db.query(Scene).filter_by(scene_uuid=uid).one().image_status == 'error'


def test_background_http_job_can_be_cancelled(project_id, monkeypatch):
    async def scenario():
        started = asyncio.Event()
        async def runner(pid, jid):
            started.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(job_manager, 'execute_batch_image_generation', runner)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            pending = asyncio.create_task(client.post(f'/api/projects/{project_id}/batch-images'))
            await asyncio.wait_for(started.wait(), 2)
            with SessionLocal() as db:
                jid = db.get(Project, project_id).active_job_id
            assert (await client.post(f'/api/jobs/{jid}/cancel')).status_code == 200
            assert (await asyncio.wait_for(pending, 2)).status_code == 200
            assert (await client.get(f'/api/jobs/{jid}')).json()['status'] == 'cancelled'
            assert (await client.patch(f'/api/projects/{project_id}', json={'name': 'After cancel'})).status_code == 200
    asyncio.run(scenario())


def test_clear_all_only_deletes_owned_media(monkeypatch, tmp_path):
    from app.routers import projects
    pid = 'proj_' + uuid.uuid4().hex
    owned = tmp_path / pid
    owned.mkdir()
    (owned / 'temporary-test-image.png').write_bytes(b'test')
    unrelated = tmp_path / 'unrelated'
    unrelated.mkdir()
    (unrelated / 'keep.txt').write_text('keep')
    monkeypatch.setattr(projects, 'PROJECTS_DIR', tmp_path)
    with SessionLocal() as db:
        db.add(Project(id=pid, name='Delete test', topic_or_script='Test'))
        db.commit()
        result = projects.clear_all_projects(db)
        assert result['media_cleanup_warnings'] == []
        assert not owned.exists()
        assert (unrelated / 'keep.txt').read_text() == 'keep'
        assert db.query(Script).count() == 0
        assert db.query(Scene).count() == 0


def test_actual_ffmpeg_render_with_non_ascii_path(project_id, monkeypatch):
    from PIL import Image
    from app.config import get_project_dir, FFMPEG_PATH
    from app.services.render_service import get_render_status, render_full_project_video
    import shutil
    if not shutil.which(FFMPEG_PATH):
        pytest.skip('FFmpeg is not installed')
    path = get_project_dir(project_id, 'тест медиа') / 'image.png'
    Image.new('RGB', (64, 64), 'navy').save(path)
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        project.resolution = '720p'
        scene = Scene(project_id=project_id, scene_uuid=uuid.uuid4().hex, scene_order=1,
                      narration='Проверка титров.', image_path=str(path), image_status='completed',
                      duration_target=0.3, camera_motion='static')
        db.add(scene)
        db.commit()
        result = asyncio.run(render_full_project_video(db, project))
        assert Path(result).stat().st_size > 0
        assert scene.clip_status == 'completed' and project.status == 'completed'
        assert get_render_status(db, project) == {'exists': True, 'current': True}
        scene.narration = 'Новый текст титров.'
        db.commit()
        assert get_render_status(db, project) == {'exists': True, 'current': False}


def test_subtitles_use_short_cues_and_preserve_words(tmp_path):
    from app.services.render_service import generate_srt_subtitles
    narration = ' '.join(f'слово{i}' for i in range(19))
    scene = Scene(scene_uuid=uuid.uuid4().hex, project_id='test', scene_order=1,
                  narration=narration, actual_duration=9.5)
    target = tmp_path / 'subtitles.srt'
    generate_srt_subtitles([scene], str(target))
    cues = target.read_text(encoding='utf-8').strip().split('\n\n')
    assert len(cues) == 3
    assert all(len(cue.splitlines()[2].split()) <= 8 for cue in cues)
    assert ' '.join(cue.splitlines()[2] for cue in cues) == narration
    assert cues[0].splitlines()[1].startswith('00:00:00,000')
    assert cues[-1].splitlines()[1].endswith('00:00:09,500')


def test_cancelled_render_removes_temporary_files_and_keeps_previous_export(project_id, monkeypatch):
    from app.config import get_project_dir
    from app.services import render_service
    image = get_project_dir(project_id, 'images') / 'input.png'
    image.write_bytes(b'image placeholder')
    clip = get_project_dir(project_id, 'clips') / 'clip.mp4'
    clip.write_bytes(b'clip placeholder')
    output = get_project_dir(project_id, 'output')
    final = output / 'final.mp4'
    final.write_bytes(b'previous export')

    async def interrupted(command):
        (output / 'concat_raw.tmp.mp4').write_bytes(b'partial concat')
        raise asyncio.CancelledError()

    monkeypatch.setattr(render_service, 'run_media_process', interrupted)
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        db.add(Scene(project_id=project_id, scene_uuid=uuid.uuid4().hex, scene_order=1,
                     narration='Narration', image_path=str(image), image_status='completed',
                     video_clip_path=str(clip), clip_status='completed'))
        db.commit()
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(render_service.render_full_project_video(db, project))
    assert final.read_bytes() == b'previous export'
    assert not (output / 'concat_raw.tmp.mp4').exists()
    assert not (output / 'final.tmp.mp4').exists()


def test_project_media_settings_invalidate_only_dependent_assets(project_id):
    uid = add_scene(project_id)
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        project.status = 'completed'
        scene.image_status = scene.tts_status = scene.clip_status = 'completed'
        db.commit()

    with offline.TestClient(app) as client:
        result = client.patch(f'/api/projects/{project_id}', json={'resolution': '720p'})
        assert result.status_code == 200 and result.json()['status'] == 'draft'
    with SessionLocal() as db:
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        assert (scene.image_status, scene.tts_status, scene.clip_status) == ('completed', 'completed', 'outdated')
        scene.clip_status = 'completed'
        db.commit()

    with offline.TestClient(app) as client:
        assert client.patch(f'/api/projects/{project_id}', json={'aspect_ratio': '9:16'}).status_code == 200
    with SessionLocal() as db:
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        assert (scene.image_status, scene.tts_status, scene.clip_status) == ('outdated', 'completed', 'outdated')


def test_failed_tts_preserves_previous_audio(project_id, monkeypatch):
    from app.config import get_project_dir
    from app.services import tts_service
    uid = add_scene(project_id)
    original = get_project_dir(project_id, 'audio') / f'scene_{uid}.mp3'
    original.write_bytes(b'previous valid audio')
    class BrokenProvider:
        async def generate_speech(self, text, voice_id=None, save_path=''):
            Path(save_path).write_bytes(b'partial output')
            raise ProviderError('Simulated provider failure')
    monkeypatch.setattr(tts_service, 'get_tts_provider', lambda *a: BrokenProvider())
    with SessionLocal() as db:
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        scene.audio_path = str(original)
        db.commit()
        with pytest.raises(ProviderError):
            asyncio.run(tts_service.generate_scene_tts(db, db.get(Project, project_id), scene))
        assert scene.tts_status == 'error'
    assert original.read_bytes() == b'previous valid audio'
    assert not original.with_name(f'scene_{uid}.tmp.mp3').exists()


def test_invalid_audio_is_not_accepted_by_file_size(monkeypatch, tmp_path):
    from app.services import tts_service
    path = tmp_path / 'invalid.mp3'
    path.write_bytes(b'not audio' * 100)
    monkeypatch.setattr(tts_service.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, 'nan', ''))
    with pytest.raises(ValueError):
        tts_service.probe_audio_duration(str(path))


def test_legacy_image_route_uses_uuid_and_absolute_storage(project_id):
    uid = add_scene(project_id)
    with SessionLocal() as db:
        sid = db.query(Scene).filter_by(scene_uuid=uid).one().id
    with offline.TestClient(app) as client:
        res = client.post(f'/api/projects/{project_id}/scenes/{sid}/regenerate_image')
        assert res.status_code == 200, res.text
        assert res.json()['image_status'] == 'completed'
        assert Path(res.json()['image_path']).is_absolute()
        assert uid in res.json()['image_path']


def test_manual_prompt_edit_takes_effect(project_id):
    uid = add_scene(project_id)
    with SessionLocal() as db:
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        scene.image_prompt = 'Original prompt'
        scene.enhanced_prompt = 'Old expansion'
        scene.image_status = 'completed'
        db.commit()
    with offline.TestClient(app) as client:
        response = client.patch(f'/api/scenes/{uid}', json={'image_prompt': 'New manual prompt'})
        assert response.status_code == 200, response.text
        assert response.json()['enhanced_prompt'] is None
        assert response.json()['image_status'] == 'outdated'


def test_image_variations_are_distinct_and_invalid_upload_preserves_scene(project_id):
    from PIL import Image
    uid = add_scene(project_id)
    image_bytes = io.BytesIO()
    Image.new('RGB', (2, 2), 'blue').save(image_bytes, format='PNG')
    with offline.TestClient(app) as client:
        first = client.post(f'/api/scenes/{uid}/upload-image',
                            files={'file': ('first.png', image_bytes.getvalue(), 'image/png')})
        second = client.post(f'/api/scenes/{uid}/upload-image',
                             files={'file': ('second.png', image_bytes.getvalue(), 'image/png')})
        assert first.status_code == second.status_code == 200
        first_path, second_path = first.json()['image_path'], second.json()['image_path']
        assert first_path != second_path
        assert Path(first_path).is_file() and Path(second_path).is_file()
        invalid = client.post(f'/api/scenes/{uid}/upload-image',
                              files={'file': ('bad.png', b'not an image', 'image/png')})
        assert invalid.status_code == 422
        assert client.get(f'/api/projects/{project_id}/scenes').json()[0]['image_path'] == second_path
    with SessionLocal() as db:
        variations = db.query(ImageVariation).filter_by(scene_uuid=uid).all()
        assert len(variations) == 2
        assert [item.is_active for item in variations] == [False, True]


def test_stale_media_cannot_be_exported(project_id):
    uid = add_scene(project_id)
    with SessionLocal() as db:
        scene = db.query(Scene).filter_by(scene_uuid=uid).one()
        scene.image_status = 'outdated'
        db.commit()
    with offline.TestClient(app) as client:
        result = client.post(f'/api/projects/{project_id}/export')
        assert result.status_code == 500
        assert 'Обновите изображение' in result.json()['detail']

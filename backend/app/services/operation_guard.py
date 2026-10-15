"""Reject conflicting mutations while a project is being processed."""
from threading import Lock

from fastapi.responses import JSONResponse


class ProjectMutationGuard:
    """Single-process local server guard, held through background task completion.

    Reads and job cancellation stay available. A collection delete is exclusive
    with every write. This deliberately rejects conflicts instead of queueing
    stale requests (e.g. an accidental double click).
    """

    def __init__(self, app):
        self.app = app
        self._lock = Lock()
        self._active = set()
        self._exclusive = False

    def _target(self, path):
        from app.database import SessionLocal
        from app.models import Scene, Job, Character, Location

        parts = path.strip('/').split('/')
        if len(parts) < 2 or parts[0] != 'api':
            return None
        if parts[1] == 'projects':
            return parts[2] if len(parts) > 2 else '*'
        if parts[1] == 'backup' and len(parts) > 2 and parts[2] == 'export':
            return '*'
        if len(parts) < 3:
            return None
        if parts[1] == 'jobs' and parts[-1] == 'cancel':
            return None
        if parts[1] == 'scenes' and parts[2] == 'merge':
            return '*'
        models = {'scenes': Scene, 'jobs': Job, 'characters': Character, 'locations': Location}
        model = models.get(parts[1])
        if model is None:
            return None
        with SessionLocal() as db:
            column = Scene.scene_uuid if model is Scene else model.id
            row = db.query(model.project_id).filter(column == parts[2]).first()
            return row[0] if row else None

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] in {'GET', 'HEAD', 'OPTIONS'}:
            return await self.app(scope, receive, send)
        try:
            target = self._target(scope['path'])
        except Exception:
            return await JSONResponse(status_code=503, content={'detail': 'База данных временно недоступна.'})(scope, receive, send)
        if target == '*' and scope['method'] == 'POST' and scope['path'].rstrip('/') == '/api/projects':
            target = '@create'
        if target is None:
            return await self.app(scope, receive, send)
        with self._lock:
            busy = self._exclusive or target in self._active or (target == '*' and bool(self._active))
            if not busy:
                if target == '*':
                    self._exclusive = True
                else:
                    self._active.add(target)
        if busy:
            response = JSONResponse(status_code=409, content={
                'detail': 'Проект уже обрабатывается. Дождитесь завершения или отмените задачу и повторите действие.'
            })
            return await response(scope, receive, send)
        try:
            await self.app(scope, receive, send)
        finally:
            with self._lock:
                if target == '*':
                    self._exclusive = False
                else:
                    self._active.discard(target)

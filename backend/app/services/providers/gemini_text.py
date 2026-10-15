import asyncio
import hashlib
import re
import time
from typing import Optional

import httpx

from app.services.errors import ProviderError
from app.services.key_store import get_api_key
from app.services.providers.base import BaseTextProvider

API_ROOT = 'https://generativelanguage.googleapis.com/v1beta'
# No API keys in URLs/logs. Cache account-specific model availability briefly.
_model_cache = {}
_cooldowns = {}


def _model_priority(name: str) -> tuple:
    """Prefer current stable Flash models over stale list order and aliases."""
    match = re.fullmatch(r'gemini-(\d+(?:\.\d+)*)-flash(-lite)?(-image)?', name)
    if not match:
        return (0, (0, 0, 0), 0)
    version = tuple(int(part) for part in match.group(1).split('.'))
    version = (version + (0, 0, 0))[:3]
    return (1, version, 0 if match.group(2) else 1)


def _retry_delay(response, attempt):
    try:
        return min(60.0, max(1.0, float(response.headers.get('Retry-After', 2 ** attempt))))
    except (TypeError, ValueError):
        return float(2 ** attempt)


class GeminiTextProvider(BaseTextProvider):
    image_mode = False
    def __init__(self, model_id: Optional[str] = None):
        self.model_id = (model_id or 'auto').removeprefix('models/')

    async def _models(self, client, headers, account):
        account = account + (':image' if self.image_mode else ':text')
        cached = _model_cache.get(account)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        models, token = [], None
        for _ in range(20):
            params = {'pageSize': 1000}
            if token:
                params['pageToken'] = token
            response = await client.get(f'{API_ROOT}/models', headers=headers, params=params)
            if response.status_code != 200:
                if response.status_code == 429:
                    _cooldowns[account.rsplit(':', 1)[0]] = time.monotonic() + 60
                self._raise_status(response.status_code)
            data = response.json()
            for model in data.get('models', []):
                name = model.get('name', '').removeprefix('models/')
                if ('generateContent' in model.get('supportedGenerationMethods', [])
                        and name.startswith('gemini-')
                        and (('image' in name) if self.image_mode else
                             not any(x in name for x in ('image', 'tts', 'audio', 'robotics', 'computer-use', 'live')))):
                    models.append(name)
            token = data.get('nextPageToken')
            if not token:
                break
        if not models:
            raise ProviderError('Для этого ключа Gemini нет доступных моделей выбранного типа. Проверьте настройки.', 503)
        _model_cache[account] = (time.monotonic() + 300, models)
        return models

    @staticmethod
    def _raise_status(status):
        if status in (400, 401, 403):
            raise ProviderError('Gemini отклонил запрос. Проверьте ключ API, доступ и настройки модели.')
        if status == 404:
            raise ProviderError('Выбранная модель Gemini недоступна. Выберите доступную модель или auto.', 503)
        if status == 429:
            raise ProviderError('Лимит Gemini исчерпан. Проверьте квоту и повторите позже.', 503)
        if status in (500, 502, 503, 504):
            raise ProviderError('Gemini временно недоступен. Проект сохранён; повторите позже.', 503)
        raise ProviderError(f'Gemini не выполнил запрос (HTTP {status}).')

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        payload = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}]}
        if system_prompt:
            payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}
        data = await self.generate_content(payload, get_api_key('gemini'))
        try:
            candidates = data.get('candidates') or []
            parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
            result = ''.join(p['text'] for p in parts if isinstance(p.get('text'), str) and not p.get('thought'))
            if not result.strip():
                raise ProviderError('Gemini вернул пустой или заблокированный ответ. Исходные данные сохранены.')
            return result
        except (ValueError, TypeError, KeyError, AttributeError, IndexError):
            raise ProviderError('Gemini вернул некорректный ответ. Исходные данные сохранены.') from None

    async def generate_content(self, payload, key):
        if not key:
            raise ProviderError('Не задан ключ Gemini. Добавьте ключ или явно выберите mock для офлайн-режима.', 503)
        account = hashlib.sha256(key.encode()).hexdigest()
        if _cooldowns.get(account, 0) > time.monotonic():
            raise ProviderError('Gemini ограничил запросы. Подождите минуту перед повторным запуском.', 503)
        headers = {'x-goog-api-key': key}
        try:
            # A total deadline bounds pagination + all retries, not just each socket.
            async with asyncio.timeout(90):
                async with httpx.AsyncClient(timeout=30.0) as client:
                    models = await self._models(client, headers, account)
                    if self.model_id == 'auto':
                        stable = [m for m in models if not any(x in m for x in ('preview', 'experimental', '-exp'))]
                        choices = sorted(stable or models, key=_model_priority, reverse=True)
                    elif self.model_id in models:
                        choices = [self.model_id]
                    else:
                        # Do not silently change a user-selected model or send to another provider.
                        self._raise_status(404)
                    for model in choices[:4]:
                        for attempt in range(3):
                            response = await client.post(f'{API_ROOT}/models/{model}:generateContent', headers=headers, json=payload)
                            status = response.status_code
                            if status == 200:
                                return response.json()
                            if status == 404:
                                _model_cache.pop(account + (':image' if self.image_mode else ':text'), None)
                                if self.model_id == 'auto':
                                    break
                            if status == 429:
                                _cooldowns[account] = time.monotonic() + max(60, _retry_delay(response, attempt))
                                self._raise_status(status)
                            if status in (500, 502, 503, 504) and attempt < 2:
                                await asyncio.sleep(_retry_delay(response, attempt))
                                continue
                            if status in (500, 502, 503, 504):
                                _cooldowns[account] = time.monotonic() + 60
                            self._raise_status(status)
                    self._raise_status(404)
        except (httpx.HTTPError, TimeoutError):
            raise ProviderError('Нет ответа от Gemini: проверьте сеть и повторите позже.', 503) from None
        except (ValueError, TypeError, KeyError, AttributeError, IndexError):
            raise ProviderError('Gemini вернул некорректный ответ. Исходные данные сохранены.') from None

    async def test_connection(self) -> bool:
        return bool(await self.generate_text("Reply with OK."))

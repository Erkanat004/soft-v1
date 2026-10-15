"""Local Windows speech synthesis with no external account or API charges."""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from app.services.errors import ProviderError
from app.services.media_process import run_media_process
from app.services.providers.base import BaseTTSProvider


SPEAK_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $requested = $env:STORYFORGE_TTS_VOICE
    $text = $env:STORYFORGE_TTS_TEXT
    $culture = if ($text -match '[А-Яа-яЁё]') { 'ru-RU' } else { 'en-US' }
    $voices = @($speaker.GetInstalledVoices() | Where-Object { $_.Enabled })
    $selected = $null
    if ($requested) {
        $selected = $voices | Where-Object {
            $_.VoiceInfo.Name -eq $requested -or $_.VoiceInfo.Culture.Name -eq $requested
        } | Select-Object -First 1
    }
    if (-not $selected) {
        $selected = $voices | Where-Object { $_.VoiceInfo.Culture.Name -eq $culture } | Select-Object -First 1
    }
    if (-not $selected) { throw 'No installed voice for the narration language.' }
    $speaker.SelectVoice($selected.VoiceInfo.Name)
    $speaker.SetOutputToWaveFile($env:STORYFORGE_TTS_OUTPUT)
    $speaker.Speak($text)
} finally {
    $speaker.Dispose()
}
"""


class WindowsTTSProvider(BaseTTSProvider):
    async def generate_speech(self, text: str, voice_id: Optional[str] = None, save_path: str = "") -> str:
        if os.name != "nt":
            raise ProviderError("Локальная озвучка доступна только на Windows.", 503)
        if not text.strip():
            raise ProviderError("Нельзя озвучить пустую сцену.", 422)
        if not save_path:
            raise ProviderError("Не задан путь для сохранения локальной озвучки.")

        output = Path(save_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment.update({
            "STORYFORGE_TTS_TEXT": text,
            "STORYFORGE_TTS_VOICE": voice_id or "",
            "STORYFORGE_TTS_OUTPUT": str(output),
        })
        try:
            result = await run_media_process(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", SPEAK_SCRIPT],
                timeout=120,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ProviderError("Локальная озвучка Windows не запустилась или превысила время ожидания.", 503) from None
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise ProviderError("Windows не смогла озвучить сцену. Проверьте установленные голоса.", 503)
        return str(output)

    async def test_connection(self) -> bool:
        with tempfile.TemporaryDirectory(prefix="storyforge_voice_") as directory:
            await self.generate_speech("Проверка озвучки.", save_path=str(Path(directory) / "voice.wav"))
        return True

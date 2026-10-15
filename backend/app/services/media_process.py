"""FFmpeg execution without blocking the API; cancellation waits for process exit."""
import asyncio
import subprocess


async def run_media_process(command, timeout=3600, env=None):
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
        env=env,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    communication = asyncio.create_task(asyncio.to_thread(process.communicate, timeout=timeout))
    try:
        stdout, stderr = await asyncio.shield(communication)
    except BaseException:
        if process.poll() is None:
            process.kill()
        try:
            await asyncio.shield(communication)
        except BaseException:
            # A timeout has ended communicate; reap the killed process.
            await asyncio.to_thread(process.communicate)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

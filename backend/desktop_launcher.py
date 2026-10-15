"""One-click localhost entry point for the Windows onedir build."""
import socket
import os
import sys
from pathlib import Path
import threading
import time
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("STORYFORGE_PORT", "8000"))


def open_when_ready():
    for _ in range(40):
        time.sleep(0.25)
        try:
            with socket.create_connection((HOST, PORT), timeout=0.3):
                webbrowser.open(f"http://{HOST}:{PORT}")
                return
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--restore":
        from restore_backup import restore_archive
        try:
            restored = restore_archive(Path(sys.argv[2]), Path(sys.argv[3]))
        except (ValueError, OSError) as exc:
            print(f"Restore failed: {exc}")
            raise SystemExit(1) from None
        print(f"Restored to {restored}. Set STORYFORGE_DATA_DIR to this folder before launching.")
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "--data-dir":
        directory = Path(sys.argv[2]).resolve()
        if not (directory / "storyforge.db").is_file():
            print("The selected data directory does not contain a StoryForge database.")
            raise SystemExit(2)
        os.environ["STORYFORGE_DATA_DIR"] = str(directory)
    elif len(sys.argv) != 1:
        print("Usage: StoryForge.exe [--data-dir DIRECTORY | --restore backup.zip NEW_DIRECTORY]")
        raise SystemExit(2)
    from app.main import app
    with socket.socket() as probe:
        try:
            probe.bind((HOST, PORT))
        except OSError:
            print(f"Port {PORT} is already in use. Close the other application first.")
            raise SystemExit(1)
    print("StoryForge runs only on this computer. Press Ctrl+C to stop.")
    if os.environ.get("STORYFORGE_NO_BROWSER") != "1":
        threading.Thread(target=open_when_ready, daemon=True).start()
    uvicorn.run(app, host=HOST, port=PORT, workers=1, log_level="warning")

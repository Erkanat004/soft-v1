import os
import shutil
from pathlib import Path
# Application Configuration Module


BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = BASE_DIR / "storyforge.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

def find_binary(binary_name: str) -> str:
    """Find system executable binary path or default fallback."""
    found = shutil.which(binary_name)
    if found:
        return found
    
    user_appdata = os.environ.get("LOCALAPPDATA", "")
    
    # Check common Windows paths & WinGet paths
    common_paths = [
        os.path.join(user_appdata, "Microsoft", "WinGet", "Links", f"{binary_name}.exe"),
        f"C:\\ffmpeg\\bin\\{binary_name}.exe",
        f"C:\\Program Files\\ffmpeg\\bin\\{binary_name}.exe",
        f"C:\\Program Files (x86)\\ffmpeg\\bin\\{binary_name}.exe"
    ]

    # Search WinGet packages directory dynamically
    winget_pkg_dir = os.path.join(user_appdata, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_pkg_dir):
        for root, dirs, files in os.walk(winget_pkg_dir):
            if f"{binary_name}.exe" in files:
                return os.path.join(root, f"{binary_name}.exe")

    for p in common_paths:
        if os.path.isfile(p):
            return p
    return binary_name


FFMPEG_PATH = find_binary("ffmpeg")
FFPROBE_PATH = find_binary("ffprobe")

GLOBAL_VISUAL_STYLE_DEFAULT = (
    "cinematic realistic photography, dark atmospheric lighting, subtle film grain, "
    "high detail, dramatic shadows, 35mm movie still, 16:9 aspect ratio"
)

MAX_CONCURRENT_IMAGE_JOBS = 3
DEFAULT_RETRY_COUNT = 3
TARGET_VISUAL_SCENE_MIN_SEC = 10
TARGET_VISUAL_SCENE_MAX_SEC = 20

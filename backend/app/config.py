import os
import shutil
import sys
from pathlib import Path
# Application Configuration Module


BASE_DIR = Path(__file__).resolve().parent.parent.parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)).resolve()
_default_data_dir = (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "StoryForgeAI") if getattr(sys, "frozen", False) else BASE_DIR
DATA_DIR = Path(os.environ.get("STORYFORGE_DATA_DIR", str(_default_data_dir))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR = Path(os.environ.get("STORYFORGE_PROJECTS_DIR", str(DATA_DIR / "projects"))).resolve()
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("STORYFORGE_DB_PATH", str(DATA_DIR / "storyforge.db"))).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR = DATA_DIR / "backups"
DATABASE_URL = f"sqlite:///{DB_PATH}"

def find_binary(binary_name: str) -> str:
    """Find system executable binary path or default fallback."""
    found = shutil.which(binary_name)
    if found:
        return found
    
    user_appdata = os.environ.get("LOCALAPPDATA", "")
    
    # Check common Windows paths & WinGet paths
    common_paths = [
        str(RESOURCE_DIR / f"{binary_name}.exe"),
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

# Mock provider fallback mode (False by default in normal mode, enabled only for dry-run/demo)
ALLOW_MOCK_FALLBACK = False

def get_project_dir(project_id: str, subfolder: str = "") -> Path:
    """Return unified absolute path to project directory or subfolder."""
    if not project_id or Path(project_id).name != project_id or project_id in ('.', '..'):
        raise ValueError('Invalid project directory')
    project_dir = (PROJECTS_DIR / project_id).resolve()
    if not project_dir.is_relative_to(PROJECTS_DIR) or project_dir == PROJECTS_DIR:
        raise ValueError('Project directory is outside media storage')
    pdir = project_dir
    if subfolder:
        pdir = pdir / subfolder
    pdir = pdir.resolve()
    if not pdir.is_relative_to(project_dir):
        raise ValueError('Media directory is outside project storage')
    pdir.mkdir(parents=True, exist_ok=True)
    return pdir

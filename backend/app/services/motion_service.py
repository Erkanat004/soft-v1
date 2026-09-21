import logging
import random
from typing import Dict, Any

logger = logging.getLogger("motion_service")

MOTION_PRESETS = [
    "slow_zoom_in",
    "slow_zoom_out",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
    "zoom_pan_left",
    "zoom_pan_right",
    "static"
]

def get_ffmpeg_zoompan_filter(
    motion: str,
    duration_sec: float,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080
) -> str:
    """
    Constructs an FFmpeg 'zoompan' filter string for the given motion preset and duration.
    """
    total_frames = int(max(duration_sec, 1.0) * fps)
    
    # Scale speed inversely proportional to frame count for smooth slow movement
    z_step = round(0.15 / max(total_frames, 1), 6)
    x_step = round((width * 0.1) / max(total_frames, 1), 4)
    y_step = round((height * 0.1) / max(total_frames, 1), 4)

    if motion == "slow_zoom_in":
        # Zoom from 1.0 to 1.15 at center
        z_expr = f"min(zoom+{z_step},1.15)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "slow_zoom_out":
        # Zoom from 1.15 down to 1.0 at center
        z_expr = f"max(1.15-{z_step}*on,1.0)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "pan_left":
        # Move camera from right to left
        z_expr = "1.10"
        x_expr = f"max(0,iw*0.1-{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "pan_right":
        # Move camera from left to right
        z_expr = "1.10"
        x_expr = f"min(iw*0.1,0+{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "pan_up":
        # Move camera from bottom to top
        z_expr = "1.10"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"max(0,ih*0.1-{y_step}*on)"

    elif motion == "pan_down":
        # Move camera from top to bottom
        z_expr = "1.10"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = f"min(ih*0.1,0+{y_step}*on)"

    elif motion == "zoom_pan_left":
        z_expr = f"min(zoom+{z_step},1.20)"
        x_expr = f"max(0,iw*0.15-{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    elif motion == "zoom_pan_right":
        z_expr = f"min(zoom+{z_step},1.20)"
        x_expr = f"min(iw*0.15,0+{x_step}*on)"
        y_expr = "ih/2-(ih/zoom/2)"

    else:  # static
        z_expr = "1.0"
        x_expr = "0"
        y_expr = "0"

    return f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={width}x{height}:fps={fps}"

def select_varied_motion(previous_motion: str) -> str:
    """Select a motion preset that is different from the previous scene."""
    candidates = [m for m in MOTION_PRESETS if m != previous_motion and m != "static"]
    return random.choice(candidates)

import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent.parent / "blender" / "blend_export.py"


def run(blender, obj_path, textures_dir, output_dir, level_name, area_id, scale):
    cmd = [
        blender,
        "--background",
        "--python", str(_SCRIPT),
        "--",
        "--obj", obj_path,
        "--textures", textures_dir,
        "--output", output_dir,
        "--level-name", level_name,
        "--area-id", str(area_id),
        "--scale", str(scale),
    ]
    subprocess.run(cmd, check=True)

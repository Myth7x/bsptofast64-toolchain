import subprocess
from pathlib import Path


def run(java_path, bspsource_jar, bsp_path, vmf_path):
    subprocess.run(
        [java_path, "-jar", bspsource_jar, "-o", vmf_path, bsp_path],
        check=True
    )

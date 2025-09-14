import subprocess
import sys
from typing import List

def run_cmd(cmd: List[str], path: str) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or str(e) + "\n")
        raise
    return result.stdout
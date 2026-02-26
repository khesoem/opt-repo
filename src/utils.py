import subprocess
import sys
from typing import List

from src import config

## Command execution utils
def run_cmd(cmd: List[str], path: str, capture_output: bool = True) -> str:
    try:
        result = subprocess.run(
            cmd,
            cwd=path,
            capture_output=capture_output,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(e.stderr or str(e) + "\n")
        raise
    return result.stdout

# Docker utils
def _prepare_new_img_dockerfile(base_image: str, working_dir: str) -> str:
        dockerfile_template = open(config.utils['git-extension-dockerfile']).read()
        dockerfile_content = dockerfile_template.replace('{base-image}', base_image)
        dockerfile_path = os.path.join(working_dir, 'Dockerfile')
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
        return dockerfile_path

def pull_image_install_git(repo: str, commit: str, working_dir: str) -> str:
    image_name = f'ghcr.io/khesoem/{repo.split("/")[-1]}-{commit}:latest'
    
    cmd = [
        "docker",
        "pull",
        image_name,
    ]
    run_cmd(cmd, working_dir)

    new_img_name = f'new-img'

    # Check if new-img exists and remove it if it does
    cmd = [
        "docker",
        "images",
        "--format",
        "{{.ID}}\t{{.Repository}}:{{.Tag}}",
    ]
    result = run_cmd(cmd, working_dir)
    image_ids = set()
    for line in result.strip().split('\n'):
        if line.strip():
            parts = line.strip().split('\t')
            if len(parts) == 2:
                image_id, image_ref = parts
                if new_img_name in image_ref:
                    image_ids.add(image_id)
    for image_id in image_ids:
        cmd = [
                "docker",
                "rmi",
                "-f",
                image_id,
            ]
        run_cmd(cmd, working_dir)

    _prepare_new_img_dockerfile(image_name, working_dir)

    cmd = [
        "docker",
        "build",
        "-t",
        new_img_name,
        working_dir,
    ]
    run_cmd(cmd, working_dir, capture_output=True)

    return new_img_name

def create_tmp_container(image_name: str, working_dir: str) -> str:
        cmd = [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=tmp-cont",
            "--format",
            "{{.Names}}",
        ]
        result = run_cmd(cmd, working_dir)
        if "tmp-cont" in result:
            cmd = [
                "docker",
                "rm",
                "tmp-cont",
            ]
            run_cmd(cmd, working_dir)
        
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            "tmp-cont",
            image_name,
        ]
        run_cmd(cmd, working_dir)
        return "tmp-cont"
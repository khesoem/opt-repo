import logging
import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import List

logging.basicConfig(filename='../../logs/openhands/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

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

def get_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-m",
        help="Mode of the tool (test or patch)",
        required=True,
    )

    parser.add_argument(
        "-repo",
        help="Repository name",
        required=True,
    )

    parser.add_argument(
        "-commit_id",
        help="Commit ID",
        required=True,
    )

    parser.add_argument(
        "-issue_id",
        help="Issue ID",
        required=True,
    )

    args = parser.parse_args()

    return (args.mode, args.repo, args.commit_id, args.issue_id)

####################################################################################

WORKING_DIR = "/home/khesoem/postdoc-eth/projects/optimization-dataset/code/tmp/working_dir"
gh_token = os.environ['github_access_token']

def pull_docker_image(repo: str, commit_id: str) -> str:
    image_name = f'ghcr.io/khesoem/{repo}-{commit_id}:latest'
    
    cmd = [
        "docker",
        "pull",
        image_name,
    ]
    run_cmd(cmd, WORKING_DIR)
    return image_name

def copy_orig_repo(image_name: str) -> str:
    cmd = [
        "docker",
        "create",
        "--name",
        "tmp-cont",
        image_name,
    ]
    run_cmd(cmd, WORKING_DIR)

    cmd = [
        "docker",
        "cp",
        "tmp-cont:/app/original_repo",
        WORKING_DIR,
    ]
    run_cmd(cmd, WORKING_DIR)

    cmd = [
        "docker",
        "rm",
        "-f",
        "tmp-cont",
    ]
    run_cmd(cmd, WORKING_DIR)
    
    return os.path.join(WORKING_DIR, 'original_repo')

def remove_git_dir(repo_path: str) -> None:
    cmd = [
        "rm",
        "-rf",
        os.path.join(repo_path, '.git'),
    ]
    run_cmd(cmd, repo_path)

def get_issue_title_and_description(issue_id: str) -> tuple[str, str]:

def run_patch_generation(repo: str, commit_id: str, issue_id: str) -> None:
    image_name = pull_docker_image(repo, commit_id)
    repo_path = copy_orig_repo(image_name)
    remove_git_dir(repo_path)

    issue_title, issue_description = get_issue_title_and_description(issue_id)
    
    task_file_path = create_task_file(issue_title, issue_description)
    config_file_path = create_config_file()
    run_openhands(task_file_path, config_file_path)
        

def main() -> None:
    (mode, repo, commit_id, issue_id) = get_args()

    if mode == "test":
        pass
    elif mode == "patch":
        run_patch_generation(repo, commit_id, issue_id)
    else:
        raise ValueError(f"Invalid mode: {mode}")

if __name__ == "__main__":
    main()
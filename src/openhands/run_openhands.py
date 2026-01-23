import logging
import argparse
import os
from src.gh.commit_analysis.commit_static_analyzer import RepoAnalyzer
from src.utils import run_cmd
from datetime import datetime
from src import config
from github import Commit, Github, Auth, Repository

logging.basicConfig(filename='../../logs/openhands/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

class OpenHandsRunner:
    def __init__(self, working_dir: str):
        self.working_dir = config.openhands['working-dir']
        self.gh_token = config.github['access_token']
        auth = Auth.Token(self.gh_token)
        self.g = Github(auth=auth)

    def pull_docker_image(self, repo: str, commit_id: str) -> str:
        image_name = f'ghcr.io/khesoem/{repo}-{commit_id}:latest'
        
        cmd = [
            "docker",
            "pull",
            image_name,
        ]
        run_cmd(cmd, self.working_dir)
        return image_name
    
    def create_tmp_container(self, image_name: str) -> str:
        cmd = [
            "docker",
            "create",
            "--name",
            "tmp-cont",
            image_name,
        ]
        run_cmd(cmd, self.working_dir)
        return "tmp-cont"

    def _prepare_original_repo(self, container_name: str) -> str:
        cmd = [
            "docker",
            "cp",
            f"{container_name}:/app/original_repo",
            self.working_dir,
        ]
        run_cmd(cmd, self.working_dir)

        repo_path = os.path.join(self.working_dir, 'original_repo')

        self._remove_git_dir(repo_path)
        
        return repo_path
    
    def _remove_tmp_container(self, container_name: str) -> None:
        cmd = [
            "docker",
            "rm",
            "-f",
            container_name,
        ]
        run_cmd(cmd, self.working_dir)

    def _remove_git_dir(self, repo_path: str) -> None:
        cmd = [
            "rm",
            "-rf",
            os.path.join(repo_path, '.git'),
        ]
        run_cmd(cmd, repo_path)

    def get_issue_title_and_description(self, repo: Repository, issue_id: int) -> tuple[str, str]:
        issue = repo.get_issue(issue_id)
        return issue.title, issue.body
    
    def get_modified_modules_and_files(self, container_name: str, commit: str) -> tuple[set[str], set[str]]:
        cmd = [
            "docker",
            "exec",
            container_name,
            "git", "diff-tree", "-r", "--no-commit-id", "--name-status", "-M", "-C", "-m", commit,
        ]
        diff_output = run_cmd(cmd, self.working_dir)
        
        analyzer = RepoAnalyzer(None)
        changed_java_files = analyzer.diff_to_java_src_files(diff_output)
        modified_modules = analyzer.get_modules_for_java_files(changed_java_files)
        return modified_modules, changed_java_files


    def _create_task_file(self, repo: Repository, commit_id: str, issue_id: int, container_name: str, openhands_files_path: str) -> str:
        issue_title, issue_description = self.get_issue_title_and_description(repo, issue_id)

        task_file_path = os.path.join(openhands_files_path, 'task-patch-generation.txt')

        task_template = open(os.path.join(config.openhands['openhands-files-dir'], 'task-patch-generation.txt')).read()

        modified_modules, changed_java_files = self.get_modified_modules_and_files(container_name, commit_id)

        if len(modified_modules) > 1:
            raise ValueError('Multiple modified modules are not supported yet')
        else:
            modified_module = modified_modules[0]

        task_content = task_template.replace('{issue-title}', issue_title).replace('{issue-description}', issue_description).replace('{buggy-module}', modified_module).replace('{buggy-files}', '\n'.join(changed_java_files))

        with open(task_file_path, 'w') as f:
            f.write(task_content)

        return task_file_path


    def _create_config_file(self, openhands_files_path: str) -> str:
        config_template = open(os.path.join(config.openhands['openhands-files-dir'], 'config.toml')).read()
        config_content = config_template.replace('{working-dir}', self.working_dir)
        config_file_path = os.path.join(openhands_files_path, 'config.toml')
        with open(config_file_path, 'w') as f:
            f.write(config_content)
        return config_file_path
    
    def _create_command_file(self, image_name: str, repo_path: str, openhands_files_path: str) -> str:
        command_template = open(os.path.join(config.openhands['openhands-files-dir'], 'command.sh')).read()
        command_content = command_template.replace('{image}', image_name).replace('{repo_path}', repo_path).replace('{openhands_files_path}', openhands_files_path)

        command_file_path = os.path.join(self.working_dir, 'command.sh')
        with open(command_file_path, 'w') as f:
            f.write(command_content)

        return command_file_path


    def _prepare_openhands_files(self, image_name: str, repo: Repository, commit_id: str, issue_id: int, container_name: str, repo_path: str) -> str:
        openhands_files_path = os.path.join(self.working_dir, 'openhands-files')
        os.makedirs(openhands_files_path, exist_ok=True)
        task_file_path = self._create_task_file(repo, commit_id, issue_id, container_name, openhands_files_path)
        config_file_path = self._create_config_file(openhands_files_path)
        command_file_path = self._create_command_file(image_name, repo_path, openhands_files_path)

        return openhands_files_path

    def _run_openhands(self) -> None:
        cmd = [
            "./command.sh",
        ]
        run_cmd(cmd, self.working_dir)

    def run_patch_generation(self, repo: str, commit_id: str, issue_id: int) -> None:
        image_name = self.pull_docker_image(repo, commit_id)
        container_name = self.create_tmp_container(image_name)
        repo_path = self._prepare_original_repo(container_name)

        repo = self.g.get_repo(repo)

        openhands_files_path = self._prepare_openhands_files(image_name, repo, commit_id, issue_id, container_name, repo_path)
        
        self._remove_tmp_container(container_name)

        self._run_openhands()

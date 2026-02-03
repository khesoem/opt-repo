import os
import shutil
from src.gh.commit_analysis.commit_static_analyzer import RepoAnalyzer
from src.utils import run_cmd
from src import config
from github import Github, Auth, Repository

class OpenHandsRunner:
    def __init__(self, working_dir: str):
        self.working_dir = config.openhands['working-dir']
        self.gh_token = config.github['access-token']
        auth = Auth.Token(self.gh_token)
        self.g = Github(auth=auth)

    def _pull_docker_image(self, repo: str, commit: str) -> str:
        image_name = f'ghcr.io/khesoem/{repo.split("/")[-1]}-{commit}:latest'
        
        cmd = [
            "docker",
            "pull",
            image_name,
        ]
        run_cmd(cmd, self.working_dir)
        return image_name
    
    def _create_tmp_container(self, image_name: str) -> str:
        cmd = [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=tmp-cont",
            "--format",
            "{{.Names}}",
        ]
        result = run_cmd(cmd, self.working_dir)
        if "tmp-cont" in result:
            cmd = [
                "docker",
                "rm",
                "tmp-cont",
            ]
            run_cmd(cmd, self.working_dir)
        
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            "tmp-cont",
            image_name,
        ]
        run_cmd(cmd, self.working_dir)
        return "tmp-cont"

    def _prepare_original_repo(self, container_name: str, commit: str) -> str:
        repo_path = os.path.join(self.working_dir, 'original_repo')

        if os.path.exists(repo_path):
            cmd = [
                "mv",
                "original_repo",
                os.path.join(self.working_dir, f'original_repo_{commit}_leftover'),
            ]
            run_cmd(cmd, self.working_dir)

        cmd = [
            "docker",
            "cp",
            f"{container_name}:/app/original_repo",
            self.working_dir,
        ]
        run_cmd(cmd, self.working_dir)

        cmd = [
            "docker",
            "cp",
            f"{container_name}:/app/original_repo",
            self.working_dir,
        ]
        run_cmd(cmd, self.working_dir)
        
        return repo_path
    
    def _remove_tmp_container(self, container_name: str) -> None:
        cmd = [
            "docker",
            "rm",
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
    
    def get_modified_modules_and_files(self, commit: str, repo_path: str) -> tuple[set[str], set[str]]:    
        analyzer = RepoAnalyzer(repo_path)
        changed_java_files = analyzer.get_changed_java_src_files(commit)
        modified_modules = analyzer.get_modules_for_java_files(changed_java_files)
        return modified_modules, changed_java_files


    def _create_task_file(self, repo: Repository, commit: str, issue_id: int, repo_path: str, openhands_files_path: str) -> str:
        issue_title, issue_description = self.get_issue_title_and_description(repo, issue_id)

        task_file_path = os.path.join(openhands_files_path, 'task-patch-generation.txt')

        task_template = open(os.path.join(config.openhands['openhands-files-dir'], 'task-patch-generation.txt')).read()

        modified_modules, changed_java_files = self.get_modified_modules_and_files(commit, repo_path)

        if len(modified_modules) > 1:
            raise ValueError('Multiple modified modules are not supported yet')
        else:
            modified_module = modified_modules.pop()

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


    def _prepare_openhands_files(self, image_name: str, repo: Repository, commit: str, issue_id: int, repo_path: str):
        openhands_files_dir = os.path.join(self.working_dir, 'openhands-files')
        os.makedirs(openhands_files_dir, exist_ok=True)
        self._create_task_file(repo, commit, issue_id, repo_path, openhands_files_dir)
        self._create_config_file(openhands_files_dir)
        self._create_command_file(image_name, repo_path, openhands_files_dir)

    def _run_openhands(self) -> None:
        cmd = [
            "bash",
            "./command.sh",
        ]
        run_cmd(cmd, self.working_dir, capture_output=False)

    def _backup_and_clean_openhands_files(self, commit: str) -> None:
        cmd = [
            "mv",
            os.path.join(self.working_dir, 'original_repo'),
            os.path.join(self.working_dir, f'original_repo_{commit}'),
        ]
        run_cmd(cmd, self.working_dir)

        # Find containers with images that have 'openhands/runtime' in their name
        cmd = [
            "docker",
            "ps",
            "-a",
            "--format",
            "{{.ID}}\t{{.Image}}",
        ]
        result = run_cmd(cmd, self.working_dir)
        workspace_container_ids = []
        all_container_ids = []
        for line in result.strip().split('\n'):
            if line.strip():
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    container_id, image_name = parts
                    if 'openhands/runtime' in image_name:
                        workspace_container_ids.append(container_id)
                    if 'openhands' in image_name:
                        all_container_ids.append(container_id)
        
        
        for container_id in workspace_container_ids:
            # Start the stopped container
            cmd = [
                "docker",
                "start",
                container_id,
            ]
            run_cmd(cmd, self.working_dir)
            
            # Create destination directory
            dest_dir = os.path.join(self.working_dir, commit)
            os.makedirs(dest_dir, exist_ok=True)
            
            # Copy /workspace directory from container
            cmd = [
                "docker",
                "cp",
                f"{container_id}:/workspace",
                dest_dir,
            ]
            run_cmd(cmd, self.working_dir)
            
        for container_id in all_container_ids:
            # Force remove the container
            cmd = [
                "docker",
                "rm",
                "-f",
                container_id,
            ]
            run_cmd(cmd, self.working_dir)
        
        # Remove all docker images that have 'openhands/runtime' in their name
        cmd = [
            "docker",
            "images",
            "--format",
            "{{.ID}}\t{{.Repository}}:{{.Tag}}",
        ]
        result = run_cmd(cmd, self.working_dir)
        image_ids = set()
        for line in result.strip().split('\n'):
            if line.strip():
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    image_id, image_ref = parts
                    if 'openhands/runtime' in image_ref:
                        image_ids.add(image_id)
        
        for image_id in image_ids:
            cmd = [
                "docker",
                "rmi",
                "-f",
                image_id,
            ]
            run_cmd(cmd, self.working_dir)

    def run_patch_generation(self, repo: str, commit: str, issue_id: int) -> None:
        image_name = self._pull_docker_image(repo, commit)
        container_name = self._create_tmp_container(image_name)
        repo_path = self._prepare_original_repo(container_name, commit)

        repo = self.g.get_repo(repo)

        self._prepare_openhands_files(image_name, repo, commit, issue_id, repo_path)
        
        self._remove_tmp_container(container_name)
        self._remove_git_dir(repo_path)

        self._run_openhands()

        self._backup_and_clean_openhands_files(commit)

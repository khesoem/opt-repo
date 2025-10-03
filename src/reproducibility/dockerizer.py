import subprocess
import logging
import shutil
from pathlib import Path
from src import config
from src.utils import run_cmd
import os

logger = logging.getLogger(__name__)

class CommitDockerizer:
    class MvnwExecResults:
        def __init__(self, patched_mvnw_log_path: str, original_mvnw_log_path: str, module_to_test_res_path: dict[str, dict[str, str]]):
            self.patched_mvnw_log_path = patched_mvnw_log_path
            self.original_mvnw_log_path = original_mvnw_log_path
            self.module_to_test_res_path = module_to_test_res_path

    def __init__(self, working_dir: str, repo: str, commit: str, patched_repo_path: str, original_repo_path: str, module_names: list[str]):
        self.working_dir = working_dir
        self.repo = repo
        self.commit = commit
        self.patched_repo_path = patched_repo_path
        self.original_repo_path = original_repo_path
        self.module_names = module_names

    @property
    def image_name(self):
        return f"{config.docker['image-name-prefix']}-{self.repo}-{self.commit}".lower()
    
    @property
    def tmp_dir(self):
        return f"{self.working_dir}/{self.image_name.replace('/', '__')}_tmp"
    
    @property
    def container_name(self):
        return f"container-{self.image_name.replace('/', '__')}"

    def build_commit_docker_image(self):
        try:
            # copy the dockerfile to the working directory
            shutil.copy(config.docker['dockerfile'], self.working_dir)
            dockerfile_path = Path(self.working_dir) / 'Dockerfile'
            
            if not dockerfile_path.exists():
                raise FileNotFoundError(f"Dockerfile not found at {dockerfile_path}")

            original_repo_path = self.original_repo_path.replace(self.working_dir, '')
            patched_repo_path = self.patched_repo_path.replace(self.working_dir, '')
            
            # Build the Docker image
            run_cmd([
                "docker", "build",
                "-f", str(dockerfile_path),
                "-t", self.image_name,
                str(Path(self.working_dir)),
                "--build-arg", f"PATCHED_REPO_DIR={patched_repo_path}",
                "--build-arg", f"ORIGINAL_REPO_DIR={original_repo_path}",
                "--build-arg", f"MODULE_NAMES={','.join(self.module_names)}"
            ], self.working_dir, capture_output=False)
            
            logger.info(f"Successfully built Docker image: {self.image_name}")
            return self.image_name
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error building Docker image: {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def get_mvnw_exec_results(self) -> MvnwExecResults:
        run_cmd(['mkdir', '-p', f'{self.tmp_dir}'], self.working_dir)
        run_cmd(['docker', 'create', '--name', f'{self.container_name}', f'{self.image_name}'], self.working_dir)

        try:
            run_cmd(['docker', 'cp', f'{self.container_name}:{config.docker['mvnw-log-path']}', f'{self.tmp_dir}'], self.working_dir)
            original_mvnw_log_path = f'{self.tmp_dir}/{config.docker['original-mvnw-log-file']}'
            patched_mvnw_log_path = f'{self.tmp_dir}/{config.docker['patched-mvnw-log-file']}'
            if not os.path.exists(original_mvnw_log_path) or not os.path.exists(patched_mvnw_log_path):
                raise FileNotFoundError(f"Mvnw log files not found at {original_mvnw_log_path} or {patched_mvnw_log_path}")

            module_to_coverage_path = {'original': {}, 'patched': {}}
            for module_name in self.module_names:
                local_original_coverage_path = f'{self.tmp_dir}/{module_name.replace('/', '__')}__coverage__original.json'
                local_patched_coverage_path = f'{self.tmp_dir}/{module_name.replace('/', '__')}__coverage__patched.json'
                run_cmd(['docker', 'cp', f'{self.container_name}:{config.docker['original-repo-path']}/{module_name}/target/tia/reports/testwise-coverage-1.json', f'{local_original_coverage_path}'], self.working_dir)
                run_cmd(['docker', 'cp', f'{self.container_name}:{config.docker['patched-repo-path']}/{module_name}/target/tia/reports/testwise-coverage-1.json', f'{local_patched_coverage_path}'], self.working_dir)

                if not os.path.exists(local_original_coverage_path) or not os.path.exists(local_patched_coverage_path):
                    raise FileNotFoundError(f"Coverage files not found at {local_original_coverage_path} or {local_patched_coverage_path}")
                
                module_to_coverage_path['original'][module_name] = local_original_coverage_path
                module_to_coverage_path['patched'][module_name] = local_patched_coverage_path

            return self.MvnwExecResults(original_mvnw_log_path, patched_mvnw_log_path, module_to_coverage_path)
        finally:
            # Ensure container is always removed, even if an exception occurs
            run_cmd(['docker', 'rm', f'{self.container_name}'], self.working_dir)

    def clean_tmp_dirs(self) -> None:
        run_cmd(["rm", "-rf", self.tmp_dir], self.working_dir)
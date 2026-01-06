import subprocess
import logging
import shutil
from pathlib import Path
from src import config
from src.utils import run_cmd
import os
from src.gh.commit_analysis.utils.java_detector import get_java_version
from src.gh.commit_analysis.utils.mvn_log_analyzer import MvnwExecResults

logger = logging.getLogger(__name__)

class CommitDockerizer:
    
    def __init__(self, working_dir: str, repo: str, commit: str, patched_repo_path: str, original_repo_path: str, module_names: list[str], builder_name: str, exec_times: int, timeout: int):
        self.working_dir = working_dir
        self.repo = repo
        self.commit = commit
        self.patched_repo_path = patched_repo_path
        self.original_repo_path = original_repo_path
        self.module_names = module_names
        self.builder_name = builder_name
        self.exec_times = exec_times
        self.timeout = timeout

    @property
    def image_name(self):
        return f"{config.docker['image-name-prefix']}-{self.repo}-{self.commit}".lower()
    
    @property
    def tmp_dir(self):
        return f"{self.working_dir}/{self.image_name.replace('/', '__')}_tmp"
    
    @property
    def container_name(self):
        return f"container-{self.image_name.replace('/', '__')}"

    def image_exists(self) -> bool:
        ls_res = run_cmd(['docker', 'image', 'ls', f'{config.docker['image-name-prefix']}-{self.repo}-{self.commit}'], self.working_dir, capture_output=True)
        return ls_res is not None and config.docker['image-name-prefix'] in ls_res

    def build_commit_docker_image(self):
        try:
            # copy the dockerfile to the working directory
            if not os.path.exists(os.path.join(self.working_dir, 'Dockerfile')):
                shutil.copy(config.docker['dockerfile'], self.working_dir)
            if not os.path.exists(os.path.join(self.working_dir, config.docker['mvn-settings-file'])):
                shutil.copy(config.docker['mvn-settings-file'], self.working_dir)
            dockerfile_path = Path(self.working_dir) / 'Dockerfile'
            
            if not dockerfile_path.exists():
                raise FileNotFoundError(f"Dockerfile not found at {dockerfile_path}")

            java_version = get_java_version(Path(self.patched_repo_path))

            # Determine base image based on Java version
            # For JDK < 8, use azul/zulu-openjdk (eclipse-temurin doesn't support versions below 8)
            # For JDK >= 8, use eclipse-temurin
            try:
                java_version_int = int(java_version)
                if java_version_int < 8:
                    base_image = f"azul/zulu-openjdk:{java_version}"
                else:
                    base_image = f"eclipse-temurin:{java_version}-jdk"
            except ValueError:
                # If version can't be parsed as int, default to eclipse-temurin
                base_image = f"eclipse-temurin:{java_version}-jdk"

            original_repo_path = self.original_repo_path.replace(self.working_dir, '')
            patched_repo_path = self.patched_repo_path.replace(self.working_dir, '')
            
            command_args = [
                "timeout", str(self.timeout), "docker", "buildx", "build", "--builder", self.builder_name, "--load",
                "-f", str(dockerfile_path),
                "-t", self.image_name,
                str(Path(self.working_dir)),
                "--build-arg", f"PATCHED_REPO_DIR={patched_repo_path}",
                "--build-arg", f"ORIGINAL_REPO_DIR={original_repo_path}",
                "--build-arg", f"MODULE_NAMES={','.join(self.module_names)}",
                "--build-arg", f"BASE_IMAGE={base_image}",
                "--build-arg", f"JAVA_VERSION={java_version}",
                "--build-arg", f"EXEC_TIMES={self.exec_times}",
                "--build-arg", f"MVN_SETTINGS_FILE=settings.xml"
            ]

            # Build the Docker image
            run_cmd(command_args, self.working_dir, capture_output=False)
            
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

            original_mvnw_log_paths = []
            patched_mvnw_log_paths = []
            for exec_time in range(1, self.exec_times + 1):
                original_mvnw_log_path = os.path.join(self.tmp_dir, config.docker['host-mvnw-log-path']('original', exec_time))
                patched_mvnw_log_path = os.path.join(self.tmp_dir, config.docker['host-mvnw-log-path']('patched', exec_time))
                if not os.path.exists(original_mvnw_log_path) or not os.path.exists(patched_mvnw_log_path):
                    raise FileNotFoundError(f"Mvnw log files not found at {original_mvnw_log_path} or {patched_mvnw_log_path}")
                
                original_mvnw_log_paths.append(original_mvnw_log_path)
                patched_mvnw_log_paths.append(patched_mvnw_log_path)

            return MvnwExecResults(original_mvnw_log_paths=original_mvnw_log_paths, patched_mvnw_log_paths=patched_mvnw_log_paths, expected_exec_times=self.exec_times)
        finally:
            # Ensure container is always removed, even if an exception occurs
            run_cmd(['docker', 'rm', f'{self.container_name}'], self.working_dir)

    def clean_tmp_dirs(self) -> None:
        run_cmd(["rm", "-rf", self.tmp_dir], self.working_dir)

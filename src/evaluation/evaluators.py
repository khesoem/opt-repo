import json
import os
import random
from src import config as conf
import logging
import subprocess as sp
from src.gh.commit_analysis.utils.mvn_log_analyzer import has_compilation_error, is_exec_successful, MvnwExecResults
from src.utils import run_cmd, pull_image_install_git, create_tmp_container
from src.data.dataset_adapter import DatasetAdapter

class EvalResult:
    def __init__(self, patch_applicable: bool, compile_success: bool, test_success: bool, mvnw_exec_results: MvnwExecResults | None):
        self.patch_applicable = patch_applicable
        self.compile_success = compile_success
        self.test_success = test_success

        self.significant_improvements = mvnw_exec_results.get_significant_test_class_improvements() if mvnw_exec_results is not None else ""
        self.original_exec_times, self.patched_exec_times = mvnw_exec_results.get_total_execution_times() if mvnw_exec_results is not None else ("", "")



class Evaluator:
    def __init__(self, repo: str, after_commit: str, output_analysis_path: str, modified_modules: list[str], versions: list[str], exec_times: int | None, min_p_value: float | None, min_exec_time_improvement: float | None, working_dir: str | None = None):
        self.repo = repo
        self.commit = after_commit
        self.versions = versions
        self.modified_modules = modified_modules

        self.working_dir = working_dir if working_dir is not None else conf.utils['working-dir']
        self.output_analysis_path = output_analysis_path
        
        self.exec_times = exec_times if exec_times is not None else conf.evaluation['exec-times']
        self.min_p_value = min_p_value if min_p_value is not None else conf.perf_commit['min-p-value']
        self.min_exec_time_improvement = min_exec_time_improvement if min_exec_time_improvement is not None else conf.perf_commit['min-exec-time-improvement']
    
    def _prepare_container(self) -> str:
        image_name = pull_image_install_git(self.repo, self.commit, self.working_dir)
        # image_name = "new-img"
        container_name = create_tmp_container(image_name, self.working_dir, replace_entrypoint=True)
        return container_name
    
    def _run_tests(self, container_name: str, tests: list[str] | None = None, should_pass_version: str | None = None) -> tuple[bool, bool, MvnwExecResults]:
        mvnw_log_dir = os.path.join(self.working_dir, "mvnw_logs")
        os.makedirs(mvnw_log_dir, exist_ok=True)

        compile_failure = True
        test_success = True
        
        for i, exec_time in enumerate(range(self.exec_times)):
            original_first = random.random() < 0.5 if i > 0 else True # first exec time is always original first to check for compiler/test/etc.

            for version in self.versions if original_first else self.versions[::-1]:
                mvnw_log_path = os.path.join(mvnw_log_dir, f"mvnw_{exec_time}_{version}.log")
                try:
                    cmd = [
                        "docker",
                        "exec",
                        "--workdir",
                        f"/app/{version}_repo",
                        container_name,
                        "./mvnw",
                        "-pl",
                        ",".join(self.modified_modules),
                        "-am",
                        "test",
                        "-Dsurefire.runOrder=alphabetical",
                        "-DfailIfNoTests=false",
                    ]

                    if tests is not None:
                        cmd.append("-Dtest=" + ",".join(tests))

                    with open(mvnw_log_path, "w") as f:
                        sp.run(
                            cmd,
                            stdout=f,
                            stderr=sp.STDOUT,  # merge stderr into stdout
                            text=True
                        )

                except Exception as e:
                    logging.info(f"{self.repo} - {self.commit} - Error running tests: {e}")
                
                compile_failure = has_compilation_error(mvnw_log_path)
                if compile_failure:
                    if should_pass_version is not None and version == should_pass_version:
                        raise Exception(f"{self.repo} - {self.commit} - Compile failed on original version")
                    return False, False, None
                
                test_success = is_exec_successful(mvnw_log_path)
                if not test_success:
                    if should_pass_version is not None and version == should_pass_version:
                        raise Exception(f"{self.repo} - {self.commit} - Test execution failed on original version")
                    return True, False, None
        
        original_mvnw_log_paths = [os.path.join(mvnw_log_dir, f"mvnw_{exec_time}_{self.versions[0]}.log") for exec_time in range(self.exec_times)]
        patched_mvnw_log_paths = [os.path.join(mvnw_log_dir, f"mvnw_{exec_time}_{self.versions[1]}.log") for exec_time in range(self.exec_times)]
        mvnw_exec_results = MvnwExecResults(original_mvnw_log_paths, patched_mvnw_log_paths, self.exec_times, self.min_p_value, self.min_exec_time_improvement)
        
        return True, True, mvnw_exec_results
    
    def _write_result(self, result: EvalResult) -> None:
        with open(self.output_analysis_path, "w") as f:
            json.dump(result.__dict__, f)



class PatchEvaluator(Evaluator):

    def __init__(self, repo: str, after_commit: str, patch_path: str, output_analysis_path: str, modified_modules: list[str], exec_times: int | None = None, min_p_value: float | None = None, min_exec_time_improvement: float | None = None, working_dir: str | None = None):        
        super().__init__(repo, after_commit, output_analysis_path, modified_modules, ['original', 'new_patched'], exec_times, min_p_value, min_exec_time_improvement)
        self.patch_path = patch_path
    
    def _apply_patch(self, container_name: str) -> bool:
        cmd = [
            "docker",
            "cp",
            self.patch_path,
            f"{container_name}:/app/fix.patch",
        ]
        run_cmd(cmd, self.working_dir)

        cmd = [
            "docker",
            "exec",
            container_name,
            "cp",
            "-r",
            "/app/original_repo",
            "/app/new_patched_repo",
        ]
        result = sp.run(cmd)

        cmd = [
            "docker",
            "exec",
            "--workdir",
            "/app/new_patched_repo",
            container_name,
            "git",
            "apply",
            "/app/fix.patch",
        ]
        result = sp.run(cmd)
        return result.returncode == 0

    def _run_tests(self, container_name: str) -> tuple[bool, bool, dict[str, set[str]]]:
        return super()._run_tests(container_name, should_pass_version="original")

    def _ensure_correct_modules_modified(self) -> None:
        # TODO
        pass

    def evaluate(self) -> None:
        logging.info(f"{self.repo} - {self.commit} - Evaluating patch")
        
        self._ensure_correct_modules_modified()

        container_name = self._prepare_container()
        logging.info(f"{self.repo} - {self.commit} - Prepared container: {container_name}")

        patch_applied = self._apply_patch(container_name)
        logging.info(f"{self.repo} - {self.commit} - Applied patch: {patch_applied}")

        if not patch_applied:
            result = EvalResult(False, False, False, None)

        else:
            compile_success, test_success, mvnw_exec_results = self._run_tests(container_name)
            logging.info(f"{self.repo} - {self.commit} - Run tests: {compile_success}, {test_success}, {mvnw_exec_results}")

            result = EvalResult(True, compile_success, test_success, mvnw_exec_results)
        
        logging.info(f"{self.repo} - {self.commit} - Result: {result.__dict__}")

        self._write_result(result)
        logging.info(f"{self.repo} - {self.commit} - Wrote result")



class TestEvaluator(Evaluator):
    def __init__(self, repo: str, after_commit: str, output_analysis_path: str, modified_modules: list[str], test_patch_path: str, tests: list[str], exec_times: int | None = None, min_p_value: float | None = None, min_exec_time_improvement: float | None = None, working_dir: str | None = None):
        super().__init__(repo, after_commit, output_analysis_path, modified_modules, ['original', 'patched'], exec_times, min_p_value, min_exec_time_improvement, working_dir)
        self.test_patch_path = test_patch_path
        self.tests = tests

    def _run_tests(self, container_name: str) -> tuple[bool, bool, dict[str, set[str]]]:
        return super()._run_tests(container_name, self.tests)
    
    def _apply_test_patch(self, container_name: str) -> bool:
        cmd = [
            "docker",
            "cp",
            self.test_patch_path,
            f"{container_name}:/app/test_addition.patch",
        ]
        run_cmd(cmd, self.working_dir)

        for v in self.versions:
            cmd = [
                "docker",
                "exec",
                "--workdir",
                f"/app/{v}_repo",
                container_name,
                "git",
                "apply",
                "/app/test_addition.patch",
            ]

            try:
                with open(os.path.join(self.working_dir, f"git_apply_{v}.log"), "w") as f:
                    result = sp.run(cmd, stdout=f, stderr=sp.STDOUT, text=True)
                if result.returncode != 0:
                    return False
            except Exception as e:
                logging.info(f"{self.repo} - {self.commit} - Error applying test patch: {e}")
                return False
        
        return True

    def evaluate(self) -> None:
        logging.info(f"{self.repo} - {self.commit} - Evaluating test patch")

        container_name = self._prepare_container()
        logging.info(f"{self.repo} - {self.commit} - Prepared container: {container_name}")

        test_patch_applied = self._apply_test_patch(container_name)
        logging.info(f"{self.repo} - {self.commit} - Applied test patch: {test_patch_applied}")

        if not test_patch_applied:
            result = EvalResult(False, False, False, None)

        else:
            compile_success, test_success, mvnw_exec_results = self._run_tests(container_name)
            logging.info(f"{self.repo} - {self.commit} - Run tests: {compile_success}, {test_success}, {mvnw_exec_results}")

            result = EvalResult(True, compile_success, test_success, mvnw_exec_results)
        
        logging.info(f"{self.repo} - {self.commit} - Result: {result.__dict__}")

        self._write_result(result)
        logging.info(f"{self.repo} - {self.commit} - Wrote result")
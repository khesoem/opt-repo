import os
import json
import re
from src.utils import run_cmd
from src.gh.commit_analysis.commit_static_analyzer import RepoAnalyzer
from src.gh.commit_analysis.utils.pom_manipulator import add_tia_to_pom
from src.reproducibility.dockerizer import CommitDockerizer
import logging
import src.config as conf

class CommitPerfImprovementAnalyzer:
    class TestResult:
        def __init__(self, test_path: str, passed: bool, duration: float, covered_lines: dict[str, list[int]]):
            self.test_path = test_path
            self.passed = passed
            self.duration = duration
            self.covered_lines = covered_lines

    class AnalysisResult:
        def __init__(self, repo: str, commit: str, image_name: str, original_exec_time: float, patched_exec_time: float, covering_test_results: dict[str, 'TestResult']):
            self.repo = repo
            self.commit = commit
            self.image_name = image_name
            self.original_exec_time = original_exec_time
            self.patched_exec_time = patched_exec_time

            self.covering_tests_performance = {}
            for test_path, test_result in covering_test_results.items():
                self.covering_tests_performance[test_path] = {'original': test_result['original'].duration, 'patched': test_result['patched'].duration}

        @property
        def is_improvement_commit(self) -> bool:
            return self.patched_exec_time < self.original_exec_time * (1 - conf.perf_commit['min-exec-time-improvement'])
    
    def __init__(self, repo: str, commit: str, working_dir: str):
        self.repo = repo
        self.commit = commit
        self.working_dir = working_dir

    def _clone_and_checkout_repo(self) -> str:
        repo_dir = self.repo.replace('/', '__') + "_" + self.commit
        clone_path = os.path.join(self.working_dir, repo_dir)
        repo_url = f"git@github.com:{self.repo}.git"

        if not os.path.exists(clone_path):
            run_cmd(["git", "clone", repo_url, repo_dir], self.working_dir)
        run_cmd(["git", "checkout", self.commit], clone_path)

        return clone_path

    def _clone_and_checkout_original_commit(self, clone_path: str) -> str:
        original_clone_path = clone_path + "_original"
        if not os.path.exists(original_clone_path):
            run_cmd(["cp", "-r", clone_path, original_clone_path], self.working_dir)

        parent_commit = run_cmd(["git", "rev-parse", f"{self.commit}^"], original_clone_path).strip()
        run_cmd(["git", "checkout", parent_commit], original_clone_path)

        return original_clone_path

    def _add_testwise_plugin_to_modified_modules(self, clone_path: str, original_clone_path: str) -> None:
        analyzer = RepoAnalyzer(clone_path)
        changed_java_files = analyzer.get_changed_java_src_files(self.commit)
        modified_modules = analyzer.get_modules_for_java_files(changed_java_files)

        for module in modified_modules:
            pom_path = os.path.join(clone_path, module, "pom.xml")
            if os.path.exists(pom_path):
                add_tia_to_pom(pom_path)

            pom_path = os.path.join(original_clone_path, module, "pom.xml")
            if os.path.exists(pom_path):
                add_tia_to_pom(pom_path)

        return modified_modules

    def _check_maven_success(self, log_path: str) -> bool:
        """
        Check if Maven execution was successful by examining the log file.
        
        Args:
            log_path: Path to the Maven execution log file
            
        Returns:
            True if Maven execution was successful, False otherwise
        """
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
            
            # Check for success indicators
            success_indicators = [
                "BUILD SUCCESS",
                "[INFO] BUILD SUCCESS",
                "Tests run:",
                "Tests passed:"
            ]
            
            # Check for failure indicators
            failure_indicators = [
                "BUILD FAILURE",
                "[ERROR] BUILD FAILURE",
                "Tests run: 0",
                "There are test failures",
                "Maven test failed"
            ]
            
            # Look for success indicators
            has_success = any(indicator in log_content for indicator in success_indicators)
            
            # Look for failure indicators
            has_failure = any(indicator in log_content for indicator in failure_indicators)
            
            # If we have explicit failure indicators, it failed
            if has_failure:
                return False
            
            # If we have success indicators and no failure indicators, it succeeded
            if has_success:
                return True
            
        except FileNotFoundError:
            logging.error(f"Maven log file not found: {log_path}")
            return False
        except Exception as e:
            logging.error(f"Error reading Maven log file {log_path}: {e}")
            return False

    def _test_wise_report_to_test_results(self, module_name: str, test_wise_report: str) -> list[TestResult]:
        """
        Convert the test-wise report to a list of TestResult objects.
        
        Args:
            test_wise_report: JSON string containing test-wise coverage report
            
        Returns:
            List of TestResult objects with parsed coverage information
        """
        try:
            f = open(test_wise_report, "r")
            report_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in test-wise report: {e}")
        finally:
            f.close()
        
        test_results = []
        
        for test in report_data.get("tests", []):
            test_path = test.get("uniformPath", "")
            passed = test.get("result", "").upper() == "PASSED"
            duration = test.get("duration", 0.0)
            
            # Parse covered lines for all files across all paths
            covered_lines = {}
            
            for path_info in test.get("paths", []):
                path = path_info.get("path", "")
                for file_info in path_info.get("files", []):
                    file_name = file_info.get("fileName", "")
                    covered_lines_str = file_info.get("coveredLines", "")
                    
                    if file_name and covered_lines_str:
                        # Parse covered lines (handles both single lines and ranges)
                        parsed_lines = self._parse_test_wise_covered_lines(covered_lines_str)
                        # Use full path as the key, handle empty path case
                        if path:
                            full_file_path = f"{module_name}/src/main/java/{path}/{file_name}"
                        else:
                            full_file_path = f"{module_name}/src/main/java/{file_name}"
                        covered_lines[full_file_path] = parsed_lines
            
            test_result = self.TestResult(
                test_path=f"{module_name}/src/test/java/{test_path}",
                passed=passed,
                duration=duration,
                covered_lines=covered_lines
            )
            test_results.append(test_result)
        
        return test_results
    
    def _parse_test_wise_covered_lines(self, covered_lines_str: str) -> list[int]:
        """
        Parse covered lines string that can contain both single lines and ranges.
        
        Args:
            covered_lines_str: String like "8,16,19-21,23,26,30-35,37,39-40"
            
        Returns:
            List of all covered line numbers
        """
        if not covered_lines_str:
            return []
        
        lines = set()
        
        # Split by comma and process each part
        for part in covered_lines_str.split(','):
            part = part.strip()
            if not part:
                continue
                
            if '-' in part:
                # Handle range (e.g., "19-21")
                start, end = map(int, part.split('-', 1))
                lines.update(range(start, end + 1))
            else:
                # Handle single line
                line_num = int(part)
                lines.add(line_num)
        
        return sorted(list(lines))

    def _ignore_modified_tests(self, patch_covering_test_results: dict[str, dict[str, TestResult]], modified_test_files: set[str]) -> dict[str, dict[str, TestResult]]:
        """
        Ignore tests that are modified in the commit.
        """
        for test_path in patch_covering_test_results.keys():
            if '/'.join(test_path.split('/')[:-1]) + '.java' in modified_test_files:
                del patch_covering_test_results[test_path]

        return patch_covering_test_results

    def _get_patch_covering_tests(self, line_changes: dict[str, list[int]], module_to_test_res_path: dict[str, str]) -> set[str]:
        """
        Get the patch covering tests for the original and patched versions.

        Args:
            line_changes: The line changes for the commit, a dictionary from filename to changed lines
            module_to_test_res_path: The module to test result path

        Returns:
            A set of test paths
        """
        patch_covering_tests = set()

        for module_name, test_res_path in module_to_test_res_path.items():
            test_res = self._test_wise_report_to_test_results(module_name, test_res_path)
            for test_result in test_res:
                if not test_result.passed:
                    raise Exception(f"Test {test_result.test_path} failed")
                
                covered_lines = test_result.covered_lines
                for filename, changed_lines in line_changes.items():
                    if filename in covered_lines:
                        if set(changed_lines) & set(covered_lines[filename]):
                            patch_covering_tests.add(test_result.test_path)
        
        return patch_covering_tests

    def _get_patch_covering_test_results(self, line_changes: dict[str, dict[str, list[int]]], original_module_to_test_res_path: dict[str, str], patched_module_to_test_res_path: dict[str, str]) -> dict[str, dict[str, TestResult]]:
        """
        Get the patch covering test results for the original and patched versions.

        Args:
            line_changes: The line changes for the commit
            original_module_to_test_res_path: The module to test result path for the original version
            patched_module_to_test_res_path: The module to test result path for the patched version

        Returns:
            A dictionary of test results for the original and patched versions
            The key is the test path and the value is a dictionary with the original and patched test results
        """


        patch_covering_tests = self._get_patch_covering_tests(line_changes['original'], original_module_to_test_res_path)
        patch_covering_tests.update(self._get_patch_covering_tests(line_changes['patched'], patched_module_to_test_res_path))

        patch_covering_test_results = {}
        for module_name, test_res_path in original_module_to_test_res_path.items():
            test_results = self._test_wise_report_to_test_results(module_name, test_res_path)
            for test_result in test_results:
                if test_result.test_path in patch_covering_tests:
                    patch_covering_test_results[test_result.test_path] = {'original': test_result}
        
        for module_name, test_res_path in patched_module_to_test_res_path.items():
            test_results = self._test_wise_report_to_test_results(module_name, test_res_path)
            for test_result in test_results:
                if test_result.test_path in patch_covering_tests:
                    patch_covering_test_results[test_result.test_path]['patched'] = test_result

        # ensure for each covering test, both original and patched results are present
        for test_path in patch_covering_tests:
            if test_path not in patch_covering_test_results:
                raise Exception(f"Test {test_path} not found in patch covering test results")
            if 'original' not in patch_covering_test_results[test_path] or 'patched' not in patch_covering_test_results[test_path]:
                raise Exception(f"Test {test_path} not found in patch covering test results")

        return patch_covering_test_results

    def _calculate_exec_times(self, patch_covering_test_results: dict[str, dict[str, TestResult]]) -> tuple[float, float]:
        original_exec_time, patched_exec_time = 0.0, 0.0
        for _, test_results in patch_covering_test_results.items():
            original_exec_time += test_results['original'].duration
            patched_exec_time += test_results['patched'].duration
        return original_exec_time, patched_exec_time

    def run_analysis(self) -> AnalysisResult:
        # clone the repo & checkout the commit & before commit
        patched_clone_path = self._clone_and_checkout_repo()
        original_clone_path = self._clone_and_checkout_original_commit(patched_clone_path)


        # add testwise plugin to modified modules
        modified_modules = self._add_testwise_plugin_to_modified_modules(patched_clone_path, original_clone_path)


        # build docker image containing the modified repos and run tests in docker
        dockerizer = CommitDockerizer(self.working_dir, self.repo, self.commit, patched_clone_path, original_clone_path, modified_modules)
        dockerizer.build_commit_docker_image()


        # get the results of executing maven
        mvnw_exec_results = dockerizer.get_mvnw_exec_results()
 

        # check if maven runs successfully on both versions
        patched_success = self._check_maven_success(mvnw_exec_results.patched_mvnw_log_path)
        original_success = self._check_maven_success(mvnw_exec_results.original_mvnw_log_path)
        if not patched_success or not original_success:
            logging.error(f"Maven execution failed - Patched: {patched_success}, Original: {original_success}")
            raise Exception("Maven execution failed")
        logging.info(f"Maven execution successful on both versions")


        # get changed lines of java src files
        repo_analyzer = RepoAnalyzer(patched_clone_path)
        line_changes = repo_analyzer.get_commit_line_changes(self.commit)
        
        # get result of patch covering tests
        patch_covering_test_results = self._get_patch_covering_test_results(line_changes, mvnw_exec_results.module_to_test_res_path['original'], mvnw_exec_results.module_to_test_res_path['patched'])

        # ignore tests that are modified in the commit
        patch_covering_test_results = self._ignore_modified_tests(patch_covering_test_results, repo_analyzer.get_changed_java_test_files(self.commit))

        # compute exec times
        original_exec_time, patched_exec_time = self._calculate_exec_times(patch_covering_test_results)

        return self.AnalysisResult(self.repo, self.commit, dockerizer.image_name, original_exec_time, patched_exec_time, patch_covering_test_results)
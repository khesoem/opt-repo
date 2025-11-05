from typing import Sequence
import re
import numpy as np
from scipy import stats
import src.config as conf

class MvnwExecResults:
    def __init__(self, original_mvnw_log_paths: list[str], patched_mvnw_log_paths: list[str]):
        self.original_mvnw_log_paths = original_mvnw_log_paths
        self.patched_mvnw_log_paths = patched_mvnw_log_paths
    
    def is_successful(self) -> bool:
        return all(self._is_exec_successful(log_path) for log_path in self.original_mvnw_log_paths) and all(self._is_exec_successful(log_path) for log_path in self.patched_mvnw_log_paths)
    
    def _is_exec_successful(self, log_path: str) -> bool:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
            return not("BUILD FAILURE" in log_content or "BUILD ERROR" in log_content or not "BUILD SUCCESS" in log_content)

    def _get_per_test_execution_times(self, log_path: str) -> dict[str, float]:
        """
        Get the execution times of the tests in the log file.

        Returns:
            A dictionary of test class names and their execution times in seconds
        """
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
        # Pattern to match lines like:
        # [INFO] Tests run: 9, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.098 s - in org.apache.pulsar.client.impl.TypedMessageBuilderImplTest
        # [INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.621 s -- in io.trino.spi.block.TestIntegerArrayBlockEncoding
        # Supports: ms (milliseconds), s (seconds), min (minutes), h (hours)
        pattern = r'\[INFO\] Tests run:.*?Time elapsed:\s+([\d.]+)\s+(ms|s|min|h)\s+-+\s+in\s+(.+)'
        
        test_times = {}
        for match in re.finditer(pattern, log_content):
            time_value = float(match.group(1))
            time_unit = match.group(2)
            test_class = match.group(3).strip()
            
            # Convert to seconds
            if time_unit == 'ms':
                time_seconds = time_value / 1000
            elif time_unit == 's':
                time_seconds = time_value
            elif time_unit == 'min':
                time_seconds = time_value * 60
            elif time_unit == 'h':
                time_seconds = time_value * 3600
            else:
                # Fallback: assume seconds
                time_seconds = time_value
            
            test_times[test_class] = time_seconds
        
        return test_times

    def _is_exec_time_improvement_significant(
        self
    ) -> bool:
        original_times, patched_times = self.get_valid_total_execution_times()
        return self.get_improvement_p_value(original_times, patched_times) < conf.perf_commit['min-p-value']
    
    def _get_total_execution_time(self, log_path: str) -> float:
        return sum(self._get_per_test_execution_times(log_path).values())
    
    def get_valid_total_execution_times(self) -> tuple[list[float], list[float]]:
        original_total_execution_times, patched_total_execution_times = self.get_total_execution_times()
        return (original_total_execution_times[1:], patched_total_execution_times[1:]) # ignore the first execution time
    
    def get_total_execution_times(self) -> tuple[list[float], list[float]]:
        return [self._get_total_execution_time(log_path) for log_path in self.original_mvnw_log_paths], [self._get_total_execution_time(log_path) for log_path in self.patched_mvnw_log_paths]
    
    def is_improvement_commit(self) -> bool:
        return self._is_exec_time_improvement_significant()

    def get_execution_improvement(self) -> float:
        original_times, patched_times = self.get_valid_total_execution_times()
        return (sum(original_times) - sum(patched_times)) / sum(original_times)
    
    def get_improvement_p_value(
        self, original_times: list[float], patched_times: list[float]
    ) -> float:
        if len(original_times) != len(patched_times):
            raise ValueError("original_times and patched_times must have the same length")

        original_times_array = np.asarray(original_times, dtype=float)
        patched_times_array = np.asarray(patched_times, dtype=float)

        c = 1.0 - conf.perf_commit['min-exec-time-improvement']  # we test μ1 < c * μ2
        original_times_array_scaled = c * original_times_array

        # Welch's t-test, one-sided: H1: mean(v1) < mean(v2_scaled)
        res = stats.ttest_ind(patched_times_array, original_times_array_scaled, equal_var=False, alternative='less')

        # return pvalue as float
        return float(res.pvalue)
    
    def get_significant_test_time_changes(self) -> dict[str, list[str]]:
        all_original_test_times = {}
        all_patched_test_times = {}
        significant_test_time_changes = {'original_outperforms_patched': [], 'patched_outperforms_original': []}
        for original_log_path, patched_log_path in zip(self.original_mvnw_log_paths[1:], self.patched_mvnw_log_paths[1:]):
            original_test_times = self._get_per_test_execution_times(original_log_path)
            patched_test_times = self._get_per_test_execution_times(patched_log_path)

            for test_class in original_test_times.keys():
                if not test_class in all_original_test_times:
                    all_original_test_times[test_class] = []
                all_original_test_times[test_class].append(original_test_times[test_class])
            for test_class in patched_test_times.keys():
                if not test_class in all_patched_test_times:
                    all_patched_test_times[test_class] = []
                all_patched_test_times[test_class].append(patched_test_times[test_class])

        for test_class in all_original_test_times.keys():
            if len(all_original_test_times[test_class]) == 5 and len(all_patched_test_times[test_class]) == 5:
                if self.get_improvement_p_value(all_original_test_times[test_class], all_patched_test_times[test_class]) < conf.perf_commit['min-p-value']:
                    significant_test_time_changes['original_outperforms_patched'].append(test_class)
                elif self.get_improvement_p_value(all_patched_test_times[test_class], all_original_test_times[test_class]) < conf.perf_commit['min-p-value']:
                    significant_test_time_changes['patched_outperforms_original'].append(test_class)

        return significant_test_time_changes
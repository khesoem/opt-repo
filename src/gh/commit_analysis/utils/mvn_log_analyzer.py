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
        self,
        original_times: Sequence[float],
        patched_times: Sequence[float]
    ) -> bool:
        res = self.get_improvement_p_value(original_times, patched_times)
        return bool(res.pvalue < conf.perf_commit['min-p-value'])
    
    def _get_total_execution_time(self, log_path: str) -> float:
        return sum(self._get_per_test_execution_times(log_path).values())
    
    def get_valid_total_execution_times(self) -> tuple[list[float], list[float]]:
        original_total_execution_times, patched_total_execution_times = self.get_total_execution_times()
        return (original_total_execution_times[1:], patched_total_execution_times[1:]) # ignore the first execution time
    
    def get_total_execution_times(self) -> tuple[list[float], list[float]]:
        return [self._get_total_execution_time(log_path) for log_path in self.original_mvnw_log_paths], [self._get_total_execution_time(log_path) for log_path in self.patched_mvnw_log_paths]
    
    def is_improvement_commit(self) -> bool:
        original_times, patched_times = self.get_valid_total_execution_times()
        return self._is_exec_time_improvement_significant(original_times, patched_times)

    def get_execution_improvement(self) -> float:
        original_times, patched_times = self.get_valid_total_execution_times()
        return (original_times - patched_times) / original_times
    
    def get_improvement_p_value(
        self,
        original_times: Sequence[float],
        patched_times: Sequence[float]
    ) -> float:
        if len(original_times) != len(patched_times):
            raise ValueError("original_times and patched_times must have the same length")
        original_times_array = np.asarray(original_times, dtype=float)
        patched_times_array = np.asarray(patched_times, dtype=float)

        c = 1.0 - conf.perf_commit['min-exec-time-improvement']  # we test μ1 < c * μ2
        original_times_array_scaled = c * original_times_array

        # Welch's t-test, one-sided: H1: mean(v1) < mean(v2_scaled)
        res = stats.ttest_ind(patched_times_array, original_times_array_scaled, equal_var=False, alternative='less')

        return res.pvalue
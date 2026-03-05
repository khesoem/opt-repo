import json
import ast
import os
import fcntl
import pandas as pd
import src.config as conf
from tempfile import NamedTemporaryFile
import shutil

DATASET_PATH = conf.data["dataset-path"]
LOCK_FILE_PATH = DATASET_PATH + ".lock"

class DatasetAdapter:
    """Process-safe adapter for managing performance dataset with file-based locking."""

    def __init__(self):
        # Each process gets its own instance
        # We'll reload from disk when needed to ensure we have the latest data
        self.df = None

    @staticmethod
    def _parse_serialized_field(value, expected_type):
        """Parse values that may be JSON, Python literal, or over-quoted."""
        if isinstance(value, expected_type):
            return value
        if isinstance(value, (dict, list)):
            return value if isinstance(value, expected_type) else None
        if value is None or pd.isna(value):
            return None
        if not isinstance(value, str):
            return None

        def _peel_quotes(text: str) -> str:
            parsed = text.strip()
            while len(parsed) >= 2 and parsed[0] == parsed[-1] and parsed[0] in ("'", '"'):
                parsed = parsed[1:-1].strip()
            return parsed

        raw = value.strip()
        candidates = [
            raw,
            _peel_quotes(raw),
            _peel_quotes(raw.replace('""', '"')),
            _peel_quotes(raw.replace('\\"', '"')),
            _peel_quotes(raw.rstrip('"')),
        ]

        seen = set()
        for candidate in candidates:
            if candidate in seen or candidate == "":
                continue
            seen.add(candidate)
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(candidate)
                except (json.JSONDecodeError, ValueError, SyntaxError):
                    continue

                # Handle values accidentally serialized multiple times.
                for _ in range(3):
                    if not isinstance(parsed, str):
                        break
                    inner = parsed.strip()
                    nested_parsed = None
                    for nested_parser in (json.loads, ast.literal_eval):
                        try:
                            nested_parsed = nested_parser(inner)
                            break
                        except (json.JSONDecodeError, ValueError, SyntaxError):
                            continue
                    if nested_parsed is None:
                        break
                    parsed = nested_parsed

                if isinstance(parsed, expected_type):
                    return parsed

        return None

    def _get_file_lock(self):
        """Get a file lock for cross-process synchronization."""
        # Ensure directory exists
        lock_dir = os.path.dirname(LOCK_FILE_PATH)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
        lock_file = open(LOCK_FILE_PATH, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return lock_file
    
    def _load_dataset(self) -> pd.DataFrame:
        """Load existing dataset or create an empty one."""
        if os.path.exists(DATASET_PATH):
            df = pd.read_csv(DATASET_PATH)
            df["test_class_improvements"] = df["test_class_improvements"].apply(
                lambda value: self._parse_serialized_field(value, dict)
            )
            df["modified_modules"] = df["modified_modules"].apply(
                lambda value: self._parse_serialized_field(value, list)
            )
            df["changed_files"] = df["changed_files"].apply(
                lambda value: self._parse_serialized_field(value, list)
            )
            # Convert nullable numeric columns to nullable integer dtype.
            df["issue_number"] = pd.to_numeric(df["issue_number"], errors="coerce").astype("Int64")
            df["pr_number"] = pd.to_numeric(df["pr_number"], errors="coerce").astype("Int64")
        else:
            df = pd.DataFrame({
                "repo": pd.Series(dtype="string"),
                "after_commit": pd.Series(dtype="string"),
                "issue_number": pd.Series(dtype="Int64"),
                "exec_status": pd.Series(dtype="string"),
                "exec_time_improvement": pd.Series(dtype="float64"),
                "p_value": pd.Series(dtype="float64"),
                "test_class_improvements": pd.Series(dtype="object"),
                "before_commit": pd.Series(dtype="string"),
                "pr_number": pd.Series(dtype="Int64"),
                "is_improvement_per_manual_analysis": pd.Series(dtype="string"),
                "modified_modules": pd.Series(dtype="object"),
                "changed_files": pd.Series(dtype="object"),
            })
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)
            df.to_csv(DATASET_PATH, index=False)
        return df
    
    def get_dataset(self) -> pd.DataFrame:
        """Get the dataset, loading it if not already loaded."""
        if self.df is None:
            self.df = self._load_dataset()
        return self.df

    def add_or_update_commit(
        self,
        repo: str,
        after_commit: str,
        issue_number: int | None,
        exec_status: str | None,
        exec_time_improvement: float | None,
        p_value: float | None,
        test_class_improvements: dict[str, float] | None,
        before_commit: str | None,
        pr_number: int | None,
        is_improvement_per_manual_analysis: bool | None,
        modified_modules: list[str] | None,
        changed_files: list[str] | None,
    ):
        """Process-safe add or update of a commit record using file locking."""
        new_row = {
            "repo": repo,
            "after_commit": after_commit,
            "issue_number": issue_number,
            "exec_status": exec_status,
            "exec_time_improvement": exec_time_improvement,
            "p_value": p_value,
            "test_class_improvements": test_class_improvements,
            "before_commit": before_commit,
            "pr_number": pr_number,
            "is_improvement_per_manual_analysis": is_improvement_per_manual_analysis,
            "modified_modules": modified_modules,
            "changed_files": changed_files,
        }

        # Acquire file lock for cross-process synchronization
        lock_file = self._get_file_lock()
        try:
            # Reload from disk to get the latest data (important for multiprocessing)
            df = self._load_dataset()
            
            # Check if record exists
            mask = (df["repo"] == repo) & (df["after_commit"] == after_commit)
            if mask.any():
                for key, value in new_row.items():
                    if value is not None:
                        df.loc[mask, key] = value
            else:
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

            # Save atomically
            self._atomic_save(df)
            
            # Update in-memory copy
            self.df = df
        finally:
            # Release lock
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

    def _atomic_save(self, df: pd.DataFrame):
        """Safely save DataFrame to CSV using a temporary file and rename."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)
        
        # Prepare DataFrame for CSV (convert test_class_improvements back to JSON string)
        df_to_save = df.copy()
        df_to_save["test_class_improvements"] = [
            json.dumps(val) if val is not None else None 
            for val in df_to_save["test_class_improvements"]
        ]
        df_to_save["modified_modules"] = [
            json.dumps(val) if val is not None else None
            for val in df_to_save["modified_modules"]
        ]
        df_to_save["changed_files"] = [
            json.dumps(val) if val is not None else None
            for val in df_to_save["changed_files"]
        ]
        
        tmp_file = NamedTemporaryFile(delete=False, dir=os.path.dirname(DATASET_PATH), mode="w", suffix=".csv")
        try:
            df_to_save.to_csv(tmp_file.name, index=False)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        finally:
            tmp_file.close()
        shutil.move(tmp_file.name, DATASET_PATH)
    
    def contains(self, repo: str, after_commit: str) -> bool:
        """Check if a after_commit exists in the dataset (reads latest from disk)."""
        lock_file = self._get_file_lock()
        try:
            df = self._load_dataset()
            mask = (df["repo"] == repo) & (df["after_commit"] == after_commit)
            return mask.any()
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
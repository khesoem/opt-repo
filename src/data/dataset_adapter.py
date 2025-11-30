import json
import os
import threading
import pandas as pd
import src.config as conf
from tempfile import NamedTemporaryFile
import shutil

DATASET_PATH = conf.data["dataset-path"]

class DatasetAdapter:
    """Thread-safe singleton adapter for managing performance dataset."""

    _instance = None
    _instance_lock = threading.Lock()  # Protect singleton creation
    _write_lock = threading.Lock()     # Protect concurrent writes

    def __new__(cls):
        """Ensure only one instance exists, safely."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:  # double-checked locking
                    cls._instance = super(DatasetAdapter, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, "df"):
            self.df = self._create_or_fetch_dataset()

    def _create_or_fetch_dataset(self) -> pd.DataFrame:
        """Load existing dataset or create an empty one."""
        if os.path.exists(DATASET_PATH):
            df = pd.read_csv(DATASET_PATH)
            df["test_class_improvements"] = [json.loads(test_class_improvements) if test_class_improvements is not None else None for test_class_improvements in df["test_class_improvements"]]
        else:
            df = pd.DataFrame({
                "repo": pd.Series(dtype="string"),
                "commit_hash": pd.Series(dtype="string"),
                "issue_number": pd.Series(dtype="Int64"),
                "exec_status": pd.Series(dtype="string"),
                "exec_time_improvement": pd.Series(dtype="float64"),
                "p_value": pd.Series(dtype="float64"),
                "test_class_improvements": pd.Series(dtype="object"),
            })
            df.to_csv(DATASET_PATH, index=False)
        return df
    
    def get_dataset(self) -> pd.DataFrame:
        return self.df

    def add_or_update_commit(
        self,
        repo: str,
        commit_hash: str,
        issue_number: int | None,
        exec_status: str | None,
        exec_time_improvement: float | None,
        p_value: float | None,
        test_class_improvements: dict[str, float] | None,
    ):
        """Thread-safe add or update of a commit record."""
        new_row = {
            "repo": repo,
            "commit_hash": commit_hash,
            "issue_number": issue_number,
            "exec_status": exec_status,
            "exec_time_improvement": exec_time_improvement,
            "p_value": p_value,
            "test_class_improvements": json.dumps(test_class_improvements) if test_class_improvements is not None else None,
        }

        with self._write_lock:
            # Check if record exists
            mask = (self.df["repo"] == repo) & (self.df["commit_hash"] == commit_hash)
            if mask.any():
                for key, value in new_row.items():
                    if value is not None:
                        self.df.loc[mask, key] = value
            else:
                self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)

            self._atomic_save()

    def _atomic_save(self):
        """Safely save to CSV using a temporary file and rename."""
        tmp_file = NamedTemporaryFile(delete=False, dir=os.path.dirname(DATASET_PATH), mode="w", suffix=".csv")
        try:
            self.df.to_csv(tmp_file.name, index=False)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        finally:
            tmp_file.close()
        shutil.move(tmp_file.name, DATASET_PATH)
    
    def contains(self, repo: str, commit: str) -> bool:
        mask = (self.df["repo"] == repo) & (self.df["commit_hash"] == commit)
        return mask.any()
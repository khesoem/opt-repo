import json
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
            if "test_class_improvements" in df.columns:
                df["test_class_improvements"] = [
                    json.loads(test_class_improvements) if pd.notna(test_class_improvements) and test_class_improvements is not None else None 
                    for test_class_improvements in df["test_class_improvements"]
                ]
            # convert issue_number and pr_number to int. if not a number, set to None
            df["issue_number"] = df["issue_number"].apply(lambda x: int(x) if pd.notna(x) and isinstance(x, float) else None)
            df["pr_number"] = df["pr_number"].apply(lambda x: int(x) if pd.notna(x) and isinstance(x, float) else None)
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
    ):
        """Process-safe add or update of a commit record using file locking."""
        new_row = {
            "repo": repo,
            "after_commit": after_commit,
            "issue_number": issue_number,
            "exec_status": exec_status,
            "exec_time_improvement": exec_time_improvement,
            "p_value": p_value,
            "test_class_improvements": json.dumps(test_class_improvements) if test_class_improvements is not None else None,
            "before_commit": before_commit,
            "pr_number": pr_number,
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
        if "test_class_improvements" in df_to_save.columns:
            df_to_save["test_class_improvements"] = [
                json.dumps(val) if val is not None else None 
                for val in df_to_save["test_class_improvements"]
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
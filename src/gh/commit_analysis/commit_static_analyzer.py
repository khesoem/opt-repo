import sys
import subprocess
import re
from src.utils import run_cmd
from typing import Set, Dict
from pathlib import Path

class RepoAnalyzer:
    def __init__(self, repo_path: str):
        if repo_path is None:
            self.repo_path = None
        else:
            self.repo_path = Path(repo_path)

    def parse_name_status(self, line: str) -> Dict[str, str]:
        """
        Parse a single line from `git diff-tree --name-status` (with -M -C -m).
        """
        parts = line.rstrip("\n").split("\t")
        if not parts or parts[0] == "":
            return {}

        status_raw = parts[0]
        if status_raw and status_raw[0] in ("R", "C") and len(status_raw) > 1:
            if len(parts) < 3:
                return {}
            old_path, new_path = parts[1], parts[2]
        else:
            status_code = status_raw
            # formats: <S>\tpath OR 'D\tpath'
            if len(parts) < 2:
                return {}
            path = parts[1]
            if status_code == "D":
                old_path, new_path = path, None
            elif status_code == "M":
                old_path, new_path = path, path
            else:
                old_path, new_path = None, path

        return {
            "old_path": old_path,
            "new_path": new_path,
        }

    def is_java_src_path(self, p: str) -> bool:
        return p.lower().endswith(".java") and not 'test' in p.lower() and not 'generated' in p.lower()
    
    def is_java_test_path(self, p: str) -> bool:
        return p.lower().endswith(".java") and '/test/' in p.lower() and not 'generated' in p.lower()

    def get_changed_java_test_files(self, commit: str) -> Set[str]:
        out = run_cmd(
            cmd=["git", "diff-tree", "-r", "--no-commit-id", "--name-status", "-M", "-C", "-m", commit],
            path=str(self.repo_path)
        )
        
        entries = set()
        for line in out.splitlines():
            rec = self.parse_name_status(line)
            if not rec:
                continue

            if rec.get('old_path') != rec.get('new_path'):
                # We only care about changes, not renames/copies
                continue

            path = rec.get("old_path")

            # Keep if it is a .java src file
            if not (self.is_java_test_path(path)):
                continue

            entries.add(path)
        
        return entries

    def diff_to_java_src_files(self, diff_output: str) -> Set[str]:
        entries = set()
        for line in diff_output.splitlines():
            rec = self.parse_name_status(line)
            if not rec:
                continue

            if rec.get('old_path') != rec.get('new_path'):
                # We only care about changes, not renames/copies
                continue

            path = rec.get("old_path")

            # Keep if it is a .java src file
            if not (self.is_java_src_path(path)):
                continue

            entries.add(path)

        return entries

    def get_changed_java_src_files(self, commit: str) -> Set[str]:
        # Use diff-tree to get paths changed by exactly this commit.
        # -r: recurse, --no-commit-id: don’t show commit id,
        # -M/-C: detect renames/copies, -m: handle merges (per-parent); we’ll dedupe.
        diff_output = run_cmd(
            cmd=["git", "diff-tree", "-r", "--no-commit-id", "--name-status", "-M", "-C", "-m", commit],
            path=str(self.repo_path)
        )  

        return self.diff_to_java_src_files(diff_output)
    
    def get_changed_java_src_files_between_commits(self, before_commit: str, after_commit: str) -> Set[str]:
        # Use diff-tree to get paths changed by exactly this commit.
        # -r: recurse, --no-commit-id: don’t show commit id,
        # -M/-C: detect renames/copies, -m: handle merges (per-parent); we’ll dedupe.
        diff_output = run_cmd(
            cmd=["git", "diff-tree", "-r", "--no-commit-id", "--name-status", "-M", "-C", "-m", before_commit, after_commit],
            path=str(self.repo_path)
        )  

        return self.diff_to_java_src_files(diff_output)

    def get_commit_line_changes(self, commit: str) -> Dict[str, Dict[str, list[int]]]:
        """
        Get line changes for Java source files in a commit.
        
        Args:
            commit: The commit hash to analyze
            
        Returns:
            Dictionary mapping file paths to dictionaries with 'original' and 'patched' keys
            containing lists of line numbers
        """
        changed_files = self.get_changed_java_src_files(commit)
        line_changes = {'original': {}, 'patched': {}}
        
        for file_path in changed_files:
            try:
                # Get the diff for this specific file in the commit
                diff_output = run_cmd(
                    cmd=["git", "show", "--format=", "--no-merges", commit, "--", file_path],
                    path=str(self.repo_path)
                )
                
                removed_lines, added_lines = self._parse_diff_lines(diff_output)
                line_changes['original'][file_path] = sorted(list(removed_lines))
                line_changes['patched'][file_path] = sorted(list(added_lines))
                
            except subprocess.CalledProcessError as e:
                # File might not exist in the commit or other git issues
                raise RuntimeError(f"Could not get diff for {file_path}: {e}") from e
        
        return line_changes
    
    def _parse_diff_lines(self, diff_output: str) -> tuple[Set[int], Set[int]]:
        """
        Parse git diff output to extract removed and added line numbers.
        
        Args:
            diff_output: The raw diff output from git
            
        Returns:
            Tuple of (removed_lines, added_lines) as sets of line numbers
        """
        removed_lines = set()
        added_lines = set()
        
        lines = diff_output.splitlines()
        old_line_num = 0
        new_line_num = 0
        
        for line in lines:
            if line.startswith('@@'):
                # Parse the hunk header: @@ -old_start,old_count +new_start,new_count @@
                match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
                if match:
                    old_line_num = int(match.group(1))
                    new_line_num = int(match.group(3))
            elif line.startswith('-') and not line.startswith('---'):
                # Removed line
                removed_lines.add(old_line_num)
                old_line_num += 1
            elif line.startswith('+') and not line.startswith('+++'):
                # Added line
                added_lines.add(new_line_num)
                new_line_num += 1
            elif line.startswith(' '):
                # Context line (unchanged)
                old_line_num += 1
                new_line_num += 1
            # Skip other lines like file headers
        
        return removed_lines, added_lines

    def get_modules_for_java_files(self, java_files: Set[str]) -> Set[str]:
        """
        Given a set of Java files, return a mapping of module names to their Java files.
        """
        modules = set()
        for f in java_files:
            # First find the first pom.xml in parent directories and then use the directory name as the module name.
            cur_path = self.repo_path / f
            while cur_path != self.repo_path and not (cur_path / "pom.xml").exists():
                cur_path = cur_path.parent

            if (cur_path / "pom.xml").exists():
                modules.add(str(cur_path.relative_to(self.repo_path)))

        return modules


def main():
    RepoAnalyzer("/home/khesoem/postdoc-eth/projects/optimization-dataset/code/tmp/quarkus").get_modules_for_java_files({"independent-projects/qute/core/src/main/java/io/quarkus/qute/JsonEscaper.java", "t"})

if __name__ == "__main__":
    main()

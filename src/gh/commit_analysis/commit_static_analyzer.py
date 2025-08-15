import sys
from src.gh.commit_analysis.utils.utils import run_cmd
from typing import Set, Dict
from pathlib import Path

class RepoAnalyzer:
    def __init__(self, repo_path: str):
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

    def get_changed_java_files(self, commit: str) -> Set[str]:
        # Use diff-tree to get paths changed by exactly this commit.
        # -r: recurse, --no-commit-id: don’t show commit id,
        # -M/-C: detect renames/copies, -m: handle merges (per-parent); we’ll dedupe.
        out = run_cmd(
            cmd="git",
            path=str(self.repo_path),
            args=["diff-tree", "-r", "--no-commit-id", "--name-status", "-M", "-C", "-m", commit]
        )

        entries = set()
        for line in out.splitlines():
            rec = self.parse_name_status(line)
            if not rec:
                continue

            if rec.get('old_path') != rec.get('new_path'):
                # We only care about changes, not renames/copies
                print(rec.get('old_path'), rec.get('new_path'), file=sys.stderr)
                continue

            path = rec.get("old_path")

            # Keep if either old or new side is a .java src file
            if not (self.is_java_src_path(path)):
                continue

            entries.add(path)

        return entries

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
                modules.add(cur_path.relative_to(self.repo_path).name)

        return modules

def main():
    RepoAnalyzer("/home/khesoem/postdoc-eth/projects/optimization-dataset/code/tmp/quarkus").get_modules_for_java_files({"independent-projects/qute/core/src/main/java/io/quarkus/qute/JsonEscaper.java", "t"})

if __name__ == "__main__":
    main()

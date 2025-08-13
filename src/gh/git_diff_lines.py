#!/usr/bin/env python3
"""
git_diff_lines.py

Given a commit-ish in a local Git repo, print:
  1) all added lines
  2) all lines in the NEW version that appear immediately after a removed line

Notes:
- Uses the first parent for merge commits (same as `git show` default).
- Skips binary diffs.
- Outputs plain text by default; use --json for machine-readable output.
- The “after a removed line” list has one entry per removed line. If a hunk ends with
  deletions (e.g., deletions at EOF), there is no “after” line to record for those.
"""

import argparse
import json
import re
import subprocess
import sys
from typing import List, Dict

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

def run_git_show(repo: str, commit: str) -> str:
    # -U1 so we can see the first unchanged line after a deletion-only hunk
    # --format= suppresses commit headers; we only want the diff body
    cmd = [
        "git", "-C", repo,
        "diff", "-m", "--format=", "--unified=1",
        "--no-color", "--no-ext-diff", f"{commit}~1", commit
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        return out
    except subprocess.CalledProcessError as e:
        print(e.output, file=sys.stderr)
        raise SystemExit(1)

def parse_diff(diff_text: str):
    """
    Parse the unified diff and return two lists:
      added_lines:      List[Dict{file, line, text}]
      after_removed:    List[Dict{file, line, text}]
    """
    added_lines = set()
    after_removed = set()

    cur_file = None
    in_hunk = False
    new_lineno = None

    pending_deletions = 0  # count of '-' lines seen since the last non-'-' line

    # We derive the filename from the +++ b/… line when available
    for raw in diff_text.splitlines():
        line = raw.rstrip("\n")

        # File headers
        if line.startswith("diff --git "):
            cur_file = None
            in_hunk = False
            pending_deletions = 0
            continue

        if line.startswith("Binary files ") and " differ" in line:
            # skip binary
            cur_file = None
            in_hunk = False
            pending_deletions = 0
            continue

        if line.startswith("+++ "):
            # e.g. "+++ b/path/to/file" or "+++ /dev/null"
            path = line[4:].strip()
            if path == "/dev/null":
                cur_file = None  # file deleted; still fine (we'll have no additions)
            else:
                # Strip leading a/ or b/
                cur_file = path.split(None, 1)[0]
                if cur_file.startswith("a/") or cur_file.startswith("b/"):
                    cur_file = cur_file[2:]
            continue

        if line.startswith("--- "):
            # old path; not used
            continue

        # Hunk header
        m = HUNK_RE.match(line)
        if m:
            in_hunk = True
            pending_deletions = 0
            # old_start, old_len = m.group(1), m.group(2) or '1'
            new_start = int(m.group(3))
            # new_len = int(m.group(4) or '1')
            new_lineno = new_start - 1  # will increment as we consume '+' or ' ' lines
            continue

        if not in_hunk or cur_file is None:
            # Not inside a tracked text hunk or no file target
            continue

        if line.startswith("\\ No newline at end of file"):
            # Metadata line — ignore
            continue

        # Diff body lines: ' ', '+', '-'
        tag = line[:1]
        content = line[1:] if line else ""

        if tag == "-":
            # Removal: does not advance new file line counter
            pending_deletions += 1

        elif tag == "+":
            # Addition: first, satisfy any pending deletions with THIS new line
            if pending_deletions:
                # The new line will be placed at new_lineno + 1
                for _ in range(pending_deletions):
                    after_removed.add(f"{cur_file}:{new_lineno + 1}")
                pending_deletions = 0

            # Record this added line
            new_lineno += 1
            added_lines.add(f"{cur_file}:{new_lineno}")

        elif tag == " ":
            # Context in the NEW file: also the “after” target if deletions are pending
            if pending_deletions:
                for _ in range(pending_deletions):
                    after_removed.add(f"{cur_file}:{new_lineno + 1}")
                pending_deletions = 0

            new_lineno += 1

        else:
            # Unexpected; ignore safely
            pass

        # If the hunk ends right after several '-' lines, pending_deletions will
        # be > 0 here, but we only attach an “after” line when we see the next
        # '+ or space' inside the hunk. Deletions at EOF thus produce no after-line.

    return added_lines, after_removed

def get_commit_line_changes(commit: str, repo: str = "repo"):
    diff_text = run_git_show(repo, commit)
    return parse_diff(diff_text)  # -> (added_lines, after_removed)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get added lines and lines after removed lines in a Git commit.")
    parser.add_argument("--commit", help="The commit hash or reference to analyze.")
    parser.add_argument("--repo", default=".", help="Path to the Git repository (default: current directory).")

    args = parser.parse_args()

    added_lines, after_removed = get_commit_line_changes(args.commit, args.repo)

    for l in sorted(added_lines):
        print(f"Added: {l}")

    for l in sorted(after_removed):
        print(f"After-removed: {l}")
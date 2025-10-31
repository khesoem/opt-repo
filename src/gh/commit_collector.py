from pathlib import Path
import time
import re
import pandas as pd
from src.data.dataset_adapter import DatasetAdapter
from src.llm.openai import *
from src.llm.invocation import Prompt
import src.config as conf
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException
from github.Repository import Repository
from github.Commit import Commit
import logging
from datetime import datetime, timedelta, timezone
from typing import Set

class CommitCollector:
    def __init__(self):
        access_token = conf.github['access-token']
        auth = Auth.Token(access_token)
        self.g = Github(auth=auth)
        self.gpt5_nano = GPT5_Nano(read_from_cache=True, save_to_cache=True)
        self.gpt5_codex = GPT5_Codex(read_from_cache=True, save_to_cache=True)
        self.start_date = conf.perf_commit['start-date']
        self.min_stars = conf.perf_commit['min-stars']
        self.max_commit_files = conf.perf_commit['max-files']
        self.dataset = DatasetAdapter()
        self.processed_commits = set()

        # Load processed commits from previous logs
        for log_file in ['logs/logging_2025-10-30-15-26.log', 'logs/logging_2025-10-30-18-41.log', 'logs/logging_2025-10-30-21-25.log']:
            with open(log_file, 'r') as f:
                for line in f:
                    if 'root INFO Commit' in line:
                        commit_hash = line.split('root INFO Commit ')[1].split(' ')[0].strip()
                        self.processed_commits.add(commit_hash)
                    if 'root INFO Skipping commit' in line:
                        commit_hash = line.split('root INFO Skipping commit ')[1].split(' ')[0].strip()
                        self.processed_commits.add(commit_hash)

    def get_popular_repos(self):
        query = f"pushed:>{self.start_date} language:Java stars:>{self.min_stars} archived:false"
        repositories = self.g.search_repositories(query=query, sort="stars", order="desc")
        logging.info(f"Fetch results for {query}.")
        return repositories

    def iter_popular_repos_segmented(self):
        """
        Work around GitHub Search API's 1,000 result cap by segmenting the search
        across pushed-date windows and deduplicating repositories across windows.
        """
        # Build rolling windows from now backwards to start_date
        start_boundary = datetime.strptime(self.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        window_end = datetime.now(timezone.utc)
        window_size = timedelta(days=1)
        seen_repo_ids: Set[int] = set()

        while window_end > start_boundary:
            window_start = max(start_boundary, window_end - window_size)

            # Construct segmented query for this window (inclusive dates)
            pushed_range = f"pushed:{window_start.date()}..{window_end.date()}"
            query = f"{pushed_range} language:Java stars:>{self.min_stars} archived:false"
            logging.info(f"Segmented fetch for {query}.")

            repos_window = self.g.search_repositories(query=query, sort="stars", order="desc")

            # Iterate this window and deduplicate
            for repo in repos_window:
                if getattr(repo, 'id', None) in seen_repo_ids:
                    continue
                if getattr(repo, 'id', None) is not None:
                    seen_repo_ids.add(repo.id)
                yield repo

            # Move window backwards
            window_end = window_start

    def get_diff(self, commit: Commit) -> str:
        diff = ""
        for f in commit.files:
            if f.patch:
                diff += f"--- {f.filename}\n"
                diff += f.patch + '\n'
        return diff

    def extract_fixed_issues(self, commit_message: str, repo: Repository) -> Set[int]:
        """
        Extract issue numbers from commit message that are explicitly closed/fixed.
        
        Args:
            commit_message: The commit message to parse
            repo: The GitHub repository object
            
        Returns:
            Set of issue numbers that are explicitly closed by this commit
            
        Examples:
            - "Fixes #123" -> {123}
            - "Closes #456 and resolves #789" -> {456, 789}
            - "Fix GH-123" -> {123}
            - "Resolves owner/repo#456" -> {456} (if matches current repo)
        """
        if not commit_message:
            return set()
            
        msg = commit_message.strip()
        out: Set[int] = set()

        # Enhanced regex patterns to catch more formats
        closing_prefix = r'(?:(?<![A-Za-z])(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved|address|addresses|addressed))(?:\s*[:\-])?\s+'
        
        # Individual issue reference patterns (without named groups to avoid conflicts)
        issue_patterns = [
            r'#(\d+)',  # #123
            r'GH-(\d+)',  # GH-123
            r'issue\s*#(\d+)',  # issue #123
            r'bug\s*#(\d+)',  # bug #123
        ]
        
        # Full repository reference patterns
        full_repo_patterns = [
            r'([\w.-]+/[\w.-]+)#(\d+)',  # owner/repo#123
            r'https?://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)',  # Full URL
        ]
        
        # PR patterns (to be filtered out)
        pr_patterns = [
            r'https?://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)',  # PR URL
        ]
        
        # Compile all patterns
        all_issue_patterns = issue_patterns + full_repo_patterns
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_issue_patterns]
        compiled_pr_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in pr_patterns]
        
        # Main fix block pattern (simplified to avoid group conflicts)
        fix_block = re.compile(
            closing_prefix + r'(?:' + '|'.join(all_issue_patterns) + r')(?:\s*(?:,|\band\b|&|\bor\b|\|)\s*(?:' + '|'.join(all_issue_patterns) + r'))*', 
            re.IGNORECASE | re.MULTILINE
        )

        # Cache for API calls to avoid duplicate requests
        issue_cache = {}
        
        def is_issue(n: int) -> bool:
            """Check if the number refers to an issue (not a PR)."""
            # Check cache first
            if n in issue_cache:
                return issue_cache[n]
                
            try:
                issue = repo.get_issue(n)
                is_issue_result = getattr(issue, "pull_request", None) is None
                issue_cache[n] = is_issue_result
                return is_issue_result
            except UnknownObjectException:
                # Issue doesn't exist or is private
                issue_cache[n] = False
                return False
            except Exception as e:
                # Handle rate limiting and other API errors
                logging.warning(f"Error checking issue #{n} in {repo.full_name}: {e}")
                issue_cache[n] = False  # Assume it's an issue to be safe
                return False

        try:
            # Find all fix blocks in the commit message
            for block in fix_block.finditer(msg):
                block_text = block.group(0)
                logging.debug(f"Found fix block: '{block_text}'")
                
                # Extract issue references using individual patterns
                for pattern in compiled_patterns:
                    for match in pattern.finditer(block_text):
                        issue_number = None
                        
                        if len(match.groups()) == 1:
                            # Simple patterns like #123, GH-123, issue #123, bug #123
                            issue_number = int(match.group(1))
                        elif len(match.groups()) == 2:
                            # Full repo patterns like owner/repo#123 or full URLs
                            repo_name = match.group(1)
                            if repo_name.lower() == repo.full_name.lower():
                                issue_number = int(match.group(2))
                        
                        if issue_number is not None and issue_number > 0:
                            if is_issue(issue_number):
                                out.add(issue_number)
                
                # Check for PR references to skip them
                for pr_pattern in compiled_pr_patterns:
                    for match in pr_pattern.finditer(block_text):
                        logging.debug(f"Skipping PR reference: {match.group(0)}")
                            
        except Exception as e:
            logging.error(f"Error parsing commit message for issues: {e}")
            # Return what we found so far rather than failing completely
            return out

        return out


    def fixed_performance_issue(self, repo: Repository, commit: Commit) -> int | None:
        msg = commit.commit.message or ""

        issue_refs = self.extract_fixed_issues(msg, repo)

        if not issue_refs:
            return None

        issue_title_body_tuples = []
        for number in issue_refs:
            try:
                gh_issue = repo.get_issue(number)

                if gh_issue.pull_request is not None:
                    continue

                title = gh_issue.title or ""
                body = gh_issue.body or ""

                issue_title_body_tuples.append((number, title, body))

                p = Prompt(messages=[Prompt.Message("user",
                                    f"The following is an issue in the {repo.full_name} repository:\n\n###Issue Title###{title}\n###Issue Title End###\n\n###Issue Body###{body}\n###Issue Body End###"
                                    + f"\n\nThe following is the commit message that fixes this issue:\n\n###Commit Message###{msg}\n###Commit Message End###"
                                    + f"\n\nIs this issue likely to be related to improving execution time? Answer by only one word: 'yes' or 'no' (without any other text or punctuation). If you do not have enough information to decide, say 'no'."
                                    )], model=self.gpt5_nano.get_model())
                res = self.gpt5_nano.get_response(p)

                if "yes" in res.first_content.lower().strip():
                    logging.info(f"Commit {commit.sha} in {repo.full_name} is related to a likely performance issue prompted by GPT5_Nano (#{number}).")

                    # Also check with gpt5_codex
                    p = Prompt(messages=[Prompt.Message("user",
                                        f"The following is an issue in the {repo.full_name} repository:\n\n###Issue Title###{title}\n###Issue Title End###\n\n###Issue Body###{body}\n###Issue Body End###"
                                        + f"\n\nThe following is the commit message that fixes this issue:\n\n###Commit Message###{msg}\n###Commit Message End###"
                                        + f"\n\nIs this issue related to improving execution time? Answer by only one word: 'yes' or 'no' (without any other text or punctuation). If you do not have enough information to decide, say 'no'.")], model=self.gpt5_codex.get_model())
                    res = self.gpt5_codex.get_response(p)

                    if "yes" in res.first_content.lower().strip():
                        logging.info(f"Commit {commit.sha} in {repo.full_name} is related to a likely performance issue prompted by GPT5_Codex (#{number}).")
                        return number

            except UnknownObjectException:
                continue
                
        return None

    def is_mvnw_repo(self, repo: Repository) -> bool:
        try:
            repo.get_contents("mvnw")
            return True
        except UnknownObjectException:
            return False

    def collect_repo_perf_commits(self, repo: Repository):
        # Fetch and filter commits
        since = datetime.strptime(self.start_date, "%Y-%m-%d")
        fetched_commits = repo.get_commits(since=since)
        logging.info(f"Fetched {fetched_commits.totalCount} commits for {repo.full_name} since {since.isoformat()}")

        for commit in fetched_commits:
            if commit.sha in self.processed_commits:
                continue
            
            self.processed_commits.add(commit.sha)

            if commit.files.totalCount > self.max_commit_files:
                logging.info(f"Skipping commit {commit.sha} in {repo.full_name} due to too many files ({commit.files.totalCount}).")
                continue
            
            # Skip if the commit does not contain changes in Java source files or contains anything other than Java source files
            if not all(f.filename.endswith(".java") and not '/test/' in f.filename.lower() for f in commit.files):
                logging.info(f"Commit {commit.sha} in {repo.full_name} does not contain Java files or contains test files.")
                continue

            
            issue_number = self.fixed_performance_issue(repo, commit)
            if issue_number is None:
                logging.info(f"Commit {commit.sha} in {repo.full_name} is not fixing performance issues.")
                continue

            logging.info(f"Found performance commit: {commit.html_url} (#{issue_number})")

            self.dataset.add_or_update_commit(
                repo=repo.full_name,
                commit_hash=commit.sha,
                issue_number=issue_number,
                exec_status=None,
                exec_time_improvement=None,
                p_value=None
            )

    def collect_commits(self):
        # Iterate using segmented search to bypass 1k cap

        repos = self.iter_popular_repos_segmented()
        for repo in repos:

            logging.info(f"Processing repository {repo.full_name} with {repo.stargazers_count} stars.")

            if not self.is_mvnw_repo(repo):
                logging.info(f"Skipping repository {repo.full_name} as it is not a Maven project.")
                continue

            repo_tries = 0
            while True:
                try:
                    self.collect_repo_perf_commits(repo)
                    break # Successfully processed the repository
                except Exception as e:
                    logging.info(f"Error processing repository {repo.full_name}: {e}")
                    time.sleep(600)  # Sleep to avoid hitting rate limits
                    repo_tries += 1
                    if repo_tries >= 12: # Do not wait more than one hour for a repo
                        logging.info(f"Too many errors, stopping processing {repo.full_name}.")
                        break

    def __enter__(self):
        print("Entering context")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        print("Exiting context")
        self.close()

    def close(self):
        self.g.close()
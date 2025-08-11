import time
import re
import tiktoken

from src.llm.openai import *
from src.llm.invocation import Prompt
import src.config as conf
import src.constants as cons
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException
from github.Repository import Repository
from github.Commit import Commit
import logging
from datetime import datetime, timedelta, timezone

class CommitCollector:
    def __init__(self):
        access_token = conf.github['access-token']
        auth = Auth.Token(access_token)
        self.g = Github(auth=auth)
        self.gpt4 = GPT4_1_Nano(read_from_cache=True, save_to_cache=True)
        self.o4 = O4_Mini_High(read_from_cache=True, save_to_cache=True)

    def get_popular_repos(self):
        query = "pushed:>2025-01-01 language:Java stars:>1000 archived:false"
        repositories = self.g.search_repositories(query=query, sort="stars", order="desc")
        logging.info(f"Fetch results for {query}.")
        return repositories

    def get_diff(self, commit: Commit) -> str:
        diff = ""
        for f in commit.files:
            if f.patch:
                diff += f"--- {f.filename}\n"
                diff += f.patch + '\n'
        return diff

    def is_performance_commit(self, repo, commit: Commit) -> bool:
        # First stage, ask Gpt4.1
        p = Prompt([Prompt.Message("user",
                                  f"The following is the message of a commit in the {repo.full_name} repository:\n\n###Message Start###{commit.commit.message}\n###Message End###"
                                  + f"\n\nHow likely is it for this commit to be a performance improving commit in terms of execution time? Answer by only writing the likelihood in the following format:\nLikelihood: x%"
                                  )])
        res = self.gpt4.get_response(p)

        match = re.search(r"Likelihood:\s*([0-9]+(?:\.[0-9]+)?)%", res.first_content)
        if match:
            likelihood = float(match.group(1))
        else:
            logging.info(f"Commit {commit.sha} in {repo.full_name} did not return a valid likelihood response.")
            return False

        if likelihood < conf.perf_commit['min-likelihood']:
            logging.info(f"Commit {commit.sha} in {repo.full_name} has a likelihood of {likelihood}%, which is below the threshold.")
            return False
        if likelihood >= conf.perf_commit['max-likelihood']:
            logging.info(f"Commit {commit.sha} in {repo.full_name} has a high likelihood of being a performance commit ({likelihood}%).")
            return True

        diff = self.get_diff(commit)

        # Second stage, ask O4
        p = Prompt([Prompt.Message("user",
                                   f"The following is the message of a commit in the {repo.full_name} repository:\n\n###Message Start###{commit.commit.message}\n###Message End###"
                                   + f"\n\nThe diff of the commit is:\n\n###Diff Start###{diff}\n###Diff End###"
                                   + f"\n\nIs this commit a performance improving commit in terms of execution time? Answer with 'YES' or 'NO'."
                                   )])

        tokens_cnt = len(tiktoken.encoding_for_model("o3").encode(p.messages[0].content))

        if tokens_cnt > conf.llm['max-o4-tokens']:
            logging.info(f"Commit {commit.sha} in {repo.full_name} has too many tokens ({tokens_cnt}), skipping.")
            return False

        res = self.o4.get_response(p)

        return 'YES' in res.first_content and 'NO' not in res.first_content

    def is_maven(self, repo: Repository) -> bool:
        try:
            repo.get_contents("pom.xml")
            return True
        except UnknownObjectException:
            return False

    def get_java_performance_commits(self, repo):
        # Fetch and filter commits
        since = datetime.now(timezone.utc) - timedelta(days=240)
        perf_commits = []
        fetched_commits = repo.get_commits(since=since)
        logging.info(f"Fetched {fetched_commits.totalCount} commits for {repo.full_name} since {since.isoformat()}")

        for commit in fetched_commits:
            if commit.files.totalCount > conf.perf_commit['max-files']:
                logging.info(f"Skipping commit {commit.sha} in {repo.full_name} due to too many files ({commit.files.totalCount}).")
                continue

            message = commit.commit.message
            if not any(f.filename.endswith(".java") and not 'test' in f.filename.lower() for f in commit.files):
                logging.info(f"Commit {commit.sha} in {repo.full_name} does not contain Java files.")
                continue

            if not self.is_performance_commit(repo, commit):
                logging.info(f"Commit {commit.sha} in {repo.full_name} is not related to performance.")
                continue

            logging.info(f"Found performance commit: {commit.html_url}")
            perf_commits.append({
                "sha": commit.sha,
                "message": message,
                "url": commit.html_url
            })

        # Display matching commits
        for pc in perf_commits:
            logging.info(f"{pc['sha']} - {pc['message']}\n{pc['url']}\n")

    def get_commits(self):
        repos = self.get_popular_repos()
        # Iterate and print repository info
        for repo in repos:

            logging.info(f"Processing repository {repo.full_name} with {repo.stargazers_count} stars.")

            if not self.is_maven(repo):
                logging.info(f"Skipping repository {repo.full_name} as it is not a Maven project.")
                continue

            repo_tries = 0
            while True:
                try:
                    self.get_java_performance_commits(repo)
                    break # Successfully processed the repository
                except Exception as e:
                    logging.info(f"Error processing repository {repo.full_name}: {e}")
                    time.sleep(300)  # Sleep to avoid hitting rate limits
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
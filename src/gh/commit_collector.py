import time

from github import Github
from github import Auth
import os
import logging
from datetime import datetime, timedelta, timezone

class CommitCollector:
    def __init__(self):
        access_token = os.environ['access_token']
        auth = Auth.Token(access_token)
        self.g = Github(auth=auth)

    def get_popular_repos(self):
        query = "pushed:>2024-05-24 language:Java stars:>1000 archived:false"
        repositories = self.g.search_repositories(query=query, sort="stars", order="desc")
        logging.info(f"Fetch results for {query}.")
        return repositories

    def get_java_performance_commits(self, repo):
        pef_keywords = ["perf:", "performance"]

        # Fetch and filter commits
        since = datetime.now(timezone.utc) - timedelta(days=365)
        perf_commits = []
        fetched_commits = repo.get_commits(since=since)
        logging.info(f"Fetched {fetched_commits.totalCount} commits for {repo.full_name} since {since.isoformat()}")
        for commit in fetched_commits:
            message = commit.commit.message
            for keyword in pef_keywords:
                if keyword.lower() in message.lower():
                    if any(f.filename.endswith(".java") and not 'test' in f.filename.lower() for f in commit.files):
                        perf_commits.append({
                            "sha": commit.sha,
                            "message": message,
                            "url": commit.html_url
                        })
                        break

        # Display matching commits
        for pc in perf_commits:
            logging.info(f"{pc['sha']} - {pc['message']}\n{pc['url']}\n")

    def get_commits(self):
        repos = self.get_popular_repos()
        # Iterate and print repository info
        for repo in repos:
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
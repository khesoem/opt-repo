from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from github import Auth, Github

import src.config as conf
from src.data.dataset_adapter import DatasetAdapter

OUTPUT_DIR = Path("results/charts")
YEAR_OUTPUT_STEM = "commits_by_year_stacked"
STARS_OUTPUT_STEM = "commits_by_stars_stacked"
CACHE_PATH = OUTPUT_DIR / "github_commit_repo_cache.json"

YEAR_MIN = 2015
YEAR_MAX = 2025
SUCCESS_STATUS = "maven_execution_successful"
FONT_SIZE = 16

# Star buckets chosen to keep a readable number of bars while spanning 20..93,448.
STAR_BINS = [20, 50, 100, 250, 500, 1_000, 5_000, 20_000, 100_000]
STAR_LABELS = [
    "20-49",
    "50-99",
    "100-249",
    "250-499",
    "500-999",
    "1k-4.9k",
    "5k-19.9k",
    "20k-99.9k",
]


def load_cache(path: Path) -> dict:
    if not path.exists():
        return {"commit_year_by_repo_sha": {}, "repo_stars": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"commit_year_by_repo_sha": {}, "repo_stars": {}}


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def get_github_client() -> Github:
    token = conf.github["access-token"]
    return Github(auth=Auth.Token(token))


def ensure_commit_years_and_stars(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cache = load_cache(CACHE_PATH)
    commit_year_by_repo_sha = cache.setdefault("commit_year_by_repo_sha", {})
    repo_stars = cache.setdefault("repo_stars", {})

    github_client = get_github_client()
    repo_obj_cache = {}

    df = df.copy()
    df["repo"] = df["repo"].astype("string")
    df["after_commit"] = df["after_commit"].astype("string")

    unique_pairs = (
        df[["repo", "after_commit"]]
        .dropna()
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )

    for repo_name, sha in unique_pairs:
        repo_name = str(repo_name).strip()
        sha = str(sha).strip()
        if not repo_name or not sha:
            continue

        cache_key = f"{repo_name}@{sha}"
        if cache_key in commit_year_by_repo_sha and repo_name in repo_stars:
            continue

        repo_obj = repo_obj_cache.get(repo_name)
        if repo_obj is None:
            try:
                repo_obj = github_client.get_repo(repo_name)
                repo_obj_cache[repo_name] = repo_obj
            except Exception as err:
                print(f"Skipping repo {repo_name}: {err}")
                continue

        if repo_name not in repo_stars:
            try:
                repo_stars[repo_name] = int(repo_obj.stargazers_count)
            except Exception as err:
                print(f"Could not fetch stars for {repo_name}: {err}")

        if cache_key not in commit_year_by_repo_sha:
            try:
                commit = repo_obj.get_commit(sha=sha)
                commit_date = commit.commit.author.date or commit.commit.committer.date
                commit_year_by_repo_sha[cache_key] = int(commit_date.year)
            except Exception as err:
                print(f"Could not fetch commit date for {repo_name}@{sha}: {err}")

    save_cache(CACHE_PATH, cache)
    github_client.close()

    df["commit_year"] = df.apply(
        lambda row: commit_year_by_repo_sha.get(
            f"{str(row['repo']).strip()}@{str(row['after_commit']).strip()}"
        ),
        axis=1,
    )
    df["repo_stars"] = df["repo"].apply(lambda repo_name: repo_stars.get(str(repo_name).strip()))

    return df, cache


def build_year_summary(df: pd.DataFrame) -> pd.DataFrame:
    filtered = df[df["commit_year"].between(YEAR_MIN, YEAR_MAX, inclusive="both")].copy()
    filtered["is_successful"] = filtered["exec_status"] == SUCCESS_STATUS

    grouped = (
        filtered.groupby(["commit_year", "is_successful"]).size().unstack(fill_value=0)
    )
    years = pd.Index(range(YEAR_MIN, YEAR_MAX + 1), name="commit_year")
    grouped = grouped.reindex(years, fill_value=0)

    successful = grouped.get(True, pd.Series(0, index=years))
    not_successful = grouped.get(False, pd.Series(0, index=years))

    return pd.DataFrame(
        {
            "year": years,
            "not_successful": not_successful.values,
            "successful": successful.values,
        }
    )


def build_star_summary(df: pd.DataFrame) -> pd.DataFrame:
    filtered = df[df["repo_stars"].notna()].copy()
    filtered["repo_stars"] = filtered["repo_stars"].astype(int)
    filtered = filtered[
        filtered["repo_stars"].between(STAR_BINS[0], STAR_BINS[-1] - 1, inclusive="both")
    ]
    filtered["star_bucket"] = pd.cut(
        filtered["repo_stars"],
        bins=STAR_BINS,
        labels=STAR_LABELS,
        right=False,
        include_lowest=True,
    )
    filtered["is_successful"] = filtered["exec_status"] == SUCCESS_STATUS

    grouped = (
        filtered.groupby(["star_bucket", "is_successful"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(STAR_LABELS, fill_value=0)
    )

    successful = grouped.get(True, pd.Series(0, index=STAR_LABELS))
    not_successful = grouped.get(False, pd.Series(0, index=STAR_LABELS))

    return pd.DataFrame(
        {
            "star_bucket": STAR_LABELS,
            "not_successful": not_successful.values,
            "successful": successful.values,
        }
    )


def plot_stacked_charts(year_summary: pd.DataFrame, star_summary: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    not_success_color = "#d62728"
    success_color = "#2ca02c"

    # Chart 1: commits by commit year.
    fig_year, ax_year = plt.subplots(figsize=(11, 4.8), dpi=300)
    ax_year.bar(
        year_summary["year"],
        year_summary["not_successful"],
        color=not_success_color,
        hatch="..",
        edgecolor="white",
        linewidth=0.5,
        label=f"Non-executable ETIPs",
    )
    ax_year.bar(
        year_summary["year"],
        year_summary["successful"],
        bottom=year_summary["not_successful"],
        color=success_color,
        hatch="//",
        edgecolor="white",
        linewidth=0.7,
        label=f"Executable ETIPs",
    )
    # ax_year.set_title("Selected commits by year")
    ax_year.set_xlabel("Commit Year", fontsize=FONT_SIZE)
    ax_year.set_ylabel("Number of ETIPs", fontsize=FONT_SIZE)
    ax_year.set_xticks(list(range(YEAR_MIN, YEAR_MAX + 1)))
    ax_year.tick_params(axis="both", labelsize=FONT_SIZE)
    ax_year.grid(axis="y", linestyle="--", alpha=0.4)
    ax_year.set_axisbelow(True)
    ax_year.legend(frameon=False, fontsize=FONT_SIZE)
    fig_year.tight_layout()

    year_png_path = OUTPUT_DIR / f"{YEAR_OUTPUT_STEM}.png"
    year_pdf_path = OUTPUT_DIR / f"{YEAR_OUTPUT_STEM}.pdf"
    fig_year.savefig(year_png_path, bbox_inches="tight")
    fig_year.savefig(year_pdf_path, bbox_inches="tight")
    plt.close(fig_year)

    # Chart 2: commits by repository stars.
    fig_stars, ax_stars = plt.subplots(figsize=(11, 4.8), dpi=300)
    x_positions = list(range(len(star_summary)))
    ax_stars.bar(
        x_positions,
        star_summary["not_successful"],
        color=not_success_color,
        hatch="..",
        edgecolor="white",
        linewidth=0.5,
        label=f"Non-executable ETIPs",
    )
    ax_stars.bar(
        x_positions,
        star_summary["successful"],
        bottom=star_summary["not_successful"],
        color=success_color,
        hatch="//",
        edgecolor="white",
        linewidth=0.7,
        label=f"Executable ETIPs",
    )
    # ax_stars.set_title("Selected commits by repository stars")
    ax_stars.set_xlabel("Repository Stars", fontsize=FONT_SIZE)
    ax_stars.set_ylabel("Number of ETIPs", fontsize=FONT_SIZE)
    ax_stars.set_xticks(x_positions)
    ax_stars.set_xticklabels(
        star_summary["star_bucket"], rotation=30, ha="right", fontsize=FONT_SIZE
    )
    ax_stars.tick_params(axis="y", labelsize=FONT_SIZE)
    ax_stars.grid(axis="y", linestyle="--", alpha=0.4)
    ax_stars.set_axisbelow(True)
    ax_stars.legend(frameon=False, fontsize=FONT_SIZE)
    fig_stars.tight_layout()

    stars_png_path = OUTPUT_DIR / f"{STARS_OUTPUT_STEM}.png"
    stars_pdf_path = OUTPUT_DIR / f"{STARS_OUTPUT_STEM}.pdf"
    fig_stars.savefig(stars_png_path, bbox_inches="tight")
    fig_stars.savefig(stars_pdf_path, bbox_inches="tight")
    plt.close(fig_stars)

    print("Saved charts:")
    print(f"- {year_png_path}")
    print(f"- {year_pdf_path}")
    print(f"- {stars_png_path}")
    print(f"- {stars_pdf_path}")


def main() -> None:
    df = DatasetAdapter().get_dataset()
    enriched_df, cache = ensure_commit_years_and_stars(df)
    year_summary = build_year_summary(enriched_df)
    star_summary = build_star_summary(enriched_df)
    plot_stacked_charts(year_summary, star_summary)

    print("Year summary:")
    print(year_summary.to_string(index=False))
    print()
    print("Stars summary:")
    print(star_summary.to_string(index=False))
    print()
    print(
        "Cache stats: "
        f"{len(cache.get('commit_year_by_repo_sha', {}))} repo+sha commit years, "
        f"{len(cache.get('repo_stars', {}))} repositories with stars."
    )


if __name__ == "__main__":
    main()
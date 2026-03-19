# pyright: reportUndefinedVariable=false

from pathlib import Path

import matplotlib.pyplot as plt

from src.data.dataset_adapter import DatasetAdapter

# Repos with fewer than this many selected items are merged into "Others".
MIN_REPO_COUNT = 10
OUTPUT_DIR = Path("results/charts")
OUTPUT_STEM = "repos"
ONE_COLUMN_WIDTH_INCHES = 7


def short_repo_name(repo_name):
    """Use text after '/' for display labels (e.g., owner/repo -> repo)."""
    if repo_name is None:
        return "Unknown"
    repo_str = str(repo_name)
    if repo_str.lower() == "others":
        return "Others"
    if "/" in repo_str:
        return repo_str.split("/", 1)[1]
    return repo_str


def build_repo_summary(df, min_repo_count: int):
    """Return per-repo total and successful counts, excluding low-frequency repos."""
    per_repo = (
        df.groupby("repo", dropna=False)
        .agg(
            total_items=("repo", "size"),
            maven_execution_successful=(
                "exec_status",
                lambda s: (s == "maven_execution_successful").sum(),
            ),
        )
        .sort_values("total_items", ascending=False)
    )

    major = per_repo[per_repo["total_items"] >= min_repo_count].copy()
    major = major.sort_values("total_items", ascending=False)

    major["label"] = [short_repo_name(r) for r in major.index]
    return major


def main():
    df = DatasetAdapter().get_dataset()
    repo_summary = build_repo_summary(df, min_repo_count=MIN_REPO_COUNT)
    total_repos_all_items = df["repo"].nunique(dropna=True)
    total_repos_successful = df.loc[
        df["exec_status"] == "maven_execution_successful", "repo"
    ].nunique(dropna=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    labels = repo_summary["label"].tolist()
    total_values = repo_summary["total_items"].tolist()
    success_values = repo_summary["maven_execution_successful"].tolist()
    y_positions = list(range(len(labels)))

    fig_height = max(4.8, len(labels) * 0.34)
    fig, ax = plt.subplots(figsize=(ONE_COLUMN_WIDTH_INCHES, fig_height), dpi=300)

    offset = 0.16
    total_y = [y - offset for y in y_positions]
    success_y = [y + offset for y in y_positions]

    total_color = "#1f77b4"
    success_color = "#2ca02c"

    for y, value in zip(total_y, total_values):
        ax.hlines(y=y, xmin=0, xmax=value, color=total_color, linewidth=2.2, alpha=0.9)
    for y, value in zip(success_y, success_values):
        ax.hlines(
            y=y, xmin=0, xmax=value, color=success_color, linewidth=2.2, alpha=0.9
        )

    ax.scatter(
        total_values,
        total_y,
        color=total_color,
        s=52,
        label="Identified ETIPs",
    )
    ax.scatter(
        success_values,
        success_y,
        color=success_color,
        s=52,
        label="Executable ETIPs",
    )

    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=12, rotation=45)
    ax.invert_yaxis()
    ax.set_xlabel("Number of ETIPs", fontsize=12)
    # ax.set_title(
    #     "Identified and Executable ETIPs by Repository",
    #     fontsize=11,
    #     pad=8,
    # )
    ax.grid(axis="x", linestyle="--", linewidth=0.8, alpha=0.55)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=10, width=1.0)
    ax.legend(
        loc="lower right",
        fontsize=12,
        frameon=False,
        prop={"size": 12},
    )

    png_path = OUTPUT_DIR / f"{OUTPUT_STEM}.png"
    pdf_path = OUTPUT_DIR / f"{OUTPUT_STEM}.pdf"
    fig.tight_layout()
    fig.savefig(png_path, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)

    print("Saved lollipop charts:")
    print(f"- {png_path}")
    print(f"- {pdf_path}")
    print(f"Total repositories (all items): {total_repos_all_items}")
    print(
        "Total repositories (maven_execution_successful items): "
        f"{total_repos_successful}"
    )
    print(f"Total selected items: {sum(total_values)}")
    print(f"Total maven_execution_successful items: {sum(success_values)}")
    print("Repo summary used for plotting:")
    print(repo_summary.to_string())


if __name__ == "__main__":
    main()

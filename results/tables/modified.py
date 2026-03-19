from src.data.dataset_adapter import DatasetAdapter


def get_length_stats(df, column_name: str) -> tuple[int, int, float]:
    counts = df[column_name].apply(
        lambda value: len(value) if isinstance(value, list) else None
    )
    valid_counts = counts.dropna()

    if valid_counts.empty:
        raise ValueError(f"No valid list values found in column '{column_name}'.")

    return int(valid_counts.min()), int(valid_counts.max()), float(valid_counts.median())


def get_zero_count_after_commits(df, column_name: str) -> list[str]:
    counts = df[column_name].apply(
        lambda value: len(value) if isinstance(value, list) else None
    )
    zero_mask = counts == 0
    return df.loc[zero_mask, "after_commit"].dropna().astype(str).tolist()


def print_stats_for_df(df, section_title: str) -> None:
    print(section_title)
    for column_name in ("modified_modules", "changed_files"):
        min_count, max_count, median_count = get_length_stats(df, column_name)
        zero_after_commits = get_zero_count_after_commits(df, column_name)
        print(f"{column_name}:")
        print(f"  min: {min_count}")
        print(f"  max: {max_count}")
        print(f"  median: {median_count}")
        print("  after_commit with zero count:")
        if zero_after_commits:
            for after_commit in zero_after_commits:
                print(f"    - {after_commit}")
        else:
            print("    - none")
    print()


def main():
    df = DatasetAdapter().get_dataset()
    successful_df = df[df["exec_status"] == "maven_execution_successful"]

    print_stats_for_df(df, "All rows:")
    print_stats_for_df(successful_df, "Rows with exec_status='maven_execution_successful':")


if __name__ == "__main__":
    main()
from src.gh.commit_collector import CommitCollector
import logging
from datetime import datetime
import argparse

logging.basicConfig(filename='logs/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run static analysis, dynamic analysis, or evaluation harness."
    )
    parser.add_argument(
        "--analysis-type",
        choices=["static", "dynamic", "evaluation-harness"],
        default="static",
        help=(
            "Choose analysis type: static (commit collector), "
            "dynamic (run analysis pipeline), or evaluation-harness."
        ),
    )

    parser.add_argument(
        "--evaluation-type",
        choices=["patch", "test"],
        help="When using evaluation-harness, choose patch or test evaluation.",
    )
    parser.add_argument("--repo", help="Repository identifier, e.g., owner/repo.")
    parser.add_argument("--after-commit", help="Commit hash to evaluate against.")
    parser.add_argument(
        "--output-analysis-path",
        help="Output path for evaluation result JSON.",
    )
    parser.add_argument(
        "--modified-modules",
        help="Comma-separated modified Maven modules, e.g., module-a,module-b.",
    )

    parser.add_argument("--patch-path", help="Path to patch file for patch evaluation.")
    parser.add_argument(
        "--test-patch-path",
        help="Path to test patch file for test evaluation.",
    )
    parser.add_argument(
        "--tests",
        help="Comma-separated test names for test evaluation.",
    )

    parser.add_argument(
        "--exec-times",
        type=int,
        default=None,
        help="Optional number of evaluation executions.",
    )
    parser.add_argument(
        "--min-p-value",
        type=float,
        default=None,
        help="Optional minimum p-value threshold.",
    )
    parser.add_argument(
        "--min-exec-time-improvement",
        type=float,
        default=None,
        help="Optional minimum execution-time improvement threshold.",
    )
    parser.add_argument(
        "--working-dir",
        default=None,
        help="Optional working directory override.",
    )

    return parser.parse_args()


def _parse_csv_list(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _require_args(args: argparse.Namespace, fields: list[str]) -> None:
    missing = [field for field in fields if getattr(args, field) in (None, "")]
    if missing:
        raise ValueError(f"Missing required argument(s): {', '.join(missing)}")


def main() -> None:
    args = parse_args()

    if args.analysis_type == "static":
        logging.info("Starting static analysis (Commit Collector)")
        with CommitCollector() as collector:
            collector.collect_commits()
    elif args.analysis_type == "dynamic":
        logging.info("Starting dynamic analysis (run_analysis)")
        from src.run_analysis import run as run_dynamic_analysis
        run_dynamic_analysis()
    else:
        logging.info("Starting evaluation harness")
        from src.evaluation.evaluators import PatchEvaluator, TestEvaluator
        _require_args(
            args,
            ["evaluation_type", "repo", "after_commit", "output_analysis_path", "modified_modules"],
        )
        modified_modules = _parse_csv_list(args.modified_modules)
        if not modified_modules:
            raise ValueError("modified-modules must contain at least one module.")

        if args.evaluation_type == "patch":
            _require_args(args, ["patch_path"])
            evaluator = PatchEvaluator(
                repo=args.repo,
                after_commit=args.after_commit,
                patch_path=args.patch_path,
                output_analysis_path=args.output_analysis_path,
                modified_modules=modified_modules,
                exec_times=args.exec_times,
                min_p_value=args.min_p_value,
                min_exec_time_improvement=args.min_exec_time_improvement,
                working_dir=args.working_dir,
            )
        else:
            _require_args(args, ["test_patch_path", "tests"])
            tests = _parse_csv_list(args.tests)
            if not tests:
                raise ValueError("tests must contain at least one test name.")
            evaluator = TestEvaluator(
                repo=args.repo,
                after_commit=args.after_commit,
                output_analysis_path=args.output_analysis_path,
                modified_modules=modified_modules,
                test_patch_path=args.test_patch_path,
                tests=tests,
                exec_times=args.exec_times,
                min_p_value=args.min_p_value,
                min_exec_time_improvement=args.min_exec_time_improvement,
                working_dir=args.working_dir,
            )

        evaluator.evaluate()

if __name__ == '__main__':
    main()
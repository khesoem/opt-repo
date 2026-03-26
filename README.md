# JETO-Bench Replication Package

This repository is the replication package for the paper **"JETO-Bench: A Reproducible Benchmark for Execution Time Improving Patches in Java"**.

It includes:
- data collection and filtering for executable ETIPs,
- dynamic analysis pipelines,
- evaluation harnesses for patch and test evaluation,
- scripts and data to reproduce reported tables and charts.

## Requirements

- Linux environment
- Python 3.11+
- [Poetry](https://python-poetry.org/)
- Docker (required for dynamic analysis and evaluation harness)

## Installation

From the project root:

```bash
poetry install
```

If you are running commands without `poetry run`, make sure dependencies are installed in your active environment.

## Environment Variables

Set the environment variables used by the code:

```bash
export workingdir="$(pwd)"
export github_access_token="<YOUR_GITHUB_TOKEN>"
export OPENROUTER_API_KEY="<YOUR_OPENROUTER_KEY>"
export OPENAI_API_KEY="<YOUR_OPENAI_KEY>"
```

Notes:
- `workingdir` is used by dynamic analysis and evaluation workflows.
- `github_access_token` is needed for GitHub API access.
- `OPENROUTER_API_KEY` / `OPENAI_API_KEY` are used by configured LLM-related components.

## Configuration and Filters

User-defined filters and analysis configuration for static and dynamic workflows can be set in:
- `src/config.py`

## Running the Main Entry Point

The main entry point is `main.py` and supports three modes via `--analysis-type`.

### 1) Static Analysis

Runs the commit collection pipeline (`CommitCollector`), which is the default mode.

```bash
poetry run python main.py
```

or explicitly:

```bash
poetry run python main.py --analysis-type static
```

### 2) Dynamic Analysis

Runs the dynamic analysis pipeline from `src/run_analysis.py`.

```bash
poetry run python main.py --analysis-type dynamic
```

### 3) Evaluation Harness

Runs evaluation via `src/evaluation/evaluators.py` and supports:
- `patch` evaluation (`PatchEvaluator`)
- `test` evaluation (`TestEvaluator`)

#### Patch Evaluation

Required arguments:
- `--evaluation-type patch`
- `--repo`
- `--after-commit`
- `--output-analysis-path`
- `--modified-modules` (comma-separated)
- `--patch-path`

Example:

```bash
poetry run python main.py \
  --analysis-type evaluation-harness \
  --evaluation-type patch \
  --repo owner/repo \
  --after-commit abc123 \
  --output-analysis-path results/eval_patch.json \
  --modified-modules module-a,module-b \
  --patch-path /path/to/fix.patch
```

#### Test Evaluation

Required arguments:
- `--evaluation-type test`
- `--repo`
- `--after-commit`
- `--output-analysis-path`
- `--modified-modules` (comma-separated)
- `--test-patch-path`
- `--tests` (comma-separated)

Example:

```bash
poetry run python main.py \
  --analysis-type evaluation-harness \
  --evaluation-type test \
  --repo owner/repo \
  --after-commit abc123 \
  --output-analysis-path results/eval_test.json \
  --modified-modules module-a,module-b \
  --test-patch-path /path/to/test.patch \
  --tests com.example.FooTest,com.example.BarTest
```

Optional evaluation arguments:
- `--exec-times`
- `--min-p-value`
- `--min-exec-time-improvement`
- `--working-dir`

## Dataset and Reproducibility Artifacts

- The list of identified and manually verified executable ETIPs is in:
  - `results/dataset.csv`
- Tables and charts can be checked and reproduced using data and scripts in:
  - `results/`

Useful scripts include:
- `results/charts/stars_year.py`
- `results/charts/repos.py`
- `results/charts/executable_etips_stats.py`
- `results/tables/modified.py`

## Logs and Outputs

- Runtime logs are written to `logs/`.
- Several workflows write analysis outputs to paths provided via CLI arguments.

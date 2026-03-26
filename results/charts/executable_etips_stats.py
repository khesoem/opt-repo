from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from github import Auth, Github

import src.config as conf
from src.data.dataset_adapter import DatasetAdapter


def print_five_number_summary(name: str, values: list[float]) -> None:
    if not values:
        print(f"{name}: (no data)")
        return
    s = pd.Series(values)
    q1, med, q3 = s.quantile([0.25, 0.5, 0.75])
    print(
        f"{name}: min={s.min():g}, max={s.max():g}, "
        f"Q1={q1:g}, median={med:g}, Q3={q3:g}"
    )


logs = ['logs/logging_2026-01-08-22-31.log', 'logs/logging_2026-01-10-21-51.log', 'logs/logging_2026-01-16-13-55.log']

found_commits = set()
all_checked_commits = set()
commit_to_time = {}
durations = []
for l in logs:
    with open(l, 'r') as f:
        is_new_day = False
        days = 0
        for line in f:
            line = line.strip()
            commit = line.split(' ')[5]
            if not commit in commit_to_time:
                time = line.split(' ')[0]
                commit_to_time[commit] = {'start': time}
            if 'Analysis Result' in line:
                if not 'end' in commit_to_time[commit]:
                    commit_to_time[commit]['end'] = line.split(' ')[0]

for commit, times in commit_to_time.items():
    if 'end' in times:
        start = times['start']
        end = times['end']
        # start and end have the format: 13:55:19,384
        start_time = datetime.strptime(start, '%H:%M:%S,%f')
        end_time = datetime.strptime(end, '%H:%M:%S,%f')
        duration = (end_time - start_time).total_seconds()
        if duration < 0:
            print("negative")
            duration += 3600 * 24
        if duration > 10000:
            continue
        durations.append(duration)
print(durations)
print_five_number_summary('Commit analysis durations (s)', durations)


def ghcr_image_sizes_bytes() -> list[int]:
    """Sizes in bytes for local Docker images whose repository name starts with 'ghcr'."""
    result = subprocess.run(
        ['docker', 'images', '--format', '{{.Repository}}\t{{.ID}}'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"docker images failed: {result.stderr.strip() or result.stdout}"
        )
    sizes: list[int] = []
    seen_ids: set[str] = set()
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split('\t', 1)
        if len(parts) != 2:
            continue
        repo, image_id = parts
        if not repo.startswith('ghcr'):
            continue
        if image_id in seen_ids:
            continue
        seen_ids.add(image_id)
        r = subprocess.run(
            ['docker', 'inspect', '--format', '{{.Size}}', image_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode != 0:
            continue
        sizes.append(int(r.stdout.strip()))
    return sizes


sizes_bytes = ghcr_image_sizes_bytes()
sizes_mib = [s / (1024 * 1024) for s in sizes_bytes]
print(f"GHCR image sizes (MiB): {sizes_mib}")
print_five_number_summary('GHCR image sizes (MiB)', sizes_mib)

fig, (ax_dur, ax_sz) = plt.subplots(2, 1, figsize=(10, 8), constrained_layout=True)

if durations:
    bp_d = ax_dur.boxplot([durations], vert=False, patch_artist=True, widths=0.45)
    bp_d['boxes'][0].set_facecolor('steelblue')
    bp_d['boxes'][0].set_edgecolor('black')
    bp_d['medians'][0].set_color('black')
ax_dur.set_xlabel('Duration (s)')
ax_dur.set_yticks([1])
ax_dur.set_yticklabels([''])
ax_dur.set_title('Commit Static Analysis Duration')

if sizes_mib:
    bp_s = ax_sz.boxplot([sizes_mib], vert=False, patch_artist=True, widths=0.45)
    bp_s['boxes'][0].set_facecolor('coral')
    bp_s['boxes'][0].set_edgecolor('black')
    bp_s['medians'][0].set_color('black')
ax_sz.set_xlabel('Size (MiB)')
ax_sz.set_yticks([1])
ax_sz.set_yticklabels([''])
ax_sz.set_title('Docker Image Size')

charts_dir = Path('results/charts')
charts_dir.mkdir(parents=True, exist_ok=True)
base = charts_dir / 'durations_and_ghcr_image_sizes'
out_pdf = base.with_suffix('.pdf')
out_png = base.with_suffix('.png')
fig.savefig(out_pdf, format='pdf', bbox_inches='tight')
fig.savefig(out_png, format='png', dpi=200, bbox_inches='tight')
plt.close(fig)
print(f"Saved plot to {out_pdf.resolve()}")
print(f"Saved plot to {out_png.resolve()}")

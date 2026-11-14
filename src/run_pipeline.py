#!/usr/bin/env python3
"""Generate submission.json with the staged pipeline.

python src/run_pipeline.py --data data --output outputs/submission.json \
    --github-handle YOUR_GITHUB_USERNAME \
    --repo-url https://github.com/YOUR_GITHUB_USERNAME/YOUR_SOLUTION_REPO

Submissions are public: never add your email address or student ID.
"""
import argparse
import json
from pathlib import Path

from straightrows.config import Config
from straightrows.io import load
from straightrows.pipeline import run


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data")
    p.add_argument("--output", default="outputs/submission.json")
    p.add_argument("--github-handle", required=True)
    p.add_argument("--repo-url", required=True)
    p.add_argument("--display-name", default=None)
    a = p.parse_args()
    sub = run(load(a.data), a.github_handle, a.repo_url, Config(), display_name=a.display_name)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)  # same path, created if missing
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(sub, f, indent=2)
    print(f"Wrote {len(sub['detections'])} detections to {a.output}")


if __name__ == "__main__":
    main()

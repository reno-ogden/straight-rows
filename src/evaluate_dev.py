#!/usr/bin/env python3
"""Compare the baseline and pipeline variants on the labeled development window.

python src/evaluate_dev.py --data data [--sweep]

1. Equivalence check: pipeline with STARTER config must reproduce src/baseline.py
   (same intervals, tractors, classes) on both the dev and eval windows.
2. Scores each variant against data/labels/train_episodes.json with the official
   scorer (tools/score_submission.py). Development labels only.
"""
import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
import baseline  # noqa: E402
import score_submission  # noqa: E402
from straightrows.config import DEV, EVAL, STARTER, Config  # noqa: E402
from straightrows.io import load  # noqa: E402
from straightrows.pipeline import detect  # noqa: E402


def baseline_dets(data, window):
    baseline.EVAL_START, baseline.EVAL_END = window
    out = baseline.detect(data)
    return [{"cause": x["class"], "start": pd.Timestamp(x["start"]), "end": pd.Timestamp(x["end"]),
             "tractors": sorted(x["tractors"])} for x in out]


def key(dets):
    return sorted((x["cause"], x["start"], x["end"], tuple(sorted(x["tractors"]))) for x in dets)


def score(dets, labels):
    sub = {"detections": [{"start": x["start"].isoformat(), "end": x["end"].isoformat(),
                           "tractors": x["tractors"], "class": x["cause"],
                           "action": score_submission_action(x["cause"])} for x in dets]}
    lab = {"episodes": [{**r, "start": r["start"].isoformat(), "end": r["end"].isoformat()}
                        for r in labels.to_dict("records")]}
    return score_submission.score(sub, lab)


def score_submission_action(cause):
    from straightrows.config import ACTION
    return ACTION[cause]


def row(name, r):
    m = r["class_metrics"]
    return (f"{name:34} {r['diagnostic_score']:6.2f} {r['macro_f1']:6.3f} {r['mean_timing_credit']:6.3f} "
            f"{sum(e['correct'] for e in r['episodes']):3d}/12 {len(r['false_positives']):3d}   "
            + " ".join(f"{m[c]['f1']:.2f}" for c in ["SPACE_WEATHER", "JAMMING", "SPOOFING", "EQUIPMENT_FAULT", "MULTIPATH"]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="data")
    p.add_argument("--sweep", action="store_true", help="also sweep bridge_gap_s")
    a = p.parse_args()
    d = load(a.data)
    labels = d["labels"]

    for name, w in (("dev", DEV), ("eval", EVAL)):
        same = key(baseline_dets(a.data, w)) == key(detect(d, STARTER, w))
        print(f"equivalence STARTER vs src/baseline.py on {name} window: {'IDENTICAL' if same else 'DIFFERENT'}")
        if not same:
            sys.exit(1)

    variants = {
        "baseline (src/baseline.py)": None,
        "pipeline STARTER (single-label)": STARTER,
        "pipeline multi-label, no bridge": Config(bridge_gap_s=0.0),
        "pipeline default (multi + bridge)": Config(),
    }
    if a.sweep:
        for g in (60, 120, 180, 240, 300, 360):
            variants[f"multi-label + bridge {g}s"] = Config(bridge_gap_s=g)
    print(f"\n{'variant':34} {'diag':>6} {'mF1':>6} {'onset':>6} {'hit':>6} {'FP':>3}   SW   JAM  SPF  EF   MP")
    results = {}
    for name, cfg in variants.items():
        dets = baseline_dets(a.data, DEV) if cfg is None else detect(d, cfg, DEV)
        results[name] = (dets, score(dets, labels))
        print(row(name, results[name][1]))
    return results


if __name__ == "__main__":
    main()

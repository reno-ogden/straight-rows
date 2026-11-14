# Detection pipeline

## Commands

```bash
python src/run_pipeline.py --data data --output outputs/submission.json --github-handle reno-ogden --repo-url https://github.com/reno-ogden/straight-rows
python src/validate_submission.py outputs/submission.json
python src/evaluate_dev.py --sweep      # dev-window comparison + parameter sweep
python -m pytest -q tests
```

## Stages (`src/straightrows/`)

| Stage | Module | Does |
|---|---|---|
| Load | `io.py` | Raw files read-only; all timestamps timezone-aware UTC (ISO-8601, mixed precision). |
| Features | `features.py` | Per tractor-minute: mean C/N0, min C/N0, mean XTE, mean speed, link-up fraction; Kp and S4 in force (backward as-of). |
| Candidates | `candidates.py` | Cause-agnostic flags: `cn0_low`, `xte_high`, `link_low`, `dropout`, `working`, fleet count `n_cn0_low`. |
| Attribution | `attribution.py` | One independent test per cause → zero or more causes per tractor-minute. |
| Assembly | `assembly.py` | Minute runs → bridge short gaps → minimum-duration filter → merge same cause across tractors. Different causes never merge. |
| Evidence | `evidence.py` | Strings computed from the 1 Hz telemetry and SDA feeds over each interval. |
| Export | `export.py` | Template-shaped `submission.json`. |

`Config` in `config.py` holds every parameter. The `STARTER` config reproduces `src/baseline.py`.
That file is **not** the untouched official starter: it is the official `starter/submission/baseline.py`
modified in commit `b40c92e` to use regional S4 instead of Kp (`kp >= 5`) to separate space weather from
jamming. "STARTER" therefore means "our baseline before the pipeline changes", not "the official starter".
`evaluate_dev.py` and `tests/test_pipeline.py` check that equivalence on both windows.

## The change, and why

**Interval assembly bridges same-tractor, same-cause gaps of at most 180 s before applying the
180 s minimum-duration filter** (the starter filters first, then merges).

Dev evidence: TRN-10 (T1 correction-link fault, 05-05 02:00–02:48) shows up minute-by-minute as
runs of 1–2 flagged minutes separated by 2–3 unflagged minutes (the link flickers; see
`outputs/dev_plots/TRN-10_EQUIPMENT_FAULT.png`). Every run is shorter than 180 s, so the
starter discards all of them. Bridging joins them into one 02:00–02:48 interval.

Parameter choice: 180 s covers every same-cause gap observed in dev (largest is 3 missing
minutes) and matches the existing minimum duration. Sweep on dev (`--sweep`): 60 s gives no gain;
every value from 120 s to 360 s gives the same 25.04, so the result is not tuned to a knife-edge.

**Multi-label attribution** is required by "keep distinct concurrent causes": the starter's
if-chain allows one cause per tractor-minute, so TRN-06 (spoofing, T2) cut TRN-09 (equipment fault, T2)
in two and left a 5-minute fault fragment as a false positive. Thresholds are unchanged.

## Development-window results (official scorer, 12 labeled episodes)

| Variant | Diagnostic /40 | Macro-F1 | Onset | Hits | FP | EF F1 |
|---|---:|---:|---:|---:|---:|---:|
| `src/baseline.py` (S4-modified starter) | 21.29 | 0.553 | 0.497 | 7/12 | 3 | 0.50 |
| Pipeline, `STARTER` | 21.29 | 0.553 | 0.497 | 7/12 | 3 | 0.50 |
| + multi-label | 22.12 | 0.587 | 0.497 | 7/12 | 2 | 0.67 |
| + bridge 180 s (default) | **25.04** | **0.653** | **0.580** | **8/12** | **2** | **1.00** |

Per episode: TRN-10 is now detected (onset +0 min, time IoU 1.00), and TRN-09's IoU goes from 0.64 to 1.00.
Nothing regressed.

Caveat: parameters were chosen and scored on the same 12 episodes (no held-out split), so this is
an in-sample comparison. The flat 120–360 s plateau is the main argument that it generalises.

## Development history: what was looked at

- Labels were used only from the development window (`data/labels/train_episodes.json`). The
  pipeline code never reads labels; only `evaluate_dev.py` and the tests do.
- **Unlabeled evaluation-window feeds were inspected during development.** When the S4 change
  (commit `b40c92e`) was proposed, the justification was the development-window pattern: Kp drops to
  3.0 at 15:00 and 21:00 on May 5 while S4 stays at 0.44–0.80 until the labeled storm episodes end.
  The proposal also pointed out the same Kp/S4 pattern on the evaluation day (Kp 6.8 → 3.0 at 15:00)
  and that the S4-modified baseline changed the evaluation output (the 15:00–16:00 jamming detection
  merged into the storm detection). The 0.2 S4 cutoff and the 180 s bridge were chosen and scored on
  development data only. Evaluation-window outputs were compared only as counts of changed
  detections, never against any truth. No evaluation labels exist in this repository or were used.
- The 0.2 S4 cutoff was chosen by hand: below the 0.418 minimum seen inside labeled storm episodes and
  above the ~0.02–0.08 levels inside quiet labeled episodes. Development S4 also takes values of
  0.27–0.33, and up to 0.71 outside storm labels, so the split is not clean. Its sensitivity has not been tested.

## Evaluation-window output (no labels; counts only)

7 detections, validator `OK`. Compared with `src/baseline.py`: the T1 equipment fault ends at 02:00
instead of 01:57, and there is a new T2 equipment fault from 19:48 to 20:28 made of bridged fragments.
These are not known to be correct.

## Still missing (dev)

- TRN-05: jamming inside a storm (absolute C/N0 rule plus S4 cannot separate it).
- TRN-08: spoofing inside a storm.
- TRN-11/12: multipath (no detector yet).
- False positives: 05-05 07:00 space weather while parked; 05-05 22:00 spoofing fragment.
- TRN-01 onset is 75 min early (parked degradation before work starts).
- Confidence is a constant 0.5 (not calibrated).

## Checks actually run

Verification run, 2026-11-14 at `99acac6`, `.venv\Scripts\python.exe` (Python 3.11.0):

- `python -m pytest -v tests`: 3 passed, 0 failed, 0 skipped.
- `python src/evaluate_dev.py --data data --sweep`: equivalence IDENTICAL on both windows; numbers as in the table above.
- `python src/run_pipeline.py … --output outputs/submission.json`: 7 detections; byte-identical to the previous file.
- `python src/validate_submission.py outputs/submission.json`: `OK: 7 detection(s)`. The validator from the
  official repository at `4b9c010` gave the same result, and the official pull-request check's offline privacy
  function reported no findings.
- `tools/score_submission.py` was confirmed identical to the official scorer apart from the two added comment lines.

Reproducibility milestone run, 2026-11-14, after adding output-folder creation, `scripts/get_data.py`,
`DATASET_SHA256` and the README (detection code unchanged from `99acac6`):

- `python -m pytest -v tests`: 3 passed.
- `python src/run_pipeline.py … --output outputs/verify-repro-20261114T070508Z/run/submission.json`
  (folder did not exist beforehand): created the folder; 7 detections; validator `OK`; byte-identical to the
  preserved pre-change output.
- `python src/dev_episode_stats.py … --out outputs/verify-repro-20261114T070508Z/stats/dev_episode_stats.csv`:
  created the folder; byte-identical to the existing CSV.
- `python scripts/get_data.py --zip <release zip>`, run in a temporary copy (not over `data/`): checksum accepted,
  6 files extracted, all byte-identical to `data/`. A non-matching file was refused with "Checksum mismatch".
- `data/`: all six files unchanged (SHA-256 compared before and after).

The full official pull-request check (needs the GitHub API and a pull request), a fresh-clone
reproduction, and a clean `pip install -r requirements.txt` have not been run.

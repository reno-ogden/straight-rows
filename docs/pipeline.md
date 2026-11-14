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

`Config` in `config.py` holds every parameter; `STARTER` reproduces `src/baseline.py`.
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
| `src/baseline.py` (S4) | 21.29 | 0.553 | 0.497 | 7/12 | 3 | 0.50 |
| Pipeline, `STARTER` | 21.29 | 0.553 | 0.497 | 7/12 | 3 | 0.50 |
| + multi-label | 22.12 | 0.587 | 0.497 | 7/12 | 2 | 0.67 |
| + bridge 180 s (default) | **25.04** | **0.653** | **0.580** | **8/12** | **2** | **1.00** |

Per episode: TRN-10 is now detected (onset +0 min, time IoU 1.00), and TRN-09's IoU goes from 0.64 to 1.00.
Nothing regressed.

Caveat: parameters were chosen and scored on the same 12 episodes (no held-out split), so this is
an in-sample comparison. The flat 120–360 s plateau is the main argument that it generalises.

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

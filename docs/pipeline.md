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
| Multipath (opt-in) | `multipath.py` | Separate 1 Hz path, off by default (`Config.detect_multipath`): short per-tractor min-C/N0 dips → one detection per tractor per dip, outside minute assembly. |
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

## Working-state gate

**Definition (unchanged, inherited from the starter):** `working = (1-minute mean of speed_mps) > moving_mps`,
`moving_mps = 1.0` (`candidates.py`). In this dataset `speed_mps` takes only the values 0 and 4.5, so a minute
is working when **at least 14 of its 60 samples are moving** (4.5 × 14/60 > 1.0). Observed: every minute in
the data is either fully parked or fully moving; tractors change state exactly at 03:00Z (park) and
11:00Z (start work).

**Change:** `SPACE_WEATHER`, `JAMMING` and `EQUIPMENT_FAULT` now also require `working`, as `SPOOFING` already
did through `xte_high` (`attribution.py`, switch `Config.require_working`, default `True`). Reason: the official
guide says scored episodes concern working tractors and "poor reception while parked alone is not a scored
guidance event". No new threshold was introduced. `STARTER` keeps `require_working=False`, so it still
reproduces `src/baseline.py` exactly.

**Bridging across stops:** gaps are only bridged up to 180 s (same tractor, same cause). Parked minutes never
start an incident or extend it beyond working minutes. A stop of at most 180 s between two working parts of the
same incident is joined, so the interval contains that brief stop (pinned by
`test_short_stop_inside_one_working_episode_is_bridged`). Longer stops, including the nightly 8-hour park,
are not bridged. This was judged consistent with the intent and left unchanged.

**Synthetic tests** (`tests/test_working_state.py`, 12 tests, no dataset needed): parked-only regional loss,
loss and link fault create nothing; the same symptoms while working are detected; a parked-then-working
transition starts at the first working minute (also when work starts mid-minute); working-then-parked ends at
the last working minute; long stops are not bridged; short stops are; the `STARTER` config still flags
parked loss. With the gate switched off, the three parked-only scenarios each produce a detection and the
transition case starts 20 minutes early, so the tests do discriminate.

## Development-window results (official scorer, 12 labeled episodes)

| Variant | Diagnostic /40 | Macro-F1 | Onset | Hits | FP | EF F1 |
|---|---:|---:|---:|---:|---:|---:|
| `src/baseline.py` (S4-modified starter) | 21.29 | 0.553 | 0.497 | 7/12 | 3 | 0.50 |
| Pipeline, `STARTER` | 21.29 | 0.553 | 0.497 | 7/12 | 3 | 0.50 |
| + multi-label | 22.12 | 0.587 | 0.497 | 7/12 | 2 | 0.67 |
| + bridge 180 s | 25.04 | 0.653 | 0.580 | 8/12 | 2 | 1.00 |
| + working gate (default) | **27.29** | **0.693** | **0.664** | **8/12** | **1** | **1.00** |

Per episode: the bridge recovered TRN-10 (onset +0 min, time IoU 1.00) and raised TRN-09's IoU from 0.64 to 1.00.
The working gate changed exactly two detections, both space weather on all three tractors on 05-05:
the 07:00–07:15 false positive (tractors 100% parked) is gone; the 09:45–16:00 detection now starts at 11:00
(the moment work starts), so TRN-01 goes from onset −75 min / time IoU 0.80 to onset +0 min / 1.00.
Space-weather F1 0.80 → 1.00. The other 8 detections, all other episodes and the tractor
memberships are unchanged. With the gate, the score is flat for bridge 120–360 s; 60 s loses TRN-10 again.
A higher score is consistent with the fix but does not prove it; the synthetic tests are the direct check.

**Evaluation window:** the gate changes none of the 7 evaluation-window detections (all were already on
working tractors). This was counted after the change, not used to choose it.

Caveat: parameters were chosen and scored on the same 12 episodes (no held-out split), so this is
an in-sample comparison. The flat 120–360 s plateau shows local insensitivity on those examples;
it does not establish performance on new episodes.

## Input validation review — 2026-11-14 (after the final detection design)

`io.load` now rejects missing or null required telemetry fields, duplicate `(tractor_id, ts)` records,
unexpected tractor IDs, and empty, missing-column, null, or duplicate-timestamp Kp/Dst/S4 series. Conflicting duplicate rows can
silently change a minute mean and suppress a detection, so rejecting them protects the rule's meaning.
Empty optional RFI and advisory lists load as empty timestamped tables. `Config` rejects non-finite or
out-of-range thresholds and duration settings. Missing timestamps remain allowed; the existing minute and
gap-bridging rules apply. The released dataset has no duplicate tractor-seconds or null telemetry fields.

Eight focused synthetic checks cover these cases. With the released data, the 41-test suite passes and a
regenerated evaluation submission is byte-identical to the preserved `outputs/submission.json`; the
development and evaluation detections are unchanged. These checks improve malformed-input behavior, not
the in-sample score or unknown evaluation accuracy.

## Evidence accuracy review — 2026-11-14

Evidence text only (`evidence.py`, plus two dashboard methodology/caption sentences); detection boundaries,
causes, actions, tractor sets and confidence are unchanged (verified on the regenerated evaluation output).
Corrections:

- Interval and RFI times now carry the date and `Z` (e.g. `2026-05-06 01:00-02:00Z`); concurrency spans too.
- "Unaffected T2,T3" → "not in this detection": tractors outside a detection can still be degraded below the
  rule threshold (evaluation #5: T2 mean C/N0 39.3 vs 45.0 prior).
- Cross-track error is named as the guidance-monitor channel, not derived from reported position.
- S4/Kp/Dst line states that SDA timestamp meaning (interval start or end) is undocumented.
- Jamming: "so scintillation does not explain the signal loss" → regional scintillation was low, so the rule
  does not attribute the loss to space weather; the rule does not use RFI reports.
- RFI: "at" → "timestamped", distance is from the tractors' mean *reported* position, observation-vs-report
  time is undocumented, rules do not use RFI. "No RFI report…" now adds that absence of a report does not show
  that no interference occurred.
- New line per detection: minutes in which the cause's per-minute rule (`attribution.tests`) held on each
  listed tractor, with the bridging (≤ 180 s) and cross-tractor merge (≤ 300 s) notes when they apply. This
  exposes, for example, that the evaluation T2 equipment fault held its rule in 19 of 40 minutes and the
  18:30 jamming detection on T1 in 24 of 30.
- Dashboard methodology and scoring caption: analysis is retrospective; onset credit is not real-time latency.

Checked and left as is: equipment-fault evidence names the observed symptom (antenna dropouts vs link loss)
with the same test the dashboard uses; confidence is described as fixed/uncalibrated wherever shown;
development metrics are labelled in-sample; reported position is never called ground truth; dashboard
rule-minute counts equal the exported counts for all 16 detections (both windows).

Known limitation (not changed, detector-adjacent): the equipment-fault evidence names the link when the
affected tractor's link-up share is *any* amount below the others', so a marginal difference could be named
alongside a dropout. Current outputs are not affected.

## Suspected multipath (opt-in, `Config.detect_multipath`, default off) — 2026-11-14

Decision: kept as an opt-in analysis option; the submission uses the default pipeline (multipath off).

**Rule** (`multipath.py`, per tractor, raw 1 Hz): min C/N0 at least `mp_drop_db` = 6 dB below its centred
`mp_window_s` = 121 s running median, mean C/N0 within `mp_mean_tol_db` = 2 dB of its own running median, and
the tractor working in that minute (the pipeline's 1-min mean speed > 1.0 m/s). Qualifying seconds at most
`mp_join_s` = 4 s apart are joined (brief recoveries, missing samples); runs of `mp_min_s` = 8 to `mp_max_s` =
60 s are reported. No interpolation; seconds without a running median (too little surrounding data) never
qualify. A centred 121 s median is itself pulled down by lows longer than about 60 s, so the 60 s limit is a
backstop (tested separately with a wider window).

**Why these values.** Development data only: the two labeled examples (TRN-11 T3, TRN-12 T1, 17 s each) are a
7–10 dB drop of min C/N0 with unchanged mean C/N0, satellites, RTK link and cross-track error. A dev-window
census (exploratory threshold 5 dB / 121 s) found ~160 such dips per working tractor per day, 12–17 s long,
recurring every ~351 s at one reported-latitude band and co-timed on all three tractors in most cases.
No labeled timestamps, latitudes, expected counts or evaluation-window patterns are used.

**Representation.** One detection per tractor per dip with 1 Hz boundaries. These runs bypass minute
assembly: the 180 s minimum duration would discard them, minute boundaries cap time IoU with a 17 s label at
0.28 (the scorer needs 0.30), and the cross-tractor merge would create three-tractor detections that cannot
match a single-tractor label (tractor IoU 1/3). Multipath never suppresses or alters other causes; concurrency
lists in existing detections' evidence ignore multipath reports, so those detections stay byte-identical.

**Development results (in-sample; official scorer).** Default vs default + multipath:

| | Diagnostic /40 | Macro-F1 | Onset | Hits | FP | MP P / R / F1 |
|---|---:|---:|---:|---:|---:|---|
| Default (multipath off) | 27.29 | 0.693 | 0.664 | 8/12 | 1 | 0 / 0 / 0 |
| + multipath | 34.79 | 0.893 | 0.830 | 10/12 | 1 | 1.00 / 1.00 / 1.00 |

Other classes unchanged (SW 1.00, JAM 0.80, SPF 0.67, EF 1.00 — P and R identical); the 9 non-multipath
detections and their evidence are byte-identical; misses TRN-05 and TRN-08 unchanged; the one FP (SPF T3
05-05 22:00) unchanged. TRN-11 matched by T3 14:04:18–14:04:33 (IoU 0.88, onset +0 s); TRN-12 by T1
19:00:35–19:00:52 (IoU 1.00, onset +0 s), kept separate from the concurrent space-weather detection.

**Cost.** 951 multipath reports on the 2 dev days (157–161 per tractor per day; 8–22 s, median 17 s), of which
949 are unmatched and counted "benign" only by the scorer's ≤180 s multipath exemption. Manual inspection:
99.9 % sit at the recurrent reported-latitude band and 924 are co-timed on all three tractors (consistent with
a recurring environmental effect), but some are look-alikes: e.g. T2 05-04 13:04:54 (min 11.2 dB-Hz) and
13:46:10 (90 m off the band, single tractor) fall inside the T2 equipment-fault/spoofing episodes and are
most likely antenna dropouts reported a second time as multipath. The exemption does not make these harmless.

**Evaluation window (counts and validity only, after the change):** 7 → 490 detections with multipath on
(10 below the validator's 500 limit), validator OK, non-multipath entries unchanged, ~535 KiB.

**Limitations.** The labeled tractor is not distinguishable in telemetry (all three dip together); parameters
come from two labels plus an unlabeled census; it cannot separate antenna dropouts inside an equipment fault;
reported position is descriptive only (unverified, spoofable); confidence stays the fixed 0.5; the dashboard
is not adapted to hundreds of short detections (it uses the default config, so multipath is off there).

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
- TRN-11/12: multipath — matched only with the opt-in detector (`detect_multipath=True`, off by default);
  see "Suspected multipath" above.
- False positive: 05-05 22:00–22:06 spoofing fragment (T3).
- Confidence is a constant 0.5 (not calibrated).
- The fleet count used by the space-weather test (`n_cn0_low == 3`) still counts parked tractors; only the
  tractor being attributed must be working. Not changed here.

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

Working-state gate run, 2026-11-14 (on top of `c984ee4`):

- `python -m pytest -v tests/test_working_state.py`: 12 passed. With `require_working=False` the parked-only
  scenarios each produced a detection (checked separately).
- `python -m pytest -q tests`: 15 passed (12 synthetic + 3 dataset tests).
- `python src/evaluate_dev.py --data data --sweep`: equivalence IDENTICAL on both windows; default 27.29 /
  macro-F1 0.693 / onset 0.664 / 8 of 12 correct / 1 FP (before: 25.04 / 0.653 / 0.580 / 8 of 12 / 2).
- Evaluation-window detections with and without the gate: 7 and 7, none different, so
  `outputs/submission.json` was not regenerated.

Dashboard (`src/dashboard.py`), 2026-11-14, on top of `ec107b8`, no analytical source changed:

- Launched with `python -m streamlit run src\dashboard.py` and inspected in a browser at 1440×900:
  both windows, selecting detections (#1 equipment fault, #3 space weather on the evaluation day), the
  concurrent T2 equipment fault + spoof (development day), a custom interval, 1 min / 10 s / 1 s display
  (1 s correctly refused for a 3-hour interval), a single tractor, the labels section, the in-dashboard scorer,
  fleet comparison, reported-position plot, methodology/provenance.
- Displayed evaluation detections equal `outputs/submission.json` (all 7, including evidence). 1-minute display
  bins equal the pipeline's minute features for mean C/N0, min C/N0, cross-track error and link fraction
  (max difference 0 over 720 tractor-minutes). The in-dashboard score (27.29, macro-F1 0.693, onset 0.664,
  1 FP) matches `evaluate_dev.py`.
- Missing data folder: error naming the missing files plus the data command. Synthetic quiet data: "No
  detections in this window" and custom-interval mode; no labels file: "No labels file in this data folder".
  At the time, synthetic data with empty RFI/advisory lists raised `KeyError: 'ts'`; the input-validation
  review above documents the later fix.
- Network: all 148 page resources came from `localhost:8501`; usage telemetry disabled in `.streamlit/config.toml`.
- `python -m pytest -q tests`: 15 passed.

## Dashboard redesign: FIELD SIGNAL (worklog)

2026-11-14, on top of `e2f1cf0`. Display only: no change to `src/straightrows`, thresholds, confidence,
submission output, data or dependencies.

**Design.** Light "field instrument" theme set entirely in `.streamlit/config.toml` (ivory `#f5f1e6`,
charcoal `#23221e`, green accent `#2e6b4e`, fine `#cfc7b4` rules, serif headings, monospace code/timestamps);
no CSS selectors. Header: FIELD SIGNAL / Straight Rows · Fleet Guidance Investigation, with a status line
(in-sample for development, not measured for evaluation). Data folder and aggregation moved to
*Advanced settings*. A fleet incident ribbon (click or selector) replaces the opening table, which moved to
*Detection register*. One incident at a time: heading, interval, action; evidence charts left, decision brief
right; methodology and provenance on their own tab.

**Display-only mapping.** Up to three primary channels per attributed cause (see README). Equipment fault uses
the same link/dropout test as `evidence.py` to choose link channels or min C/N0 channels.

**Contrast** (WCAG ratios on `#f5f1e6`): body text 14.1, secondary text 6.4, green accent 5.6; tractor lines
T1 3.9, T2 3.65, T3 3.86 (T2/T3 darkened from the reference palette); white codes on cause bars 5.4–5.8;
working bar 4.8; parked bar 1.98 (intentionally faint; also shown by thickness and tooltip).

**Checks run.**
- Browser at 1366×768: heading at y≈566 (first screen), decision brief and charts after one short scroll;
  evidence chart 487 px in a 506 px column, no horizontal scroll. At 1920×1080 the heading (694), brief (881)
  and first chart (919) are all in the first screen. Ribbon click selected #3; the selector then selected #2
  without the earlier click overriding it; tooltip legible (ivory background, charcoal text) and correct.
- `streamlit.testing.AppTest` (headless): all 7 evaluation incidents and the development T2 fault/spoof and T1
  link fault render with heading, action and interpretation; chart sets match the mapping (dropout fault →
  min C/N0/satellites/mean C/N0; link fault → link/RTK_FIXED/min C/N0). Switching window resets the selection
  to #1. Custom interval, missing data folder, no detections and no labels file show their messages without
  exceptions.
- Evaluation output from the pipeline equals `outputs/submission.json`; `src/straightrows` etc. unchanged vs
  `e2f1cf0`; data hashes unchanged; `python -m pytest -q tests`: 15 passed; no server errors.

**Not checked.** Screen readers; touch devices; browser zoom levels other than 100 %; colour-vision simulation of
the full page (T1 blue and T3 green have similar lightness, 1.13:1; they are told apart by hue, legend and
tooltip). Some screenshots could not be taken while the app window was hidden; those checks used DOM
measurements and AppTest instead.

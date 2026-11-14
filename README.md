# Straight Rows: degraded-guidance detection and attribution

Solution for the individual Bluestaq × NDSU **Straight Rows Hackathon** (Nov 13–14, 2026).
It reads 72 h of simulated 1 Hz telemetry from three tractors near Casselton, ND, plus Space Domain
Awareness feeds, and reports **when guidance degraded, which tractors were affected, the likely cause,
the recommended action, a confidence value, and evidence computed from the measurements**.

Causes and actions are the official ones: `SPACE_WEATHER` → `HALT_OR_DEGRADED_MODE`,
`JAMMING` → `HALT_AND_REPORT`, `SPOOFING` → `HALT_CROSSCHECK_AND_REPORT`,
`EQUIPMENT_FAULT` → `SERVICE_MACHINE_OTHERS_CONTINUE`, `MULTIPATH` → `CONTINUE_FALSE_ALARM`.

## Setup (Windows CMD)

Tested with **Python 3.11.0** on Windows 11. All commands below run from the repository root and
use the project-local interpreter `.venv\Scripts\python.exe`.

```bat
:: 1. Create the environment (requires Python 3.11 on PATH or the py launcher)
py -3.11 -m venv .venv

:: 2. Install the pinned dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` pins the exact versions installed in the tested environment (pandas 3.1.1,
numpy 2.4.6, matplotlib 3.11.2, pytest 9.2.0, streamlit 1.67.0, altair 6.3.0, among others). Some pinned
packages (for example pydeck) are not imported by the code.

**Clean-copy reproduction (2026-11-14, same Windows machine):** a fresh `git clone` into a temporary folder,
`py -3.11 -m venv .venv` (Python 3.11.0, bundled pip 22.3) and the install command above succeeded from PyPI
with certificate verification on; `pip check` reported no broken requirements. Every command in this README
then ran in that copy with the results stated below. Not tested: another machine or operating system, another
Python version, an offline install.

## Get and verify the data

**What the data is.** A **synthetic simulation** produced by the organizers (Bluestaq) for this hackathon:
72 h of 1 Hz telemetry for three simulated tractors (`farm\tractor_telemetry.csv.gz`), simulated SDA feeds
(`sda\sgi_indices.json` with Kp and Dst, `sda\scintillation_series.json` with regional S4,
`sda\constellation_advisories.json`, `sda\rfi_reports.json`) and development labels for May 4–5
(`labels\train_episodes.json`). No real farm, receiver or space-weather measurements are involved.

**How labels are used.** Only the 12 development episodes have labels. `straightrows.io.load` reads the labels
file when it is present, but no detection, attribution, assembly or evidence step uses it; only
`src\evaluate_dev.py` (scoring) and the dashboard's separate "Development labels" section use the labels, to score
and inspect development output. Parameters
were chosen on these labels, so development scores are in-sample. The evaluation day (May 6) has no public
labels.

The dataset is **not** in this repository. It is published by the organizers as
`StraightRows_Student_Package.zip` on the
[latest release](https://github.com/Bluestaq/ndsu-hackathon-submissions/releases/latest).
`scripts\get_data.py` and `DATASET_SHA256` are the official, unmodified starter files
(see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

**Direct download (official default):**

```bat
.venv\Scripts\python.exe scripts\get_data.py
```

It downloads the release zip, checks its SHA-256 against `DATASET_SHA256` (`14bfdf4c…174546`), refuses a
mismatch, and extracts only the `data\` folder into `data\` (existing files with the same names are replaced).
Expected result: `Extracted 6 data files into …\data`. In the clean-copy reproduction (2026-11-14) this worked,
and the six files were byte-identical to the development copy. Earlier on the same machine it failed with
`SSL: CERTIFICATE_VERIFY_FAILED` because that Python installation did not trust the certificate chain; if that
happens, use the local zip below. Do **not** disable certificate verification.

**Local-zip fallback:** download the zip in a browser, then:

```bat
.venv\Scripts\python.exe scripts\get_data.py --zip C:\path\to\StraightRows_Student_Package.zip
```

The same checksum check and extraction apply. This path was used to obtain the development copy earlier;
it was not re-run in the clean-copy reproduction (the zip was not on disk).

## Network and offline operation

| Step | Network |
|---|---|
| `pip install -r requirements.txt` | PyPI (once) |
| `scripts\get_data.py` without `--zip` | GitHub release download (once) |
| `scripts\get_data.py --zip …`, tests, pipeline, validation, development evaluation, plots | none |
| Dashboard | none: served on `localhost`, no web fonts, map tiles or external scripts; usage telemetry off |

No step calls an LLM or any online API at analysis time.

## Run

```bat
:: Tests (-rs prints the reason for any skipped test)
.venv\Scripts\python.exe -m pytest -q -rs tests

:: Generate the submission file (creates the output folder if needed)
.venv\Scripts\python.exe src\run_pipeline.py --data data --output outputs\submission.json --github-handle reno-ogden --repo-url https://github.com/reno-ogden/straight-rows

:: Official format validation
.venv\Scripts\python.exe src\validate_submission.py outputs\submission.json

:: Development evaluation on the 12 labeled episodes (add --sweep for the bridge-gap sweep)
.venv\Scripts\python.exe src\evaluate_dev.py --data data

:: Optional analysis outputs
.venv\Scripts\python.exe src\plot_dev_episodes.py --data data --out outputs\dev_plots
.venv\Scripts\python.exe src\dev_episode_stats.py --data data --out outputs\dev_episode_stats.csv
```

**Check that the dataset tests actually ran.** With `data\` present the expected test result is
`41 passed` (3 dataset tests + 38 synthetic tests). Without `data\`, pytest still exits successfully but reports
`38 passed, 3 skipped` with the reason `dataset not downloaded`: that is **not** a successful analysis run.
`run_pipeline.py` and `evaluate_dev.py` stop with `Dataset not found …` and write nothing if `data\` is missing.

`src\validate_submission.py` is the official validator (`starter/submission/validate_submission.py`), identical
apart from line endings (see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

Current clean-copy results (2026-11-14 ~19:15 UTC, commit `91262e3`): fresh `git clone`, new Python 3.11.0
venv, `pip install -r requirements.txt`, `pip check` clean; without `data\`: `38 passed, 3 skipped` and
`run_pipeline.py` stops with `Dataset not found` (exit 1, nothing written); with the checksum-verified dataset:
`41 passed`; `run_pipeline.py` output byte-identical to the designated `outputs\submission.json`
(SHA-256 `27ed40c5…60ccb6`); official validator `OK: 7 detection(s)`; `evaluate_dev.py` reproduced the
*Development results* table; the dashboard loaded headlessly (overview, an evaluation report, development
window, the TRN-03 report). The dataset in that copy was copied from an earlier clean copy whose direct download
passed the checksum check, not downloaded again.

Earlier clean-copy results (2026-11-14, before the input-validation tests): `33 passed`; `Wrote 7 detections`; both the repository copy and a freshly
downloaded official validator print `OK: 7 detection(s)`; the output was byte-identical to the development
copy's `outputs\submission.json` and to a second run; `evaluate_dev.py` reproduced the table under
*Development results*; both optional analysis scripts ran (12 plots); the dashboard loaded headlessly
(Streamlit `AppTest`: overview, a report, window switch). The dashboard was not opened in a browser from the
clean copy.

| Output | Written by | Notes |
|---|---|---|
| `outputs\submission.json` | `run_pipeline.py` | Replaced on each run. Deterministic: repeated runs give identical bytes. |
| `outputs\dev_plots\*.png` | `plot_dev_episodes.py` | One plot per labeled episode. Replaced on each run. |
| `outputs\dev_episode_stats.csv` | `dev_episode_stats.py` | Per-episode statistics. Replaced on each run. |
| console | `evaluate_dev.py`, `validate_submission.py`, tests | Nothing written. |

`outputs\` is not committed. The submission file is submitted by copying it into a fork of the
official repository (see *Submission* below).

## Dashboard: FIELD SIGNAL

```bat
.venv\Scripts\python.exe -m streamlit run src\dashboard.py
```

Run it from the repository root so `.streamlit\config.toml` is used (light report theme with a navy header, no
usage telemetry, no auto-opened browser, localhost only). Open http://localhost:8501 (if that port is busy, add
`--server.port 8502`). No network access is needed: no web fonts, map tiles or external scripts.

**Data source.** The dashboard calls the pipeline itself: `straightrows.io.load`, `pipeline.detect`,
`export.to_submission` (so detections, actions, confidence and evidence are exactly what goes into
`submission.json`), `features.minute_features` + `candidates.flag` for the working flag and per-minute flags,
`attribution.tests` for per-minute rule results, and `evidence._stats` for measurements (the function behind the
exported evidence numbers). It has no detector of its own. Results are cached per data folder (file size and
modification time), window and `Config` values.

### Navigation: an interactive incident report

One level fills the screen at a time.

1. **Header** (navy band): FIELD SIGNAL, the Evaluation/Development switch with the window's UTC dates, one
   status line (evaluation: unlabeled, accuracy unknown; development: labeled, scores in-sample) and *Settings*
   (data folder).
2. **Fleet overview — choose a case.** A T1/T2/T3 timeline of pipeline detections (cause colour + text code;
   concurrent causes in sub-rows) and a list with one row per detection: suspected cause, tractors, UTC interval,
   short action and *Open report*. Rows are in time order; nothing is ranked. Clicking a timeline bar or a row
   opens that report; the last-opened detection stays highlighted in both. Below: *Explore a custom interval*,
   the *Detection register* (exact exported fields), *Development labels* with in-sample scoring (development
   window only) and *About this analysis* (methodology, display definitions, provenance).
3. **Incident report — the finding and the decision.** A navigation bar (*← Back to fleet*, *‹ Previous*,
   *n of N*, *Next ›*, and a slim clickable timeline), then a heading such as "Suspected equipment fault · T1"
   with the UTC interval and duration. Two columns:
   - *Evidence lab* (wide): one question per view —
     **Guidance** (cross-track error), **Receiver health** (mean C/N0, min C/N0, satellites), **Link & fix**
     (RTK link, RTK_FIXED), **Space / RF** (S4 with the scintillation level and RFI report ticks, Kp),
     **Before / after** (per-tractor dot/slope chart + pooled table), **Position** (reported GNSS), **All
     signals**. Each view has one prominent chart, a measured observation and access to the numbers. The default
     view depends on the attributed cause (display only: spoofing → Guidance, jamming → Receiver health, space
     weather → Space / RF, equipment fault → Receiver health or Link & fix by the same test the evidence uses).
     Tractor focus (*All tractors*/T1/T2/T3) dims the others; *Chart options* sets context minutes and display
     aggregation.
   - *Finding* (narrow): recommended action (episode-level), what was observed during the detection, the pipeline
     rule with how many minutes it was true per tractor, and the main uncertainty with the fixed confidence.
   - *Details* (one expander): exported evidence and identifiers, full measurements, rules and confidence,
     methodology and limitations, provenance.
4. **Custom interval.** Any start hour and length, the same evidence lab (with *Compare tractors* instead of
   Before / after).

**Replay.** Every time-based view has one scrubber (1 s steps inside the charted interval), *−10 s / +10 s*,
*More* (±1 min, onset, end) and *Full readout*. The cursor is drawn on every chart and on the position plot. The
inline inspector shows the raw 1 Hz values relevant to the current view; *Full readout* shows every field,
the working flag of that minute, episode-level detection membership, and S4/Kp in force with their publication
time. Only an exact timestamp match is shown (tolerance 0 s; the telemetry is complete 1 Hz); otherwise
*no sample*. Episode attribution is never recomputed at the cursor.

**Display-only statistics** (documented in the app under *Display definitions*):

- *Rule-minute counts*: minutes in the detection where the cause's `attribution.tests` result (or a
  `candidates.flag` column) is true, per tractor.
- *Before / during / after*: `evidence._stats` over Before = 30 min before onset, working samples
  (speed > 0) — the exported baseline; During = the detection, all samples — the exported statistics;
  After = 30 min after the end, working samples — a display-only mirror. The table pools the affected tractors
  as the evidence does; the chart applies the same function per tractor. Empty windows show *unavailable*;
  overlapping detections are named.
- *Axes*: mean C/N0 at least 20–50 dB-Hz, min C/N0 at least 0–50 dB-Hz, satellites/link/fix from zero, so small
  changes are not magnified. Dotted amber lines are the pipeline's rule levels (applied by the rules to 1-minute
  values).

**Units and aggregation.** Cross-track error in metres (guidance-monitor channel, signed, bin mean); C/N0 in
dB-Hz (mean: bin mean; min: bin minimum); satellites: bin median; RTK link up and RTK_FIXED: % of samples; S4
(15-min) and Kp (3-hour) as the latest published value. Bins: 1 min (equal to the pipeline's features), 10 s, or
1 s for intervals up to 30 minutes. No smoothing; lines break at missing bins. Tractor colours are fixed (T1
blue, T2 orange, T3 green, plus labels and marker shapes); causes use a separate hue set and always carry a text
code; tractors outside the detection are dashed.

**Reported position** is labelled "may be misleading during spoofing": 10 s mean reported positions in metres
from the interval's mean position (flat-earth conversion), equal scale, trails broken at gaps, bright up to the
cursor, 1 Hz markers at the cursor. No field boundary, intended row or true location is drawn, and cross-track
error is not derived from it.

The charts show the inputs behind each detection. They do not independently validate the detector.

## How it works

`src/straightrows/` runs these stages in order (parameters in `config.py`; details in
[docs/pipeline.md](docs/pipeline.md)):

1. **Load** (`io.py`): raw files read-only; every timestamp parsed as timezone-aware UTC.
2. **Features** (`features.py`): per-tractor, per-minute mean C/N0, minimum C/N0, mean cross-track error,
   mean speed and RTK-link-up fraction; the regional S4 and Kp values in force at each minute.
3. **Candidates** (`candidates.py`): cause-agnostic flags such as low C/N0, high cross-track error,
   link loss and antenna dropout, plus how many tractors show low C/N0 at once.
4. **Attribution** (`attribution.py`): one independent test per cause, so a tractor-minute can carry
   more than one cause.
5. **Assembly** (`assembly.py`): minute runs → bridge same-cause gaps ≤ 180 s → drop runs < 180 s →
   merge the same cause across tractors. Different causes are never merged, so concurrent causes stay
   separate detections.
   **Suspected multipath** (`multipath.py`, opt-in via `Config.detect_multipath`, **off by default**) is a
   separate 1 Hz path: short min-C/N0 dips (≥ 6 dB below a 121 s running median for 8–60 s, mean C/N0 within
   2 dB of its own median, tractor working) become one detection per tractor per dip, outside minute assembly.
6. **Evidence** (`evidence.py`): strings computed from the 1 Hz telemetry and SDA feeds over each
   detection (affected vs. own prior 30 min vs. other tractors, S4/Kp/Dst, how many minutes the cause's
   per-minute rule held on each listed tractor and how bridging/merging shaped the interval, nearby RFI
   reports, concurrent detections). Times carry the date and UTC; RFI and SDA timestamp meanings are stated as
   undocumented; "no RFI report" is not presented as proof that no interference occurred.
7. **Export** (`export.py`): `submission.json` in the official template's shape.

Inputs and how they are treated:

- **Cross-track error** comes from the separate simulated guidance monitor (per the official
  guide). It is used as its own input (metres). It is exactly 0 while parked.
- **Reported GNSS position (lat/lon) is not trusted ground truth.** Detection never uses it. It
  appears only in evidence: the approximate distance from an RFI report's centre, and (multipath, opt-in)
  the reported distance between successive dips, labelled as unverified and spoofable.
- `src/baseline.py` is the **official starter baseline modified** to use S4 instead of Kp
  (commit `b40c92e`). It is kept for comparison; the pipeline's `STARTER` config reproduces it exactly.

## Development results (in-sample)

Scored with the organizers' published scorer (`tools/score_submission.py`, code unchanged) against the
**12 labeled development episodes** (May 4–5, simulated). The parameters were chosen on these same
episodes, so these are **in-sample** numbers. They are **not** evaluation-window performance: the
evaluation labels are not public, and the organizers score once after the lock. The analysis is
retrospective (intervals are assembled after the whole window is available); onset credit measures how close a
detection's start is to the labeled start, not real-time alerting latency.

| Variant | Diagnostic /40 | Macro-F1 | Onset credit | Episodes correct | False positives |
|---|---:|---:|---:|---:|---:|
| `src/baseline.py` (S4-modified starter) | 21.29 | 0.553 | 0.497 | 7/12 | 3 |
| Pipeline without the working gate | 25.04 | 0.653 | 0.580 | 8/12 | 2 |
| Pipeline (default) | 27.29 | 0.693 | 0.664 | 8/12 | 1 |
| Pipeline + multipath (opt-in, not default) | 34.79 | 0.893 | 0.830 | 10/12 | 1 |

Still missed on development data with the default pipeline: TRN-05 (jamming during the storm), TRN-08
(spoofing during the storm), TRN-11/12 (multipath). Remaining false positive: a 6-minute spoofing fragment on
T3 at 05-05 22:00. With the opt-in multipath detector, TRN-11 and TRN-12 are matched (onset +0 s) and no other
class changes, but it adds 951 short reports on the two development days; 949 are unmatched and are not
counted as false positives only because the scorer exempts short multipath reports. That exemption is not
evidence that they are useful or harmless (see `docs/pipeline.md`, "Suspected multipath").

## Tests

`tests/test_pipeline.py` has three tests that use the challenge data:

1. With the `STARTER` config, the pipeline produces the same intervals, tractors and classes as
   `src/baseline.py` on both the development and evaluation windows.
2. Overlapping causes on one tractor (TRN-06 spoofing inside TRN-09 equipment fault, T2) stay
   separate detections.
3. The evaluation-window output passes the official validator, and every detection has non-empty
   evidence.

Without `data\` these three are skipped rather than failed, so a passing run without the dataset does not
show that the analysis works (see *Check that the dataset tests actually ran* above).

`tests/test_working_state.py` has twelve synthetic tests (no dataset needed) for the working-state
gate: parked-only poor reception creates no space-weather, jamming or equipment-fault detection;
the same symptoms while working do; detections start and end at working-state transitions; long stops
are not bridged; a stop of at most 180 s inside one incident is.

`tests/test_multipath.py` has eighteen synthetic tests for the opt-in multipath path: a 17 s dip gives
one detection with exact 1 Hz boundaries that survives minute assembly; brief blips, shallow dips, long lows,
dips with a falling mean C/N0 and dips while parked do not trigger; brief recoveries and missing samples inside
a dip are joined (only real samples counted), longer gaps are not; no detection without a running-median
baseline; window boundaries clip; repeated dips are each reported once with recurrence evidence; co-timed dips
stay separate per tractor; a concurrent equipment fault is unchanged and kept as its own cause; the detector is
off by default and in `STARTER`.

`tests/test_input_validation.py` has eight focused checks: empty optional RFI/advisory feeds load;
conflicting duplicate tractor-seconds, null required telemetry, empty required Kp, and invalid configuration
values fail with clear errors. Missing sample timestamps remain allowed; the documented gap rules apply.

The tests do **not** establish that detections are correct, check the development score, check
that evidence numbers are right, or exercise the command-line scripts.

## Limitations and known issues

- **Multipath is not detected by default.** The opt-in detector (`Config.detect_multipath=True`) matches
  both development labels but reports every recurring dip on every tractor (~160 per tractor per day; 490
  detections in the evaluation window, 10 below the validator's 500 limit). It cannot tell which tractor a
  label would name, it can report an equipment-fault antenna dropout a second time as multipath, and the
  dashboard is not adapted to that volume.
- **Confidence is fixed at 0.5** for every detection. It is not calibrated and is not a probability.
- **Dashboard limitations:** no automatic playback (manual replay only). Streamlit columns only stack below
  ~640 px, so between that and ~1100 px the report's two columns get narrow. Screen-reader, keyboard-only
  timeline use, touch, zoom and colour-vision checks have not been done. A replay button pressed while the page
  is still re-running may be dropped.
- **Input validation:** the loader rejects null required fields, duplicate tractor-seconds, unexpected tractor
  IDs, and empty required SDA series. Empty optional RFI/advisory feeds load. It does not require continuous
  1 Hz sampling; missing minutes can be bridged by the detector's existing gap rule.
- **Working state** = 1-minute mean speed above 1.0 m/s. Speed is only ever 0 or 4.5 m/s, so that means
  at least 14 moving seconds in the minute. All causes require the attributed tractor to be working.
  A stop of at most 180 s inside one incident is bridged and therefore included in the interval.
  The space-weather fleet count (all three tractors low) still counts parked tractors.
- Jamming is decided from absolute C/N0 plus quiet S4, so jamming during a storm is missed. RFI reports
  are used only as evidence.
- Merging the same cause across tractors can overstate which tractors were affected.
- Whether SDA timestamps mark the start or end of their interval, and whether RFI `ts` is the
  observation or the report time, is not documented. The pipeline uses the latest value at or
  before each minute.
- The analysis is retrospective: intervals are assembled after the whole window is available, so onset
  results are not real-time alerting performance.

## AI assistance

This project was built with the help of Claude (Anthropic), an AI assistant, used through Claude Code. It
wrote and revised much of the code, tests and documentation and ran the checks described here, under the
author's direction; the author chose the approach and approved each change. Commits carry a
`Co-Authored-By: Claude` trailer. No AI model or online API is used when the analysis runs: detections,
evidence and the dashboard come only from the deterministic code in this repository and the official data.

## Submission

The current official instructions (event site *Submit* page and `submissions/README.md` in the official
repository) **take precedence over the older PDF guide**. The submission file identifies the participant
only by `participant.github_handle` (an optional `display_name` is allowed). It must **not** contain an
email address or student ID. To submit before **Saturday, 14 Nov 2026, 4:00 pm CT (22:00 UTC)**:

1. Make this repository public.
2. Fork `Bluestaq/ndsu-hackathon-submissions` and add exactly `submissions/reno-ogden/submission.json`.
3. Open one pull request to `main`, and check that the Submission check passes.

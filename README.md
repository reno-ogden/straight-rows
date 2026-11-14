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
numpy 2.4.6, matplotlib 3.11.2, pytest 9.2.0, among others). A fresh install from it on a clean
machine has not been tested. The dashboard uses the pinned streamlit 1.67.0 and altair 6.3.0; some other
pinned packages (for example pydeck) are not imported by the code.

## Get and verify the data

The dataset is **not** in this repository. It is published by the organizers as
`StraightRows_Student_Package.zip` on the
[latest release](https://github.com/Bluestaq/ndsu-hackathon-submissions/releases/latest).
`scripts\get_data.py` and `DATASET_SHA256` are the official, unmodified starter files
(see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

**Local-zip workflow (tested):** download the zip in a browser, then:

```bat
.venv\Scripts\python.exe scripts\get_data.py --zip C:\path\to\StraightRows_Student_Package.zip
```

The script checks the zip's SHA-256 against `DATASET_SHA256`
(`14bfdf4c…174546`), refuses a mismatch, and extracts only the `data\` folder into `data\`
(existing files with the same names are replaced). Expected result: `Extracted 6 data files`.

**Direct download** (`.venv\Scripts\python.exe scripts\get_data.py` with no arguments) is the
official default. On the development machine it failed with
`SSL: CERTIFICATE_VERIFY_FAILED`, because that Python installation does not trust the certificate
chain. Use the local-zip workflow in that case. Do **not** disable certificate verification.

## Run

```bat
:: Tests (need data\; they are skipped if the dataset is missing)
.venv\Scripts\python.exe -m pytest -q tests

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

Run it from the repository root so `.streamlit\config.toml` is used (ivory "field instrument" theme, no
usage telemetry, no auto-opened browser, served on localhost only). Then open http://localhost:8501. It needs
no network access: all page resources are served by the local Streamlit server.

**Data source.** The dashboard calls the pipeline itself: `straightrows.io.load`, `pipeline.detect`,
`export.to_submission` (so detections, actions, confidence and evidence are exactly what goes into
`submission.json`), `features.minute_features` + `candidates.flag` for the working flag, and
`evidence._stats` for the measurement table (the same function that writes the exported evidence numbers).
It has no detector of its own and does not use `devdata.py`. Results are cached per data folder (keyed by
file size and modification time), window and `Config` values, so changing inputs or configuration recomputes.

**Layout (one incident at a time).**

- *Header and sidebar:* window choice (development or evaluation, UTC bounds shown). Data folder and display
  aggregation sit under *Advanced settings*. The status line states whether scores are in-sample
  (development) or not measured (evaluation).
- *Fleet incident ribbon:* T1/T2/T3 lanes across the window; each pipeline detection is a bar with a cause
  colour and a text code (SW, JAM, SPF, EF). Concurrent causes on one tractor sit in separate sub-rows.
  Click a bar, or use the *Incident* selector next to it. The full table is under *Detection register*.
- *Selected incident:* plain-language heading, full UTC interval, "pipeline attribution, not confirmed
  truth", and the operator action in words. Exact identifiers are under *Identifiers*.
- *Evidence (left):* incident lane (selected bar solid, adjacent incidents faded), a working-state strip only
  when the state changes (otherwise one line of text), and up to three primary channels chosen for the
  attributed cause (display only; see below). Every channel is under *Inspect all signals*; the exact
  submission evidence is under *Exact evidence exported to submission*.
- *Decision brief (right):* observed measurements (incident tractors vs. others vs. the same tractors' prior
  30 working minutes), the SDA and RFI lines from the evidence, the pipeline's attribution line(s), the
  recommended action, and uncertainty (fixed confidence 0.5, the rule that fired with its configured values,
  and known gaps).
- *Fleet comparison* and *Methodology and limitations* tabs: per-tractor statistics, the reported-GNSS-position
  view (not ground truth), methodology, display choices, aggregation and provenance (window, data folder,
  git commit, every `Config` value).

**Primary channels (display only; detection is unaffected).** Space weather: mean C/N0, regional S4,
RTK_FIXED. Jamming: mean C/N0, satellites, cross-track error. Spoofing: cross-track error, mean C/N0,
satellites. Equipment fault: chosen with the same test the evidence text uses. Antenna dropouts give min
C/N0, satellites, mean C/N0; correction-link loss gives RTK link up, RTK_FIXED, min C/N0. Cross-track error
is never primary for equipment fault: the rule does not use it, and a concurrent spoof can inflate it.

**Units and aggregation.** Cross-track error in metres (guidance-monitor channel, signed, bin mean); C/N0 in
dB-Hz (mean C/N0: bin mean; min C/N0: bin minimum); satellites: bin median; RTK link up and RTK_FIXED: % of
samples; S4 (15-min values) and Kp (3-hour values) drawn as the latest published value. Bins: 1 min (equal to
the pipeline's features for the shared channels), 10 s, or 1 s for intervals of at most 30 minutes. Lines
break at missing bins and never join different tractors. Tractor colours are fixed on every chart (T1 blue,
T2 orange, T3 green); lines for tractors outside the selected incident are dashed.

**Development labels** (development window only) are in a separate, labelled section, never mixed with
detections. A button scores the detections against them with the official scorer (in-sample).

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
6. **Evidence** (`evidence.py`): strings computed from the 1 Hz telemetry and SDA feeds over each
   detection (affected vs. own prior 30 min vs. other tractors, S4/Kp/Dst, nearby RFI reports,
   concurrent detections).
7. **Export** (`export.py`): `submission.json` in the official template's shape.

Inputs and how they are treated:

- **Cross-track error** comes from the separate simulated guidance monitor (per the official
  guide). It is used as its own input (metres). It is exactly 0 while parked.
- **Reported GNSS position (lat/lon) is not trusted ground truth.** Detection never uses it. It
  appears only in evidence, as the approximate distance from an RFI report's centre.
- `src/baseline.py` is the **official starter baseline modified** to use S4 instead of Kp
  (commit `b40c92e`). It is kept for comparison; the pipeline's `STARTER` config reproduces it exactly.

## Development results (in-sample)

Scored with the organizers' published scorer (`tools/score_submission.py`, code unchanged) against the
**12 labeled development episodes** (May 4–5, simulated). The parameters were chosen on these same
episodes, so these are **in-sample** numbers. They are **not** evaluation-window performance: the
evaluation labels are not public, and the organizers score once after the lock.

| Variant | Diagnostic /40 | Macro-F1 | Onset credit | Episodes correct | False positives |
|---|---:|---:|---:|---:|---:|
| `src/baseline.py` (S4-modified starter) | 21.29 | 0.553 | 0.497 | 7/12 | 3 |
| Pipeline without the working gate | 25.04 | 0.653 | 0.580 | 8/12 | 2 |
| Pipeline (default) | 27.29 | 0.693 | 0.664 | 8/12 | 1 |

Still missed on development data: TRN-05 (jamming during the storm), TRN-08 (spoofing during the storm),
TRN-11/12 (multipath). Remaining false positive: a 6-minute spoofing fragment on T3 at 05-05 22:00.

## Tests

`tests/test_pipeline.py` has three tests that use the challenge data:

1. With the `STARTER` config, the pipeline produces the same intervals, tractors and classes as
   `src/baseline.py` on both the development and evaluation windows.
2. Overlapping causes on one tractor (TRN-06 spoofing inside TRN-09 equipment fault, T2) stay
   separate detections.
3. The evaluation-window output passes the official validator, and every detection has non-empty
   evidence.

Without `data\` these three are skipped rather than failed.

`tests/test_working_state.py` has twelve synthetic tests (no dataset needed) for the working-state
gate: parked-only poor reception creates no space-weather, jamming or equipment-fault detection;
the same symptoms while working do; detections start and end at working-state transitions; long stops
are not bridged; a stop of at most 180 s inside one incident is.

The tests do **not** establish that detections are correct, check the development score, check
that evidence numbers are right, or exercise the command-line scripts.

## Limitations and known issues

- **Multipath is not detected.** No `MULTIPATH` detections are produced.
- **Confidence is fixed at 0.5** for every detection. It is not calibrated and is not a probability.
- **Dashboard limitations:** chart widths are fixed (evidence ~490 px, ribbon ~790 px) and do not stretch on
  wide screens; very narrow windows scroll sideways. The reported-position plot does not use equal x/y scales.
  "Parked" bars in the working strip are deliberately faint (1.98:1 on the background); state is also shown
  by bar thickness and in the tooltip.
  `straightrows.io.load` fails if the RFI or advisory feed is an empty list (`KeyError: 'ts'`); the
  dashboard then shows that error rather than a page.
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
- Evidence times are HH:MM (UTC) without a date.

## Submission

The current official instructions (event site *Submit* page and `submissions/README.md` in the official
repository) **take precedence over the older PDF guide**. The submission file identifies the participant
only by `participant.github_handle` (an optional `display_name` is allowed). It must **not** contain an
email address or student ID. To submit before **Saturday, 14 Nov 2026, 4:00 pm CT (22:00 UTC)**:

1. Make this repository public.
2. Fork `Bluestaq/ndsu-hackathon-submissions` and add exactly `submissions/reno-ogden/submission.json`.
3. Open one pull request to `main`, and check that the Submission check passes.

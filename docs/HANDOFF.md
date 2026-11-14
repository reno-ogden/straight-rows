# Handoff — Straight Rows (written 2026-11-14 02:20 CST; readiness update 2026-11-14 08:25 UTC)

## Readiness verification — 2026-11-14 08:25 UTC (supersedes older state where they differ)

- Git: branch `main`, HEAD `6c2bb1b` (docs handoff commit on `00f52cd`); local `origin/main` ref = `6c2bb1b`
  (not re-fetched). No stash, no other branches. Working tree clean apart from untracked `outputs/` and this
  uncommitted `docs/HANDOFF.md` edit. **No uncommitted dashboard work exists.**
- Backup: `outputs/submission.before-readiness-20261114T082526Z.json` (SHA-256 `5e62e998…e06cc`, = `outputs/submission.json`).
- Regenerated into new folder `outputs/readiness-20261114T082526Z/` with the CLAUDE.md submission command
  (`.venv` Python 3.11.0): `Wrote 7 detections`; **byte-identical** to `outputs/submission.json`.
- Validators: repo `src/validate_submission.py` and official `starter/submission/validate_submission.py` at
  official main `4b9c010` (still current at 08:2x UTC; content identical to the repo copy except CRLF line endings)
  both print `OK: 7 detection(s)` on the regenerated and preserved files.
- Official `.github/scripts/check_submission_pr.py` `check()` run offline with stubbed GitHub API responses:
  privacy findings none; with repo simulated **private** → 1 error "solution repository … is not public yet";
  simulated public → no errors/warnings. Workflow deadline: `SUBMISSION_LOCK_UTC` default `2026-11-14T22:00:00Z`, grace 0.
- Tests: `pytest -q tests` → 15 passed, 0 skipped.
- `data/` SHA-256 of all 6 files identical before and after the run; release zip not on this machine, so the
  comparison to the zip hash in `DATASET_SHA256` was **not** re-run today.
- Not run: real PR check (needs a PR), fresh clone, clean `pip install`, dashboard re-check.

### Remaining submission steps (all require the user; each needs explicit authorization)

1. Make `reno-ogden/straight-rows` public (the PR check fails while private). Decide first on the personal git
   author email in history and the tracked guide PDF (see Known issues).
2. Fork `Bluestaq/ndsu-hackathon-submissions`; add exactly `submissions/reno-ogden/submission.json`
   (copy of `outputs/submission.json`); open one PR to `main` before 22:00 UTC; confirm the Submission check is green.
3. Any push to the PR after 22:00 UTC makes it late.

## Polish and reliability pass (2026-11-14 ~14:55 UTC)

Committed on local branch `feat/blue-investigation-workspace` on top of `6155945` (not pushed, not merged); only `src/dashboard.py` and this
file changed. Layout direction, features, pipeline, data and schema unchanged.

Launch (Windows CMD, repo root): `.venv\Scripts\python.exe -m streamlit run src\dashboard.py` → http://localhost:8501

**Header (measured in the browser, then fixed).** Causes: (1) the main block container had `max-width: 1680px`,
centred, so the band could not reach the viewport edges; (2) Streamlit gives the keyed block `width/max-width:
100%`, so its negative right margin had no effect (band ended 48 px short); (3) a 16 px flex gap after the hidden
`<style>` element pushed the band down; (4) Streamlit's `margin-bottom: -16px` on markdown containers let the
date line overflow the band's bottom. Fixes (scoped to `.st-key-shell` plus `max-width: none` on the container):
explicit `width: calc(100% + 3rem)`, `max-width: none`, `margin-top: -1rem`, `margin-bottom: 0` on markdown inside
the band, 0.35rem inner gap, white Settings button. No `vw` units, no overflow hiding. Verified by DOM
measurement at 1920/1366/1024: band spans 0 → scroll-container width (scrollbar excluded), no horizontal
overflow, date line inside the band, wraps at 1024.

**Navigation (reproduced, profiled, fixed).** Mechanism: Streamlit reruns (no full page reloads); `on_click` /
`on_select` callbacks change session state before the rerun, so the first run already renders the new view (no
flash of a different incident, no loop). Root causes of choppiness: report reruns took ~1.3–1.6 s of Python
(headless timing) while Streamlit showed the old view faded. Profile: Altair `to_dict` JSON-schema validation of
six specs (~0.5 s), `.configure_*()` deep copies (~0.4 s), rebuilding the unchanged window timeline, and a `git`
subprocess for provenance on every rerun. Fixes: charts serialised once with `to_dict(validate=False)` and shown
with `st.vega_lite_chart` (same `on_select`), theme merged as a plain config dict, timeline specs cached
(`timeline_spec`, keyed by data signature, window, config, selection), `git_commit` cached (120 s). Headless
timings, before → after: fleet rerun 0.6 → ~0.2 s; report revisit 1.6 → ~0.6 s; replay step 1.6 → ~0.66 s.
Also: navigation clicks scroll to the top once (one-shot flag, script emitted at page end; ordinary reruns keep
scroll); Previous/Next stop at the ends (disabled) instead of wrapping.
Framework limits: Streamlit still re-renders the page on each interaction and briefly shows stale elements; the
browser Back button does not navigate between app views; cached specs are keyed by their own function source,
so after editing chart code restart the server (runtime data/config changes do invalidate correctly).

**Other bugs fixed.** Compact report timeline bars were ~2 px tall (cause sub-rows) and effectively unclickable →
10 px bars per lane; full timeline used one sub-row per cause in the window (thin bars) → sub-rows only where
detections overlap on a tractor (greedy packing; overlaps still visible). With `vega_lite_chart`, Streamlit's
`autosize: fit` squeezed titles/axes into the plot height and clipped supporting-chart titles → `fit-x`.
Nav buttons, tractor focus and Chart options truncated below ~1200 px → wrapping horizontal containers. Row
interval text "01:00 → 02:00 60 min" ran together → "05-06 · 01:00–02:00 UTC · 60 min" (no-wrap); report
meta "2026-05-06 01:00–02:00 UTC · 60 min". Selected row has a text label "last opened" plus hover/focus
states. Inspector labels "C/N0 mean … · min … dB-Hz · satellites". In-app display definitions used old view
names. Settings button lost contrast while open.

**Checks performed.**

| Check | Result |
|---|---|
| `pytest -q tests` | 15 passed |
| Regenerate → new `outputs/polish-verify-20261114T145420Z/` | parsed JSON equal to `outputs/submission.before-readiness-20261114T082526Z.json` (and byte-identical) |
| Repo + official validator (`4b9c010`) | `OK: 7 detection(s)` both |
| `data/` SHA-256 | unchanged |
| Headless `AppTest` (scratch) | both windows, all 16 detections from the list with correct "n of N", every lab view, focus, +10 s, Previous/Next disabled exactly at ends and round-trip, Back, custom interval all views, window switch keeps per-window state, missing data → message — no failures |
| Browser (in-app pane) | list open (incl. last row from a scrolled position → report at top), fleet-timeline click, compact-timeline click, Next, Back (selection retained, "last opened"), dev↔eval from overview and report, focus, two +10 s steps (slider = cursor = inspector), Details, Settings, custom interval; DOM checks at 1920/1366/1024: no overflow, no clipped buttons, no clipped chart titles; console errors: none in the buffer read |

Screenshots: `outputs/polish-screenshots-20261114/` (01 is before the fix; 03–04 predate the final timeline
height trim; late captures were cropped by the pane after a DPI change — geometry verified by DOM measurement).
Not checked: screen reader, keyboard-only timeline, touch, zoom, colour-vision simulation, widths < 1024 px, the
empty-detections state with real data (code path exists; no window produces zero detections).

## Dashboard overhaul — interactive incident report (2026-11-14 ~14:30 UTC)

- Committed on local branch `feat/blue-investigation-workspace` on top of `4d3eaab` (the dark workspace below);
  not pushed, not merged. Changed: `src/dashboard.py` (rewritten), `.streamlit/config.toml` (light theme),
  `README.md`, this file. No change to `src/straightrows/`, tests, data or schema.
- Structure (one level at a time): navy header (window switch, dates, status, Settings) → **Fleet overview**
  (timeline + one-row-per-detection list, register, custom interval, dev labels, About) → **Incident report**
  (Back / Previous / n of N / Next / slim clickable timeline; heading "Suspected <cause> · <tractors>";
  evidence lab | finding; one Details expander with tabs) → **Custom interval** lab.
- Evidence lab views: Guidance, Receiver health, Link & fix, Space / RF, Before / after, Position, All signals
  (custom: Compare tractors instead of Before / after). Default view per cause (display-only mapping);
  equipment fault with dropouts puts min C/N0 first.
- State: stable detection IDs (`class|start|tractors`); per-window keys for view, selection, focus, context,
  aggregation; lab view keyed per detection (resets to the cause default); replay key per detection + context
  (clamped to the interval). Selection validated against the window's detections every run.
- New display-only statistics: per-tractor rule-minute counts (`attribution.tests`, `candidates.flag`);
  per-tractor before/during/after via `evidence._stats`; axis floors for C/N0 (20–50, 0–50 dB-Hz) and
  rule-level lines. Definitions are in the app (About / Details → Display definitions) and README.
- Deferred: automatic playback; hover-synchronised cursor; responsive stacking between ~640 and ~1100 px.

### Verification performed (overhaul content, 2026-11-14 ~14:30 UTC)

| Check | Result |
|---|---|
| `pytest -q tests` | 15 passed |
| `run_pipeline.py` → new `outputs/report-ui-verify-20261114T143021Z/` | byte-identical to `outputs/submission.json` and the readiness backup (SHA-256 `5e62e998…`) |
| Repo validator + official validator (`4b9c010`) | `OK: 7 detection(s)` both |
| `data/` SHA-256 before/after | unchanged |
| Headless `AppTest` (scratch script, not in repo) | both windows; every detection (7 + 9) opened from the list with correct "n of N"; every lab view; focus; +10 s; Next→Previous returns to same report; Back; custom interval with every view; window switch keeps each window's state; missing data folder → message, no exception — no failures |
| Dashboard eval detections == submission | True |
| Browser (in-app pane), 1366×768 and 1920×1080 | fleet list + timeline; timeline click opens report; Next; Before/after; Position + T1 focus; +10 s; Full readout; development window; custom interval. Fixed during review: header button contrast, cramped lab toolbar and replay buttons, overlapping mini-timeline labels, auto-zoomed C/N0 axis exaggerating ~1 dB changes, EF primary channel. Screenshots: `outputs/report-ui-screenshots-20261114/` |

Not checked: screen reader, keyboard-only timeline, touch, zoom, colour-vision simulation, widths below 1366 px,
fresh clone. Screenshots 01–08 predate the C/N0 axis/threshold change (09 shows it); 02 still shows the
overlapping mini-timeline labels fixed immediately afterwards.

## Dashboard redesign — blue investigation workspace (2026-11-14 ~08:45 UTC; superseded by the overhaul above)

- Committed on local branch `feat/blue-investigation-workspace` (from `main` @ `6c2bb1b`; not pushed, not
  merged; `git log --oneline -1` on that branch shows the hash). Changed:
  `src/dashboard.py` (layout + interactions), `.streamlit/config.toml` (dark blue theme), `README.md`
  (dashboard section, limitations), this file. No change to `src/straightrows/`, tests, data or schema.
  Previous dashboard copy (for reference only): commit `6c2bb1b`.
- Implemented: compact header (window toggle, UTC bounds, settings popover); bounded keyed panels (CSS on
  `st-key-panel-*` classes only); fleet ribbon with click selection via `on_select` callback + selector
  fallback sharing ONE session-state key per window; selected detection outlined + span shaded; incident
  summary band; wide evidence panel (context strip, tall primary chart, two supporting charts, all
  container-width, shared UTC axis, detection band, replay cursor); narrow decision panel (action, ≤3 measured
  observations, main uncertainty; details in expanders); manual replay (1 s slider + ±10 s/±1 min/Onset
  buttons, keyed per detection + context so it resets on change); replay readout (exact-second 1 Hz samples,
  tolerance 0, "no sample" otherwise; minute working flag; S4/Kp in force with publication age; episode-level
  membership); tractor focus (dims, never hides); before/during/after table (evidence._stats; "after" is a
  display-only mirror of the 30-min working baseline); reported-position plot (equal scale, local metres,
  gap-aware 10 s trails, cursor markers, spoofing caveat).
- Deferred: play/pause animation; hover-synchronised cursor across charts.
- Removed: the "Tractors on charts" multiselect (replaced by focus, which keeps comparison context).

### Verification performed (redesign content)

| Check | Result |
|---|---|
| `pytest -q tests` | 15 passed |
| `run_pipeline.py` → new `outputs/redesign-verify-20261114T084243Z/` vs `outputs/submission.json` | byte-identical; validator `OK: 7 detection(s)` |
| `data/` SHA-256 before/after | unchanged |
| Headless `AppTest` (scratch script, not in repo): every detection in both windows (7 eval + 9 dev), focus T2, +10 s, custom interval, window switch | no exceptions/errors |
| Dashboard eval detections == `outputs/submission.json` detections | True (7) |
| Missing data folder | explicit error message, no exception |
| Browser (in-app pane) at 1366×768 and 1920×1080 | ribbon click → selector/summary/decision/replay synced; selector → ribbon highlight synced; window switch resets safely; focus; ±10 s / +1 min steps; custom interval; readout with concurrent membership (#1 EF #2 SPF); position plot. Fixed during review: clipped header, working lanes inheriting cause colours, truncated lane label, wrapped readout labels, "13.0"/"1e+1" axis labels. Screenshots: `outputs/redesign-screenshots-20261114/` |

Not checked: screen reader, keyboard-only navigation of the ribbon, touch, browser zoom, colour-vision
simulation, widths below 1366 px, fresh clone. One of two rapid "+1 min" clicks was not applied in the
browser (possibly pressed during a rerun); single presses worked.

## Revised priority order (2026-11-14)

1. Submission (user actions above) — deadline 22:00 UTC.
2. **Dashboard**: interactive incident report implemented and committed on local branch `feat/blue-investigation-workspace`
   (see "Dashboard overhaul"). Next: user review; push/merge only on explicit authorization; accessibility
   checks; optional automatic playback (no blocking loops).
3. Multipath detection — **deferred**; needs separate user authorization; not part of the redesign.
4. Loader robustness (unchanged from below).

## Repository state (as of 02:20 CST)

- Branch `main`, HEAD `00f52cd` ("feat: redesign dashboard as FIELD SIGNAL incident investigation").
- `origin/main` = `00f52cd` (pushed). Remote: `https://github.com/reno-ogden/straight-rows` (still **private**).
- Working tree: clean except untracked `outputs/` (generated files and backups, deliberately not committed):
  `submission.json`, `submission.before-verify-20261114T065529Z.json`,
  `submission.before-repro-20261114T070249Z.json`, `dev_episode_stats.csv`, `dev_plots/`,
  `verify-repro-20261114T070508Z/`, `verify-review-20261114T072133Z/`.
- This handoff (`CLAUDE.md` additions, `docs/HANDOFF.md`) is committed in the docs-only commit directly on top
  of `00f52cd`; run `git log --oneline -3` to see its hash. It changes no code.
- Last verified working checkpoint: `00f52cd` (tests and dashboard checks below were run on exactly this
  content immediately before committing). Analysis code is unchanged since `ec107b8`.

## Dashboard

- Entry point `src/dashboard.py`; theme and local-only settings in `.streamlit/config.toml`.
- Launch (Windows CMD, repo root): `.venv\Scripts\python.exe -m streamlit run src\dashboard.py` → http://localhost:8501
- Reads pipeline output only: `io.load`, `pipeline.detect`, `export.to_submission`,
  `features.minute_features` + `candidates.flag`, `evidence._stats`. No detector logic of its own.

## Completed checks and the code state they apply to

| Check | Result | Code state |
|---|---|---|
| `python -m pytest -q tests` | 15 passed (3 dataset + 12 synthetic working-state) | `00f52cd` content |
| `python src/evaluate_dev.py --data data --sweep` | Equivalence IDENTICAL (dev + eval); default 27.29/40, macro-F1 0.693, onset 0.664, 8/12, 1 FP — **in-sample** | analysis at `ec107b8` (unchanged through `00f52cd`) |
| `run_pipeline.py` into a new folder vs `outputs/submission.json` | byte-identical, 7 detections | `ec107b8` analysis |
| `validate_submission.py` (repo copy and official copy at `4b9c010`) | `OK: 7 detection(s)` | same |
| Official PR-check privacy function (offline) | no errors, no warnings | same |
| Data files vs release zip SHA-256 | unchanged | throughout |
| Dashboard: browser at 1366×768 and 1920×1080, headless `AppTest` over all 7 eval incidents + dev fault/spoof/link cases, empty/missing-data states | pass; details in `docs/pipeline.md` (FIELD SIGNAL worklog) | `00f52cd` content |
| Dashboard eval detections vs `outputs/submission.json` | identical | `00f52cd` content |

Not run: full official PR check (needs a PR), fresh-clone reproduction, clean `pip install -r requirements.txt`,
screen-reader/touch/zoom/colour-vision checks of the dashboard.

## Known issues

- **Multipath is not detected** (macro-F1 capped at 0.8; dev TRN-11/12 missed).
- Confidence is a fixed 0.5 (not calibrated).
- Jamming and spoofing during a storm are missed (dev TRN-05, TRN-08); one dev FP: 05-05 22:00 spoofing fragment.
- Same-cause merge across tractors (within 5 min) can overstate affected tractors.
- `straightrows.io.load` raises `KeyError: 'ts'` if the RFI or advisory feed is an empty list (real data unaffected).
- SDA/RFI timestamp semantics undocumented (interval start vs end; RFI observation vs report time).
- Starter notebook in the official repo still says "hour 22"; current official sources say hour 24 (4 pm CT).
- Git author email on all commits is a personal address; it becomes public when the repo is made public
  (user decision; history rewrite would need explicit approval).
- Guide PDF is tracked in `docs/`; redistribution permission is not established (user decision).
- Dashboard (redesign): no play/pause; position plot fixed 330 px square; accessibility checks not done
  (see redesign section). The earlier fixed-width / non-equal-aspect issues are resolved on the redesign branch.

## FIELD SIGNAL direction (implemented in `00f52cd`; visual styling superseded 2026-11-14 — see Revised priority order)

Editorial scientific-instrument style: ivory `#f5f1e6`, charcoal `#23221e`, green accent `#2e6b4e`, fine rules,
serif headings, monospace timestamps; no gradients/glow/gauges/emoji/oversized cards/generated-ID CSS.
One incident at a time: compact header with subordinate status (in-sample vs not measured); fleet incident
ribbon (T1/T2/T3 lanes, cause colour + text code, concurrent causes in sub-rows); plain-language incident
heading labelled "pipeline attribution, not confirmed truth"; evidence charts left (≤3 cause-specific primary
channels, all signals in an expander) and decision brief right (observed measurements, pipeline
interpretation, action, uncertainty); exact submission evidence in an expander. No map or animation yet.

## Must remain unchanged

- Detection, attribution, thresholds, assembly, working-state gate, confidence value, evidence text, and
  `submission.json` content (evaluation output byte-identical to `outputs/submission.json` at 7 detections).
- `STARTER` config reproducing `src/baseline.py`; existing tests passing.
- Raw `data/`; submission schema (only `participant.github_handle`, optional `display_name`).
- Dashboard reuse of `straightrows`; labels shown separately from predictions; in-sample wording.

## Next three tasks (02:20 CST list; order superseded by "Revised priority order" above)

1. **Submission readiness (deadline today 16:00 CST / 22:00 UTC).**
   Regenerate into a new folder, back up first, validate, then — only with explicit user authorization at each
   step — the user makes the repo public, forks the official repo, adds `submissions/reno-ogden/submission.json`,
   opens one PR to `main`.
   *Accept:* validator `OK`; Submission check green on the PR; PR opened and last changed before 22:00 UTC;
   no email/student ID in the file.
2. **Multipath detector** (new cause test in `straightrows`, short headland dips in min C/N0, recurring every
   ~5.8 min; see `docs/dev_findings.md`).
   *Accept:* synthetic tests for dip/no-dip and recurrence; dev MULTIPATH F1 > 0 with no regression in other
   classes (official scorer); evaluation output change reported as counts only; `STARTER` equivalence still
   IDENTICAL; README/docs updated.
3. **Loader robustness** (`io.load` handles empty RFI/advisory feeds; assert no duplicate (tractor, ts),
   no NaN in required columns, known tractor IDs).
   *Accept:* new synthetic tests pass (empty feeds load; bad data raises a clear error); real-data outputs
   byte-identical; all existing tests pass.

## References

- Event site: https://bluestaq.github.io/ndsu-hackathon-submissions/ (submit page: `submit.html`)
- Official repo: https://github.com/Bluestaq/ndsu-hackathon-submissions (main at `4b9c010` when last checked);
  dataset release `dataset-v1.4`.
- Local: `README.md`, `CLAUDE.md`, `docs/pipeline.md` (method, results, worklogs), `docs/dev_findings.md`,
  `docs/preflight.md`, `THIRD_PARTY_NOTICES.md`, official guide v1.4 `docs/Bluestaq_NDSU_Straight_Rows_Hackathon_Official.pdf`.

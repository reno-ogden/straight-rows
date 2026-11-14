# Handoff — Straight Rows

## Current state — 2026-11-14 12:01 CST / 18:01 UTC

**Read this section first; dated sections below are history and may describe older branches, counts, or bugs.**
The deadline is **16:00 CST / 22:00 UTC today**; target a successful submission by **15:00 CST / 21:00 UTC**.
The fleet-overview → incident-report dashboard design is approved. See [CODEX_REVIEW.md](CODEX_REVIEW.md)
for change ownership, exact verification scope, independent detection traces, and open issues.

- **Git:** branch `feat/blue-investigation-workspace`, full committed HEAD
  `c2c342c3b1245968de4fd15b6f5e7bfc473f6cd7`; no staged files. Modified, uncommitted:
  `.gitignore`, `README.md`, `docs/HANDOFF.md`, `docs/pipeline.md`, `docs/preflight.md`,
  `src/dashboard.py`, `src/straightrows/config.py`, `src/straightrows/io.py`.
  Untracked: `docs/DEMO.md`, `tests/test_input_validation.py`; this handoff also creates untracked
  `docs/CODEX_REVIEW.md` and modifies `CLAUDE.md` to correct a durable download instruction.
  `outputs/` is ignored and contains the preserved submission, backups, and review artifacts.
  Local `origin/main` points to the same commit as HEAD; local `main` is seven commits behind that ref.
  No network fetch or push was performed in this handoff: current remote synchronization is **not verified**.
- **Pipeline:** default causes are `SPACE_WEATHER`, `JAMMING`, `SPOOFING`, `EQUIPMENT_FAULT`.
  Suspected `MULTIPATH` exists as an opt-in 1 Hz detector, **off** in the dashboard and submission.
  Per-tractor 1-minute mean speed >1.0 m/s defines working (at least 14 moving seconds with this dataset).
  Same-tractor/same-cause gaps ≤180 s bridge before the 180 s minimum; same-cause tractor runs merge
  within 300 s. Different causes remain separate. Confidence is a fixed heuristic **0.5**, not a probability.
  S4/Kp are backward-as-of aligned with no staleness bound; RFI is evidence context, not a rule input.
  RFI observation versus report time and SDA interval timestamp meaning are undocumented. Cross-track error
  is a separate guidance-monitor channel; reported GNSS lat/lon is not ground truth.
- **Known limitations:** development TRN-05 jamming and TRN-08 spoofing inside a storm are missed; the
  six-minute spoofing tail after the storm is the one development scorer false positive. Default misses both
  labeled multipath episodes. Same-cause cross-tractor merging can overstate the affected set. Development
  scores are in-sample; evaluation accuracy is unknown.
- **Verified on the current code state:** `.venv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider tests`
  → **41 passed**; `src\validate_submission.py outputs\submission.json` → `OK: 7 detection(s)`.
  `outputs\submission.json` SHA-256 is
  `27ED40C569210563D25A1219D7713F6E4173BAFCE469E23BED12D66D6260CCB6`.
  A unique regeneration after the input changes, `outputs/approved-robustness-20261114T174352550Z/submission.json`,
  has the same SHA-256. Later edits affected only display and documentation, so regeneration is not required
  by an analytical change; do not replace the designated file silently. Schema validation does not prove
  analytical accuracy. Full procedure and limits: [CODEX_REVIEW.md](CODEX_REVIEW.md).
- **Dashboard:** from the repository root in Windows CMD run
  `.venv\Scripts\python.exe -m streamlit run src\dashboard.py`, then open `http://localhost:8501`.
  Uses the same pipeline output, with cached visualization. The latest tooltip fix was checked in live
  headless Edge at 1366×768; accessibility and zoom remain untested.
- **Sync update — 2026-11-14 ~19:10 UTC (Claude, after Codex):** live `git ls-remote` showed
  `origin/main` = `c2c342c` (pushed earlier the same day); the solution repo returned 404 to an
  unauthenticated API query (private); no `reno-ogden` fork, PR, or `submissions/reno-ogden` existed.
  Official repo still `4b9c010`; its validator/PR-check/workflow unchanged. The final working tree
  regenerated `outputs/submission.json` byte-identically (closing the gap that `config.py` was edited after
  the recorded 17:43 regeneration); 41 tests passed. **User decisions:** (1) the personal author email in
  Git history is **accepted** for publication — no history rewrite; (2) the guide PDF is **removed from the
  tree** (untracked, ignored, local copy kept; earlier commits still contain it; the tracked copy differed
  from the organizers' current published copy). Codex's reviewed work was committed as `5a52954`.
- **Submission readiness:** no visibility change, fork, PR, or green live Submission check has been made or
  verified. Earlier offline PR-check simulation reported a private-repository blocker; do not treat it as a
  current remote status check.
  Committing, pushing, changing visibility, forking, opening a PR, and submitting each require the user's
  explicit authorization. The official fork PR must change exactly
  `submissions/reno-ogden/submission.json` and pass its Submission check before lock.

**Next three tasks:** (1) ~~User decides public-repository history/PDF exposure~~ — done 19:10 UTC (email
accepted; PDF removed from tree); (2) with authorization, make a focused solution-repo commit,
verify the remote public state and push/merge the reviewed branch (about 15–30 min; accept only if code,
docs, demo, and chosen JSON agree); (3) with authorization, create the official fork's one-file PR and
confirm a green Submission check by 21:00 UTC (about 20–40 min, allow time for failures).
Do not reopen the dashboard design, enable multipath, retune on unlabeled evaluation, or overwrite
`outputs/submission.json` as part of this handoff.

## Approved independent-review fixes — 2026-11-14 ~17:49 UTC (milestone record)

The working branch is `feat/blue-investigation-workspace` at committed HEAD `c2c342c`. These fixes are
uncommitted. Preserve the pre-existing README label-use edit, `docs/DEMO.md`, and all `outputs/` files;
no existing result was replaced. No detector threshold, attribution rule, interval assembly rule,
raw challenge file, or intended `outputs/submission.json` was changed.

1. **Correctness/presentation claim:** `docs/DEMO.md` now says RFI-001 is *timestamped* 15 minutes after
   onset, not that its report arrived then. The feed does not document whether `ts` is observation or
   arrival time. The space-weather line now describes what the rule attributes rather than proving a
   physical alternative impossible. `.gitignore` now ignores `outputs/`, as the README says they are local;
   it prevents the generated review files and backups from being included by a broad stage. No analytical
   or UI code changed in this milestone.
2. **Input robustness:** `io.load` now rejects missing/null required telemetry, duplicate tractor-seconds,
   unexpected IDs, and empty, missing-column, null, or duplicate-timestamp Kp/Dst/S4. Empty optional RFI/advisory feeds load.
   `Config` rejects invalid numeric thresholds/durations. Missing sample timestamps are still allowed;
   the existing gap behavior remains. Eight new focused tests passed; the full suite was **41 passed**
   with the released data. Regeneration to
   `outputs/approved-robustness-20261114T174352550Z/submission.json` wrote 7 detections, passed the
   official-identical local validator, and was byte-identical to preserved `outputs/submission.json`
   (SHA-256 `27ed40c5…60ccb6`). `evaluate_dev.py` after this code change reproduced the prior table:
   default 27.29/40, macro-F1 0.693, onset 0.664, 8/12 correct, 1 FP; STARTER equivalence identical on
   both windows. The nine development detections, including evidence, had the same sorted-JSON SHA-256
   (`c39806ce…340fb1e6fa1`) as the independent clean archive of committed HEAD. These checks apply to the
   loader/config changes before the later display-only edits.
   A separate current-source copy without data (`outputs/no-data-check-20261114T175255054Z/`) produced
   **38 passed, 3 skipped** with explicit dataset-skip reasons; `run_pipeline.py` exited 1 with
   "Dataset not found" and wrote no output.
3. **Dashboard and documentation:** chart overlays now suppress their automatic tooltip, which previously
   showed a wrong end date. In live headless Edge at 1366×768, the shaded-band hover had no tooltip,
   a data line still showed tractor/UTC bin/value, +10 s advanced replay, and Back returned to fleet.
   The stable report had no horizontal overflow. `README.md`, `docs/pipeline.md`, `docs/preflight.md`,
   and the dashboard methodology now state the current test count, input behavior, multipath status,
   and in-sample limits. These edits do not change analytical output. Review screenshot:
   `outputs/approved-tooltip-stable-20261114T1745Z.png`.
4. **Optional analytical enhancement:** none approved or made. Multipath stays opt-in and off in the
   submission; storm-relative rules and confidence calibration remain deferred.

**Still required before submission:** decide whether the existing non-`noreply` author email in Git
history is acceptable in a public repository; explicitly select final files for the solution-repo
commit (avoid adding all of `outputs/`); make that repo public; fork the official repository; add
only `submissions/reno-ogden/submission.json` to one PR; confirm the Submission check passes before
22:00 UTC, preferably by the 21:00 UTC target. No commit, push, visibility change, fork, or PR was made here.

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

## Reproduction review (2026-11-14 ~16:25 UTC; committed locally, not pushed)

Clean copy: `git clone` of `90473a7` into a temporary scratch folder, `py -3.11 -m venv .venv`, `pip install -r
requirements.txt` from PyPI (TLS verification on) → success, `pip check` clean. In that copy:
- Without `data\`: `pytest` → `30 passed, 3 skipped` (exit 0) — looks like success but is not an analysis run;
  `run_pipeline.py` / `evaluate_dev.py` raised `FileNotFoundError` (exit 1, nothing written).
- `scripts\get_data.py` (direct download, no `--zip`) → `Extracted 6 data files`, checksum verified; the six files
  are byte-identical to the working `data\` (this also verifies the working dataset against the release).
- With data: `pytest -q -rs tests` 33 passed; `run_pipeline.py` → byte-identical to working `outputs\submission.json`
  (`27ed40c5…`) and to a second run; repo + official validator OK; `evaluate_dev.py` reproduced the README table;
  `dev_episode_stats.py` and `plot_dev_episodes.py` ran (12 plots); dashboard loaded headlessly (AppTest).
- Not tested: `--zip` fallback (zip not on disk; used earlier), another machine/OS/Python, offline install,
  dashboard in a browser from the clean copy.

Fixes: `run_pipeline.py` and `evaluate_dev.py` now stop with `Dataset not found …` (exit 1, nothing written)
instead of a traceback; output with data unchanged (byte-identical). README: install now marked tested (clean
copy), data provenance/synthetic nature and label use, direct download documented with both observed outcomes,
`--zip` fallback status, network/offline table, `pytest -rs` and the skipped-tests warning, official validator
identity, clean-copy results, stale "evidence times without a date" limitation replaced by the retrospective note.
README now has a short "AI assistance" section (user decision, 2026-11-14): Claude via Claude Code, under the
author's direction; commits carry the co-author trailer; no AI or online API at analysis time.

## Evidence accuracy review (2026-11-14 ~16:10 UTC; committed locally, not pushed)

Evidence wording only; detector behaviour unchanged. Changed: `src/straightrows/evidence.py`, `src/dashboard.py`
(one methodology bullet + scoring caption), `README.md`, `docs/pipeline.md` ("Evidence accuracy review" lists
every correction), this file.

- Regenerated to `outputs/evidence-review-20261114T160749Z/submission.json`: official + repo validator OK;
  start, end, tractors, class, action, confidence identical for all 7 detections vs the reference; only
  `evidence` strings differ (dated times, "not in this detection", guidance-monitor wording, SDA/RFI timestamp
  caveats, reported-position wording, softened jamming sentence, absence-of-RFI caveat, new per-tractor
  rule-minute/bridging/merge line).
- Checks: `pytest -q tests` 33 passed; dashboard headless suites pass (they now report "differs from
  `outputs/submission.json`" only because that file holds the old wording); dashboard rule-minute counts = exported
  counts for 16/16 detections; multipath option still leaves non-multipath entries identical (dev and eval).
- **Submission file replaced (user approved, 2026-11-14 ~16:15 UTC).** Old file backed up to
  `outputs/submission.before-evidence-wording-20261114T161516Z.json` (SHA-256 `5e62e998…e06cc`, = the earlier
  references). `outputs/submission.json` is now the corrected wording (SHA-256 `27ed40c5…60ccb6`): official and
  repo validator OK; offline official PR-check logic: no privacy findings, only "repository not public yet" while
  private; same 7 detections (boundaries, tractors, class, action, confidence identical); current code regenerates
  it byte-identically (`outputs/replace-check-20261114T161530Z/`). **This is the file to submit**, and the new
  reference for future comparisons.

## Suspected multipath — opt-in detector (2026-11-14 ~16:00 UTC; committed locally, not pushed)

**Decision (user, 2026-11-14): keep as opt-in, default off.** The submission keeps the default pipeline
(multipath off); `detect_multipath=True` remains available for analysis and development scoring.

On `feat/blue-investigation-workspace` (= `origin/main` @ `a2df1e3`). New `src/straightrows/multipath.py`,
`tests/test_multipath.py`; changed `config.py` (seven `mp_*`/`detect_multipath` fields), `pipeline.py` (append
multipath runs when enabled), `export.py` (multipath evidence; concurrency lists ignore multipath reports),
`evaluate_dev.py` (one extra variant), `README.md`, `docs/pipeline.md`, this file. No other rule, threshold or
assembly parameter changed. **Default is off**, so `submission.json` and the dashboard are unchanged.

- Rule, parameters, representation, results and inspection: `docs/pipeline.md` → "Suspected multipath".
- Checks run: `pytest -q tests/test_multipath.py` 18 passed (mutation check: weakening drop, mean tolerance,
  join, min length and max length each makes a test fail); full suite 33 passed; `evaluate_dev.py`: STARTER
  equivalence IDENTICAL on both windows; default 27.29 / macro-F1 0.693 / onset 0.664 / 8/12 / 1 FP →
  with multipath 34.79 / 0.893 / 0.830 / 10/12 / 1 FP (in-sample); other classes' P/R/F1 identical;
  non-multipath dev detections and evidence byte-identical. Default regenerated to
  `outputs/multipath-default-off-20261114T154519Z/` → byte-identical to the reference submission.
  Evaluation window with multipath on (counts/validity only): 490 detections, validator OK. Dashboard headless
  suite (default config): no failures.
- Not done: dashboard support for hundreds of short detections; any change to `submission.json`.
- To enable: set `detect_multipath: bool = True` in `config.py` (then regenerate, validate, and expect ~490
  evaluation detections — close to the 500 limit).

## Milestone verification (2026-11-14 ~15:30 UTC) — checkpoint `2e97e47`

Verification only; no code or data changed. Branch `feat/blue-investigation-workspace` @ `2e97e47`, clean tree.
Checkpoint publication: this section is committed on top of `2e97e47` and fast-forward pushed (no force) to
`origin/main` on user authorization; "not pushed" notes in the dated sections below describe their own time.
Confirm with `git log --oneline origin/main -5`.
`git diff main..HEAD` touches only `src/dashboard.py`, `.streamlit/config.toml`, `README.md`, `docs/HANDOFF.md`
(nothing under `src/straightrows`, `tests`, `tools`, `scripts`, `run_pipeline.py`, `validate_submission.py`).

| # | Command / check (Windows CMD equivalents; run from repo root with `.venv`) | Result |
|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pytest tests -q -rA` (+ `--collect-only -q`) | 15 collected · 15 passed · 0 failed · 0 skipped |
| 2 | `.venv\Scripts\python.exe src\run_pipeline.py --data data --output outputs\milestone-verify-20261114T152824Z\submission.json --github-handle reno-ogden --repo-url https://github.com/reno-ogden/straight-rows` (folder did not exist) | `Wrote 7 detections`, exit 0 |
| 3 | Official validator, `starter/submission/validate_submission.py` at official `main` `4b9c010` (re-downloaded; SHA-256 `5a68d949…`, identical to the copy verified earlier) | `OK: 7 detection(s)`, exit 0; repo copy also OK |
| 4 | Compare with pre-redesign reference `outputs/submission.before-readiness-20261114T082526Z.json` (backed up at `6c2bb1b`) | byte-equal (SHA-256 `5e62e998…e06cc`); parsed-equal; field-by-field: participant, repository_url, 7 detections × {start, end, tractors, class, action, confidence, evidence} — no differences (35 evidence strings) |
| 5 | Headless harness (scratch `milestone_check.py`): rendered register vs `to_submission(detect(...))` per window; each report's heading, UTC interval, duration, tractors, action text, class/action identifiers, fixed-confidence statement, exported evidence verbatim | all 7 evaluation + 9 development detections match |
| 6 | Same harness: tractor focus T1/T2/T3/All; every lab view; +10 s = 10 s; slider = cursor label; inspector XTE = raw 1 Hz sample for T1–T3; Next opens next detection and resets cursor to its onset; methodology text on fleet (About) and report (Details); dev scoring button → 27.29 / 0.693 / 0.664 / 1 FP with "In-sample" caption | pass |
| 6 | Missing input / empty selection: nonexistent folder; folder missing `sda/rfi_reports.json` (scratch copy); zero detections (scratch copy with nominal telemetry); invalid stored selection; forced report view with zero detections | named error, no exception; named missing file; "no detections" message, custom interval works; falls back to #1; falls back to fleet |
| 7 | Instrumented counts (wrapped `io.load`, `pipeline.detect`, `st.set_page_config`) | 1 script run per interaction (open, +10 s, back; 2 for two window switches); raw data loaded once, 0 reloads during navigation; `detect` called 2× total (one per window, then cached) |
| — | Browser (in-app pane, 1366×768, live server): open #4 from list, T1 focus, +10 s, Development, back to Evaluation | heading/interval/action/cursor correct; report at top; no horizontal overflow; inspector T1 +0.952 m at 16:35:10 (= full readout); console errors: none |

**Findings.**
- *Nonblocking:* after switching windows and back, the report and selection are restored, but tractor focus,
  replay time and the evidence-lab view return to defaults (All tractors, onset, cause default). Cause: Streamlit
  removes state of widgets not rendered in a run; selection/view use plain session keys and survive. Safe default,
  not stale. Fix if wanted: mirror these values in non-widget session keys.
- *Nonblocking:* Vega's automatic screen-reader descriptions of time bars (e.g. timeline "end: May 05, 2026")
  use the browser's local time zone; visible axes and all tooltips are UTC strings.
- *Nonblocking (tooling):* in-app pane screenshots of report pages were cropped/zoomed after a DPI change;
  DOM metrics (visual viewport scale 1, width 1366, zoom 1) confirm the page itself is correct.
- No blockers found for the dashboard. Submission steps (repo public, fork, PR before 22:00 UTC) remain the user's.

Checkpoint files (tracked, already committed in `2e97e47`): `src/dashboard.py`, `.streamlit/config.toml`,
`README.md`, `docs/HANDOFF.md`. Untracked evidence (not committed by design): `outputs/milestone-verify-20261114T152824Z/submission.json`,
`outputs/polish-screenshots-20261114/`, `outputs/report-ui-screenshots-20261114/`.

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
| Headless `AppTest` (scratch) | both windows, all 16 detections from the list with correct "n of N", every lab view, focus, +10 s, Previous/Next disabled exactly at ends and round-trip, Back, custom interval all views, window switch keeps per-window selection and view (see milestone note: focus, replay time and lab view reset), missing data → message — no failures |
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
| Headless `AppTest` (scratch script, not in repo) | both windows; every detection (7 + 9) opened from the list with correct "n of N"; every lab view; focus; +10 s; Next→Previous returns to same report; Back; custom interval with every view; window switch keeps each window's selection and view (focus/replay/lab view reset — see milestone verification); missing data folder → message, no exception — no failures |
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
3. Multipath detection — implemented as an **opt-in** detector (`Config.detect_multipath`, default off),
   committed locally (not pushed); user decision: keep opt-in, not enabled for the submission (see "Suspected
   multipath" at the top).
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

- **Multipath is off in the default submission** (dev TRN-11/12 missed); an opt-in detector exists.
- Confidence is a fixed 0.5 (not calibrated).
- Jamming and spoofing during a storm are missed (dev TRN-05, TRN-08); one dev FP: 05-05 22:00 spoofing fragment.
- Same-cause merge across tractors (within 5 min) can overstate affected tractors.
- Empty RFI/advisory feeds now load; required feeds, null values, and duplicate tractor-seconds are checked
  (see the current-state review section at the top).
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
3. **Loader robustness — completed in the current-state review section** (`io.load` handles empty RFI/advisory feeds; assert no duplicate (tractor, ts),
   no NaN in required columns, known tractor IDs).
   *Accept:* new synthetic tests pass (empty feeds load; bad data raises a clear error); real-data outputs
   byte-identical; all existing tests pass.

## References

- Event site: https://bluestaq.github.io/ndsu-hackathon-submissions/ (submit page: `submit.html`)
- Official repo: https://github.com/Bluestaq/ndsu-hackathon-submissions (main at `4b9c010` when last checked);
  dataset release `dataset-v1.4`.
- Local: `README.md`, `CLAUDE.md`, `docs/pipeline.md` (method, results, worklogs), `docs/dev_findings.md`,
  `docs/preflight.md`, `THIRD_PARTY_NOTICES.md`; official guide: organizers' copy at
  `starter/docs/Bluestaq_NDSU_Straight_Rows_Hackathon_Official.pdf` in the official repo (no longer tracked here).

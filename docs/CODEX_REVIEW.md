# Independent review and Codex handoff — 2026-11-14

Snapshot: **12:01 CST / 18:01 UTC**, Saturday 14 November 2026. Deadline **16:00 CST / 22:00 UTC**;
target successful submission **15:00 CST / 21:00 UTC**. This record was made from `CLAUDE.md`,
`docs/HANDOFF.md`, `README.md`, `docs/pipeline.md`, `docs/dev_findings.md`, `docs/preflight.md`,
`docs/DEMO.md`, Git, source diffs, dataset, and local artifacts. Historical details remain in
[HANDOFF.md](HANDOFF.md) and the [pipeline worklog](pipeline.md). It does not assert that an unpublished
remote or PR was checked today.

## Git and file ownership

- Current branch `feat/blue-investigation-workspace`; full HEAD
  `c2c342c3b1245968de4fd15b6f5e7bfc473f6cd7` (`docs: document clean-copy reproduction, data provenance and AI assistance`).
  Recent relevant commits: `90473a7` (evidence wording), `612170c` (opt-in multipath),
  `a2df1e3` (dashboard verification), `2e97e47` (header/navigation polish), and `6155945`
  (fleet/report dashboard). No commit was made in this handoff.
- At snapshot: staged **none**. Uncommitted modified `.gitignore`, `README.md`, `CLAUDE.md`,
  `docs/HANDOFF.md`, `docs/pipeline.md`, `docs/preflight.md`, `src/dashboard.py`,
  `src/straightrows/config.py`, `src/straightrows/io.py`.
  Untracked `docs/DEMO.md`, `docs/CODEX_REVIEW.md`, `tests/test_input_validation.py`.
  `outputs/` is ignored and is local only. Check `git status --short --branch` again before staging.
- The current branch has no shown upstream. Local `origin/main` points to HEAD; local `main` is seven
  commits behind that local remote-tracking ref. This is **local-ref evidence only**, not a fresh fetch.
  Current GitHub visibility, fork and PR state were not queried. The older handoff's private-repository
  result and offline PR-check simulation may be stale.
- Already present before Codex's independent review: the committed analysis pipeline, four-cause default,
  opt-in multipath, dashboard design, evidence wording and `outputs/submission.json`. A seven-line README
  label-use clarification was already uncommitted; `docs/DEMO.md` and `outputs/` already existed locally.
  Attribution for any other pre-existing uncommitted material is uncertain.

## Codex changes in the uncommitted tree

| Milestone / location | Finding and change | Effect / status |
|---|---|---|
| Claim accuracy: `docs/DEMO.md` | RFI-001 is **timestamped** 15 min after onset; feed does not establish report arrival. Storm explanation now describes the implemented rule rather than excluding a physical alternative. | Documentation only; complete. The demo remains untracked. |
| Output hygiene: `.gitignore` | Ignore generated `outputs/` to match README and avoid accidental staging of backups/review artifacts. | Repository configuration only; existing files intact. Verify explicit staging; the intended JSON must be copied to the official fork. |
| Input integrity: `src/straightrows/io.py::load`, `::_feed` | Reject missing/null required telemetry columns, duplicate `(tractor_id, ts)`, unexpected tractor IDs, and empty/missing/null/duplicate-time required Kp/Dst/S4. Accept empty optional RFI/advisory lists as UTC timestamped tables. | Malformed-input behavior changes; released-data detection output unchanged. No schema or data migration. Continuous 1 Hz is not enforced; direct calls to `detect` bypass `load` checks. Complete within scope. |
| Configuration: `src/straightrows/config.py::Config.__post_init__` | Reject nonnumeric/nonfinite/out-of-range thresholds and durations, including invalid multipath min/max. | Invalid configs now fail early. Defaults, rules, and valid-config output unchanged. Complete. |
| Focused tests: `tests/test_input_validation.py` | Eight cases: empty optional feeds, conflicting tractor-second, null telemetry, empty Kp, four invalid configs. | Test-only; complete, untracked. Tests do not cover every malformed numeric field or all missing-file cases. |
| Chart truth: `src/dashboard.py::overlays` | Disable implicit tooltip on shaded interval/edge/cursor marks; implicit band tooltip previously displayed an incorrect end date. Data-line tooltip remains. | Dashboard only; no detection change; complete. |
| Method text: `src/dashboard.py::methodology_md`, `README.md`, `docs/pipeline.md`, `docs/preflight.md`, `docs/HANDOFF.md` | Clarify opt-in multipath, current 41/38+3 test counts, input validation, in-sample score limits, superseded older observations. | Documentation/display only; complete. |
| Durable instruction: `CLAUDE.md` in this handoff | Correct stale assertion that direct data download always fails TLS: a later checksum-verified clean-copy download succeeded; local archive remains fallback. | Instruction only; no runtime effect. |

No detector threshold, attribution rule, episode assembly rule, default multipath flag, dependency, raw data,
or designated submission file changed in these Codex milestones. Do not bundle an analytical enhancement
with the dashboard fix. If another agent edits the pipeline, rerun analytical verification and regenerate
to a **new** folder before deciding what to submit.

## Current analytical implementation and limitations

`io.load` normalizes times to aware UTC; `features.minute_features` computes per-tractor minute means of
C/N0, guidance-monitor cross-track error and speed, min C/N0, and RTK-link fraction. It attaches latest
Kp/S4 at or before the minute (`merge_asof`, no staleness cap). `candidates.flag` defines working as mean
speed >1.0 m/s (with the released 0/4.5 m/s values, at least 14 of 60 seconds). It marks low mean C/N0,
high mean XTE, low link and min-C/N0 dropout; a fleet low-C/N0 count uses all three tractors, including
parked ones. `attribution.tests` separately yields: space weather = low C/N0 on all three + high S4;
jamming = low C/N0 + quiet S4; spoofing = high XTE without low C/N0; equipment fault = link low or
dropout. Default attribution requires the attributed tractor to work. Concurrent different causes are
retained. `assembly.assemble` joins consecutive rule minutes, bridges same tractor/cause gaps ≤180 s
**before** the 180 s minimum, then merges same-cause tractor runs within 300 s. Cross-tractor merge can
overstate membership across the full interval; exported per-tractor rule-minute counts make that visible.

`multipath.py` has a separate 1 Hz short-dip rule but `Config.detect_multipath=False` by default;
the submission and dashboard omit it. Turning it on produces about 490 evaluation-window detections,
near the 500-entry cap, and was deliberately deferred. `export` writes fixed confidence 0.5 for every
episode; it is a heuristic, **not** a calibrated probability. `evidence.py` cites rule counts, measured
signal/guidance/RTK statistics and SDA/RFI context. Dst and RFI do not decide a cause. Kp/S4/Dst
timestamp interval semantics and RFI observation versus arrival time are undocumented. RFI distance uses
**reported** position only. Cross-track error is a separate simulated guidance-monitor channel; reported
GNSS lat/lon is not trusted position truth. The analysis is retrospective on a synthetic dataset.

Known development misses: TRN-05 jamming and TRN-08 spoofing inside high S4/low C/N0 storm minutes;
default TRN-11/12 multipath. A six-minute T3 spoofing tail at 22:00 May 5 is the scorer's one false
positive because time IoU is below the match threshold, although guidance symptoms persist. The
development parameters and score use the same 12 labels. The unlabeled May 6 evaluation day has **unknown
accuracy**. The daily breakdown is a diagnostic, not a held-out test. The default may report broad storms
or tractor membership inaccurately; do not retune to the unlabeled evaluation pattern.

## Verification matrix

All commands below ran from repository root with the project `.venv` unless stated. “Current” means
HEAD above plus the uncommitted loader/config/dashboard/docs/test changes; documentation written in this
handoff does not change runtime. Earlier procedures were performed in the independent-review/fix work
and corroborated here by surviving files and hashes; stdout was not saved as a standalone log.

| Check / exact command or procedure | Result and input/output scope | Code state / applicability |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest -q -rs -p no:cacheprovider tests` | **41 passed**, 0 skipped, on local released `data/`; rerun during this handoff. | Current runtime code. Not an accuracy test. |
| `.venv\Scripts\python.exe src\validate_submission.py outputs\submission.json` | `OK: 7 detection(s); submission is well-formed.` Rerun during this handoff on the exact intended JSON. | Exact file, current local validator. Format only. The local validator had previously been compared with the official copy, apart from line endings; no new official fetch in this handoff. |
| SHA-256 `Get-FileHash -Algorithm SHA256 outputs\submission.json` and same for `outputs\approved-robustness-20261114T174352550Z\submission.json` | Both **27ED40C569210563D25A1219D7713F6E4173BAFCE469E23BED12D66D6260CCB6**. Also same for `outputs/final-submission-20261114T164359Z/submission.json`. Recomputed during handoff. | Exact bytes; no later analytical edit. |
| `.venv\Scripts\python.exe src\run_pipeline.py --data data --output outputs\approved-robustness-20261114T174352550Z\submission.json --github-handle reno-ogden --repo-url https://github.com/reno-ogden/straight-rows`, then local validator and hash comparison | Earlier fix-stage run wrote 7, validated OK, byte-identical to preserved file. New folder, released May 6 input. | HEAD + loader/config, before later display/docs edits. Still applicable analytically; no new regeneration during this handoff. |
| `.venv\Scripts\python.exe src\evaluate_dev.py --data data` | Earlier fix-stage run: default **27.29/40**, macro-F1 **0.693**, onset **0.664**, **8/12** correct, **1 FP**; STARTER baseline equivalent in development and evaluation. Opt-in multipath **34.79**, **0.893**, **0.830**, **10/12**, **1 FP**. | HEAD + loader/config; dashboard/docs did not affect analysis. In-sample development result only. |
| Compare sorted exported development detections including evidence with clean committed `git archive HEAD` copy | Both nine-detection serialized JSON SHA-256 `c39806ce9d87635faa8766b33a9bfecf3491445bdefdd2ffd7ead340fb1e6fa1`. | HEAD + loader/config versus committed HEAD. Result persists after display/docs edits. |
| Current-source no-data copy at `outputs/no-data-check-20261114T175255054Z/`: `pytest -q -rs -p no:cacheprovider tests`; `run_pipeline.py` | **38 passed, 3 skipped** (dataset tests); pipeline exit 1 “Dataset not found,” no output. | Copied current source/tests before final UI/docs edits; still applicable to loader/pipeline behavior. A passing no-data pytest is not full validation. |
| `git diff --check` | Exit 0 during handoff; Git printed line-ending conversion notices, no whitespace errors. | Current uncommitted diff before final documentation write; rerun after writing. |

**Independent review before fixes.** The released synthetic dataset had 777,600 telemetry rows,
259,200 per tractor, complete 1 Hz UTC from May 4 through May 6, with no null telemetry or duplicate
tractor-second. Its six files matched a checksum-verified official release download in the clean
committed archive `outputs/independent-clean-20261114T171742377Z/`. That archive used the existing
project interpreter, not a newly installed independent environment: 33 older tests passed with data,
regeneration was byte-identical, validator OK, and dashboard HTTP returned 200. A prior separate fresh
clone performed a clean Python 3.11 venv and pinned `pip install -r requirements.txt` successfully,
`pip check` clean, direct data download checksum verified, 33 tests passed; see the dated “Reproduction
review” in [HANDOFF.md](HANDOFF.md). Clean installation of the **current uncommitted** code was not run.
No TLS verification was disabled. The local archive fallback was not rerun in the clean clone.

**Raw evidence recomputation, independent of `evidence._stats`.** For development TRN-03 jamming,
the raw 42-minute interval yielded 42/42 rule minutes on each T1/T2/T3, pooled during C/N0 27.59 dB-Hz
versus 45.01 before, min C/N0 −6, max XTE 26.519 m, S4 0.052–0.074; exported/dashboard rounded
values agree. TRN-09 equipment fault T2 had 108/120 qualifying minutes with 12 isolated one-minute gaps
bridged, during C/N0 44.21, min 6.2, max XTE 6.511; its interval 12:00–14:00 reflects bridging.
TRN-06 T2 spoofing overlaps that fault at 13:19–13:54, 35/35 minutes; XTE median 3.515 and normal
mean C/N0 44.19. Its onset is 7 minutes after the 13:12 label. TRN-02 storm on May 5 at 19:00–22:00
yielded 180/180 rule minutes on all three, pooled C/N0 32.42, S4 0.418–0.466, max XTE 26.822.
TRN-08's T3 XTE was >1 m in 21/30 in-storm minutes but C/N0 was low in all 30, explaining the miss;
the 22:00–22:06 spoofing fragment has only 6/36-minute label overlap. Opt-in TRN-12 multipath T1
19:00:35–:52 had min C/N0 16.1, rolling median 28.3, median drop 9.6 dB, and 14/17 seconds qualifying.
These examples verify selected computations and explanations, **not class-level generalization**.

**Synthetic boundary probes before loader fixes.** Unsorted input and a missing second preserved detection;
a missing minute bridged; conflicting duplicate tractor-seconds silently suppressed a detection (now rejected
by `io.load`). Empty window returned `[]`; exactly 38 dB-Hz did not meet the strict low-C/N0 rule;
13 moving seconds did not meet working, 14 did; parked-only signals did not start detections, a short parked
gap bridged; concurrent equipment fault and spoofing stayed separate. Empty S4 and negative configuration
previously failed poorly (now rejected at load/config construction). Direct `detect` on a handcrafted frame
can still bypass `io.load`. These probes and focused tests support malformed-input behavior, not a claim
that arbitrary missing samples or all malformed numeric types are handled.

**Daily diagnostic:** with the fixed default on May 4: 5 labels, 4 detections, 4 correct, 0 FP,
macro-F1 0.6, onset 0.793, diagnostic 26.89. May 5: 7 labels, 5 detections, 4 correct, 1 FP,
macro-F1 0.5, onset 0.571, diagnostic 21.07. Both days had influenced design; daily macro-F1 has
different class presence and neither day is independent holdout validation.

**UI and timing.** The earlier dashboard milestone **reported** checks of all 7 evaluation and 9
development reports, list/timeline navigation, windows, tractor focus, replay, custom interval,
missing-data messages and display/export agreement; see [HANDOFF.md](HANDOFF.md). Those all-report
checks were not repeated in this handoff. Its reported headless timings after cache/spec changes
were about fleet 0.2 s, report revisit 0.6 s, replay 0.66 s (environment-specific). Latest UI-only
tooltip fix was observed in live headless Edge at 1366×768: stable report had no horizontal overflow;
hovering the interval band showed no misleading date; a data-line tooltip still showed T2, UTC minute
and satellites; +10 s moved replay; Back returned to fleet. Screenshot:
`outputs/approved-tooltip-stable-20261114T1745Z.png`. AppTest had zero errors on fleet/open/back and
showed current methodology. Earlier mid-rerun screenshot was transient; use the **stable** screenshot.
Zoom, screen reader, keyboard-only timeline, touch, and another-machine browser were not checked.
Streamlit still briefly fades prior content on rerun; cached chart specs may require server restart
after chart-source edits. Switching windows preserves selected incident but resets focus/replay/lab view.
To reproduce that reset: open a report, select a tractor, move replay forward, switch to the other
window, then switch back; the incident returns with All tractors, cursor at onset, and the default
lab view. This is a known Streamlit session-state limitation, not a changed detection.

## Intended submission and next work

The previously designated artifact is **`outputs/submission.json`**, hash above. It came from the
evidence-wording-corrected default pipeline with multipath off and is still reproduced byte-for-byte
by the loader/config review state. Its exact current bytes passed the local official-identical
validator during this handoff. No later analytical edit requires regeneration. `outputs/` is ignored,
so this JSON is **not** in the solution repo; it must be copied to the official fork at the required path.
`outputs/submission.before-evidence-wording-20261114T161516Z.json` is the older wording backup (SHA-256
`5E62E9984D6CB3DD07227199B52A5D88674D5EC76A9CE9BF92E1FA134C1E06CC`). Other named
`submission.before-*` files and unique generation directories are historical references; do not
overwrite them. The format validator does not establish scoring correctness or PR acceptance.

1. **Publication decision (10–20 min):** user decides whether the existing non-`noreply` Git author
   email in history and tracked official guide PDF are acceptable when making the solution repo public.
   Accept when the user has explicitly chosen a path; do not reveal the email value in handoff prose.
2. **Reviewed solution-repo commit/push (15–30 min, explicit user authorization):** inspect current Git
   status again, stage only intended source/docs/tests, run tests and exact-file validator if code changed,
   commit, verify public visibility and remote state before any PR. No history rewrite, reset or broad
   cleanup without direction.
3. **Official submission (20–40 min, explicit user authorization):** fork the official submissions
   repository, add **only** `submissions/reno-ogden/submission.json` from the designated artifact,
   check its hash after copy, open one PR to `main`, and confirm a green live Submission check before
   **21:00 UTC target / 22:00 UTC lock**. The official workflow may reject a private solution repo.

Read first: `CLAUDE.md`, current section of `docs/HANDOFF.md`, `README.md`, this review, `docs/DEMO.md`,
`docs/pipeline.md`; for implementation: `src/straightrows/{io,config,features,candidates,attribution,assembly,evidence,export,pipeline,multipath}.py`,
`src/dashboard.py::overlays` and `::methodology_md`, `src/run_pipeline.py`, `src/validate_submission.py`,
and `tests/test_input_validation.py`. Preserve the fleet-overview → incident-report design. Deferred:
storm-relative concurrent-cause rules, enabling multipath, probability calibration, large accessibility
or responsive-layout work, and unlabeled evaluation tuning. If publication cannot be authorized, the
usable local state remains the validated seven-detection file plus the uncommitted reviewed changes.

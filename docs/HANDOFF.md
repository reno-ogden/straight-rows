# Handoff — Straight Rows (written 2026-11-14 02:20 CST)

## Repository state

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
- Dashboard: fixed chart widths; position plot not equal-aspect; "parked" bars intentionally faint (1.98:1).

## FIELD SIGNAL direction (agreed, implemented in `00f52cd`)

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

## Next three tasks

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

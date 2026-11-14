\# Straight Rows Hackathon



\## Goal

Build a reproducible local system that detects degraded tractor guidance,

attributes causes using farm telemetry and SDA context, and recommends

actions supported by checkable evidence.



\## Working style

\- Work in small, reviewable steps.

\- Explain important decisions so I can defend the implementation.

\- Read the official rules and starter code before changing the architecture.

\- Use the project .venv for Python commands.

\- Prefer a working command-line pipeline before building a UI.

\- Ask before installing system packages, deleting files, or publishing.

\- Keep raw challenge data unchanged.

\- Never fabricate measurements, labels, scores, or results.



\## Analysis

\- Normalize timestamps to timezone-aware UTC.

\- Check missing values, duplicate timestamps, sampling gaps, and tractor IDs.

\- Develop methods using the labeled development window.

\- Do not treat unlabeled evaluation predictions as ground truth.

\- Compare tractors; concurrent machines may have different causes.

\- Allow overlapping causes and keep distinct causes as separate detections.

\- Reported GNSS position is not trusted ground truth during spoofing.

\- Cross-track error is a separate guidance-monitor channel in this simulation.

\- Poor reception while parked alone is not a scored working-tractor event.

\- Distinguish RFI observation times from report arrival times.

\- Do not assume elevated Kp proves space weather caused an episode.



\## Outputs

\- Match the supplied submission template exactly.

\- Generate submission.json through code.

\- Evidence must cite actual timestamps, tractor IDs, measurements,

&#x20; and relevant SDA observations.

\- Use the supplied validator.

\- Document exact setup and regeneration commands.

\- Keep runtime analysis reproducible without an LLM or live API.



## Project map (added 2026-11-14)

- Pipeline: `src/straightrows/` (io → features → candidates → attribution → assembly → evidence → export);
  parameters in `config.py`. `STARTER` config reproduces `src/baseline.py` (the official starter modified to
  use S4, commit b40c92e) and must keep doing so.
- Entry points: `src/run_pipeline.py` (submission.json), `src/evaluate_dev.py` (development scoring with the
  vendored official scorer `tools/score_submission.py`), `src/dashboard.py` (Streamlit, read-only view).
- Details: `README.md`, `docs/pipeline.md` (method, results, worklog), `docs/HANDOFF.md` (current state).

## Commands (Windows CMD, repository root, project .venv)

- Tests: `.venv\Scripts\python.exe -m pytest -q tests` (dataset tests skip without `data\`).
- Submission: `.venv\Scripts\python.exe src\run_pipeline.py --data data --output outputs\submission.json --github-handle reno-ogden --repo-url https://github.com/reno-ogden/straight-rows`
- Validate: `.venv\Scripts\python.exe src\validate_submission.py outputs\submission.json`
- Development evaluation: `.venv\Scripts\python.exe src\evaluate_dev.py --data data`
- Dashboard: `.venv\Scripts\python.exe -m streamlit run src\dashboard.py` (then http://localhost:8501)
- Data: `.venv\Scripts\python.exe scripts\get_data.py --zip C:\path\to\StraightRows_Student_Package.zip`
  (direct download fails TLS verification on this machine; never disable verification).

## Rules that must hold

- The dashboard and any analysis script reuse `straightrows` functions; do not reimplement detector,
  attribution or evidence logic in the UI. Display-only choices must not change detections.
- Keep `data/` byte-identical to the official release; never commit it.
- Never present development labels as predictions, and never present development scores (in-sample) as
  evaluation performance.
- Units: cross-track error in metres (separate guidance-monitor channel, signed); C/N0 in dB-Hz; speed in m/s;
  all times UTC. Working = 1-minute mean speed > 1.0 m/s (speed is only 0 or 4.5).
- Confidence is a fixed heuristic 0.5, not a calibrated probability; say so wherever it is shown.
- Before regenerating outputs, back up existing results under a new name; never overwrite a backup.
- Do not commit, push, change repository visibility, fork, open pull requests, or submit unless the user
  explicitly authorizes that specific action in the current conversation.
- Submission files contain only `participant.github_handle` (optional `display_name`); never add a name,
  email or student ID.

## Official submission workflow (current sources take precedence over older PDF versions)

- Deadline: Saturday 14 Nov 2026, 4:00 pm CT = 22:00 UTC; PRs opened or changed later are late.
  Sources: https://bluestaq.github.io/ndsu-hackathon-submissions/submit.html ;
  official repo `submissions/README.md` (lines 3-5); `.github/workflows/validate-submission.yml` line 50.
- Steps: make this repo public → fork Bluestaq/ndsu-hackathon-submissions → add exactly
  `submissions/reno-ogden/submission.json` → one PR to `main` → Submission check passes.

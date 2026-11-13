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


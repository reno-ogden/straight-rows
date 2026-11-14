# Third-party files

These files are copied from
[Bluestaq/ndsu-hackathon-submissions](https://github.com/Bluestaq/ndsu-hackathon-submissions)
at commit `4b9c010fe17f0825ca6cb7bc68deb6eae5ae2dfe`. Code in that repository is licensed under the
Apache License 2.0; a copy is in [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt).

| File here | Official source | Changes |
|---|---|---|
| `scripts/get_data.py` | `starter/scripts/get_data.py` | None (byte-identical). Its docstring mentions the official `starter/` paths; in this repository it is run as `scripts/get_data.py`. |
| `DATASET_SHA256` | `starter/DATASET_SHA256` | None (byte-identical). |
| `src/validate_submission.py` | `starter/submission/validate_submission.py` | None (identical apart from line endings). |
| `src/submission_template.json` | `starter/submission/submission_template.json` | None (identical apart from line endings). |
| `src/baseline.py` | `starter/submission/baseline.py` | **Modified** in commit `b40c92e`: regional S4 replaces Kp for separating space weather from jamming. |
| `tools/score_submission.py` | `scoring/score_submission.py` | Two provenance comment lines added; code unchanged. |

The official event guide (`docs/Bluestaq_NDSU_Straight_Rows_Hackathon_Official.pdf`) and the dataset
are "provided for the Straight Rows event" (official README); they are not covered by the Apache
License. The dataset is not committed here (see `.gitignore`).

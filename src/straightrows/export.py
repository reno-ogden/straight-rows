"""Build the submission dictionary in the template's exact shape."""
from .config import ACTION
from .evidence import describe

CONFIDENCE = 0.5  # unchanged from the starter; calibration is not part of this change


def to_submission(dets, d, cfg, handle, repo_url, display_name=None):
    out = []
    for i, det in enumerate(dets):
        others = [o for j, o in enumerate(dets) if j != i and o["start"] < det["end"] and o["end"] > det["start"]]
        out.append({
            "start": det["start"].isoformat(), "end": det["end"].isoformat(),
            "tractors": det["tractors"], "class": det["cause"], "action": ACTION[det["cause"]],
            "confidence": CONFIDENCE, "evidence": describe(det, d, cfg, others),
        })
    participant = {"github_handle": handle}
    if display_name:
        participant["display_name"] = display_name
    return {"participant": participant, "repository_url": repo_url, "detections": out}

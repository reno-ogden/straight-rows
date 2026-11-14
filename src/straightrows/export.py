"""Build the submission dictionary in the template's exact shape."""
from . import multipath
from .config import ACTION
from .evidence import describe

CONFIDENCE = 0.5  # unchanged from the starter; calibration is not part of this change


def to_submission(dets, d, cfg, handle, repo_url, display_name=None):
    out = []
    mp = [x for x in dets if x["cause"] == "MULTIPATH"]
    for i, det in enumerate(dets):
        # Concurrency lists other causes only: short multipath reports are not listed inside other detections'
        # evidence (keeps those detections unchanged), and multipath evidence lists the non-multipath ones.
        others = [o for j, o in enumerate(dets) if j != i and o["cause"] != "MULTIPATH"
                  and o["start"] < det["end"] and o["end"] > det["start"]]
        ev = (multipath.describe(det, d, cfg, mp, others) if det["cause"] == "MULTIPATH"
              else describe(det, d, cfg, others))
        out.append({
            "start": det["start"].isoformat(), "end": det["end"].isoformat(),
            "tractors": det["tractors"], "class": det["cause"], "action": ACTION[det["cause"]],
            "confidence": CONFIDENCE, "evidence": ev,
        })
    participant = {"github_handle": handle}
    if display_name:
        participant["display_name"] = display_name
    return {"participant": participant, "repository_url": repo_url, "detections": out}

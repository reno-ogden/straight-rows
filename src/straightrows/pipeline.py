"""Run the stages in order. `detect` returns intervals; `run` adds evidence + export."""
from . import multipath
from .assembly import assemble
from .attribution import attribute
from .candidates import flag
from .config import EVAL, Config
from .export import to_submission
from .features import minute_features


def detect(d, cfg=Config(), window=EVAL):
    feat = minute_features(d, window)
    flags = flag(feat, cfg)
    rows = attribute(flags, cfg)
    dets = assemble(rows, cfg, window)
    if cfg.detect_multipath:
        # Separate 1 Hz path: short per-tractor runs that bypass minute assembly (minimum duration, bridging,
        # cross-tractor merge). Existing detections are left exactly as assembled.
        dets = sorted(dets + multipath.detect(d, cfg, window), key=lambda m: (m["start"], m["cause"]))
    return dets


def run(d, handle, repo_url, cfg=Config(), window=EVAL, display_name=None):
    return to_submission(detect(d, cfg, window), d, cfg, handle, repo_url, display_name)

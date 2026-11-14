"""Run the stages in order. `detect` returns intervals; `run` adds evidence + export."""
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
    return assemble(rows, cfg, window)


def run(d, handle, repo_url, cfg=Config(), window=EVAL, display_name=None):
    return to_submission(detect(d, cfg, window), d, cfg, handle, repo_url, display_name)

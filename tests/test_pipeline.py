"""Regression tests on the development window. Run: python -m pytest -q"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
DATA = ROOT / "data"
pytestmark = pytest.mark.skipif(not (DATA / "farm/tractor_telemetry.csv.gz").exists(), reason="dataset not downloaded")


@pytest.fixture(scope="module")
def d():
    from straightrows.io import load
    return load(DATA)


def test_starter_config_reproduces_baseline(d):
    import evaluate_dev as e
    from straightrows.config import DEV, EVAL, STARTER
    from straightrows.pipeline import detect
    for w in (DEV, EVAL):
        assert e.key(e.baseline_dets(DATA, w)) == e.key(detect(d, STARTER, w))


def test_concurrent_causes_kept_separate(d):
    from straightrows.config import DEV, Config
    from straightrows.pipeline import detect
    t2 = [x for x in detect(d, Config(), DEV) if x["tractors"] == ["T2"] and x["start"].day == 4]
    causes = {x["cause"] for x in t2 if x["start"].hour in (12, 13)}
    assert {"EQUIPMENT_FAULT", "SPOOFING"} <= causes  # TRN-09 and TRN-06 overlap on T2


def test_output_passes_validator(d):
    import validate_submission
    from straightrows.pipeline import run
    sub = run(d, "reno-ogden", "https://github.com/reno-ogden/straight-rows")
    assert validate_submission.validate(sub) == []
    assert all(ev and all(s.strip() for s in ev) for ev in (x["evidence"] for x in sub["detections"]))

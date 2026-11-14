"""Synthetic tests for the suspected-multipath path (straightrows/multipath.py). No challenge data needed.

Run: python -m pytest -q tests/test_multipath.py
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src")]
from straightrows.config import STARTER, Config  # noqa: E402
from straightrows.export import to_submission  # noqa: E402
from straightrows.pipeline import detect  # noqa: E402

T0 = pd.Timestamp("2026-05-06T00:00:00Z")
WINDOW = (T0, T0 + pd.Timedelta(hours=1))
TRACTORS = ["T1", "T2", "T3"]
NORMAL = dict(speed=4.5, cn0=45.0, mincn0=40.0, link=True)
MP = Config(detect_multipath=True)
S = pd.Timedelta(seconds=1)


def tractor(segments, tid, total_s):
    """segments: list of (seconds, overrides) from T0; the rest of total_s is normal and working."""
    used = sum(s for s, _ in segments)
    rows, t = [], T0
    for secs, over in segments + [(total_s - used, {})]:
        s = {**NORMAL, **over}
        ts = pd.date_range(t, periods=secs, freq="1s")
        rows.append(pd.DataFrame({
            "ts": ts, "tractor_id": tid, "lat": 46.9, "lon": -97.2,
            "speed_mps": s["speed"], "cross_track_error_m": 0.05, "num_sats": 12,
            "mean_cn0_dbhz": s["cn0"], "min_cn0_dbhz": min(s["mincn0"], s["cn0"]),
            "fix_state": "RTK_FIXED", "base_link_ok": s["link"],
        }))
        t = t + pd.Timedelta(seconds=secs)
    return pd.concat(rows)


def scenario(per_tractor, total_s=3600, drop=None):
    """per_tractor: {tid: segments}. drop: {tid: [seconds offsets to delete]} to simulate missing samples."""
    tele = []
    for tid in TRACTORS:
        df = tractor(per_tractor.get(tid, []), tid, total_s)
        if drop and tid in drop:
            df = df[~df.ts.isin([T0 + k * S for k in drop[tid]])]
        tele.append(df)
    return {
        "tele": pd.concat(tele, ignore_index=True),
        "kp": pd.DataFrame({"ts": [T0], "kp": [2.0]}),
        "s4": pd.DataFrame({"ts": [T0], "s4": [0.05]}),
        "dst": pd.DataFrame({"ts": [T0], "dst_nT": [-10.0]}),
        "rfi": pd.DataFrame({"ts": pd.to_datetime([], utc=True), "id": [], "confidence": [], "centerLat": [],
                             "centerLon": [], "semiMajor_km": [], "semiMinor_km": []}),
    }


def mp(dets):
    return [x for x in dets if x["cause"] == "MULTIPATH"]


DIP = {"mincn0": 30.0}            # 10 dB below the 40 dB-Hz running median; mean C/N0 unchanged


# --- intended short-event behaviour -----------------------------------------------------------------
def test_short_dip_is_one_detection_with_1hz_boundaries():
    d = scenario({"T1": [(600, {}), (17, DIP)]})
    got = mp(detect(d, MP, WINDOW))
    assert len(got) == 1
    x = got[0]
    assert x["tractors"] == ["T1"]
    assert (x["start"], x["end"]) == (T0 + 600 * S, T0 + 617 * S)       # not rounded to minutes


def test_short_dip_survives_minute_assembly_rules():
    # 17 s is far below min_duration_s (180 s); multipath runs are not passed through minute assembly.
    d = scenario({"T1": [(600, {}), (17, DIP)]})
    assert Config().min_duration_s > 17
    assert len(mp(detect(d, MP, WINDOW))) == 1


def test_evidence_cites_measurements_and_does_not_claim_position_is_true():
    d = scenario({"T1": [(600, {}), (17, DIP)]})
    sub = to_submission(detect(d, MP, WINDOW), d, MP, "x", "https://github.com/x/y")
    det = [x for x in sub["detections"] if x["class"] == "MULTIPATH"][0]
    text = " ".join(det["evidence"])
    assert "00:10:00Z-00:10:17Z (17 s" in text and "min C/N0 down to 30.0" in text
    assert "mean C/N0 45.0" in text and "RTK_FIXED 100%" in text
    assert det["action"] == "CONTINUE_FALSE_ALARM" and det["confidence"] == 0.5


# --- normal brief fluctuations and look-alikes must not trigger ---------------------------------------
@pytest.mark.parametrize("segs", [
    [(600, {}), (5, DIP)],                              # brief blip shorter than mp_min_s
    [(600, {}), (17, {"mincn0": 36.0})],                # shallow: 4 dB below the running median
    [(600, {}), (90, DIP)],                             # long low: longer than mp_max_s (other causes)
    [(600, {}), (17, {"cn0": 38.0, "mincn0": 30.0})],   # mean C/N0 also drops (jamming-like), not multipath
])
def test_non_multipath_fluctuations_do_not_trigger(segs):
    assert mp(detect(scenario({"T1": segs}), MP, WINDOW)) == []


def test_long_low_rejected_by_max_duration_guard():
    # With a 121 s median a >~60 s low drags the median down by itself; widen the window so only the
    # explicit mp_max_s guard can reject a 90 s low.
    wide = Config(detect_multipath=True, mp_window_s=601)
    d = scenario({"T1": [(900, {}), (90, DIP)]})
    assert mp(detect(d, wide, WINDOW)) == []
    assert len(mp(detect(d, Config(detect_multipath=True, mp_window_s=601, mp_max_s=120), WINDOW))) == 1


def test_dip_while_parked_does_not_trigger():
    d = scenario({"T1": [(600, {}), (120, {"speed": 0.0}), (17, {"speed": 0.0, **DIP}), (120, {"speed": 0.0})]})
    assert mp(detect(d, MP, WINDOW)) == []


# --- gaps, missing samples and boundaries --------------------------------------------------------------
def test_brief_recovery_inside_one_dip_is_joined():
    d = scenario({"T1": [(600, {}), (8, DIP), (2, {}), (8, DIP)]})
    got = mp(detect(d, MP, WINDOW))
    assert len(got) == 1 and (got[0]["end"] - got[0]["start"]) == 18 * S


def test_missing_samples_inside_a_dip_are_joined_not_interpolated():
    d = scenario({"T1": [(600, {}), (17, DIP)]}, drop={"T1": [607, 608, 609]})
    got = mp(detect(d, MP, WINDOW))
    assert len(got) == 1 and (got[0]["start"], got[0]["end"]) == (T0 + 600 * S, T0 + 617 * S)
    assert got[0]["mp"]["samples"] == 14                  # only real samples are counted


def test_long_gap_splits_dip_into_pieces_too_short_to_report():
    d = scenario({"T1": [(600, {}), (24, DIP)]}, drop={"T1": list(range(607, 617))})   # 10 s missing
    assert mp(detect(d, MP, WINDOW)) == []


def test_no_baseline_no_detection():
    # Too little data around the dip to form a running median (min_periods): nothing is reported.
    d = scenario({"T1": [(600, {}), (17, DIP)]}, drop={"T1": [k for k in range(3600) if not 590 <= k < 630]})
    assert mp(detect(d, MP, WINDOW)) == []


def test_window_boundaries_clip_and_exclude():
    w = (T0 + 1200 * S, T0 + 2400 * S)
    d = scenario({"T1": [(1195, {}), (17, DIP), (1171, {}), (17, DIP)]})   # dips at 1195 s and 2383 s
    got = mp(detect(d, MP, w))
    assert [(x["start"], x["end"]) for x in got] == [(T0 + 1200 * S, T0 + 1212 * S), (T0 + 2383 * S, T0 + 2400 * S)]
    assert all(w[0] <= x["start"] and x["end"] <= w[1] for x in got)


# --- repetition and concurrency ------------------------------------------------------------------------
def test_repeated_dips_each_reported_once_with_recurrence():
    segs = [(300, {}), (17, DIP), (333, {}), (17, DIP), (333, {}), (17, DIP)]
    d = scenario({"T1": segs})
    dets = detect(d, MP, WINDOW)
    got = mp(dets)
    assert [x["start"] for x in got] == [T0 + 300 * S, T0 + 650 * S, T0 + 1000 * S]
    for a_, b_ in zip(got, got[1:]):
        assert a_["end"] <= b_["start"]                     # no overlap, no umbrella detection
    sub = to_submission(dets, d, MP, "x", "https://github.com/x/y")
    middle = [x for x in sub["detections"] if x["class"] == "MULTIPATH"][1]
    assert any("previous dip on T1 350 s away" in e and "next dip on T1 350 s away" in e for e in middle["evidence"])


def test_co_timed_dips_are_separate_per_tractor_and_not_merged():
    d = scenario({t: [(600, {}), (17, DIP)] for t in TRACTORS})
    got = mp(detect(d, MP, WINDOW))
    assert sorted(x["tractors"][0] for x in got) == TRACTORS
    assert all(len(x["tractors"]) == 1 for x in got)
    sub = to_submission(detect(d, MP, WINDOW), d, MP, "x", "https://github.com/x/y")
    assert any("Co-timed dips" in e and "T2" in e and "T3" in e
               for e in [x for x in sub["detections"] if x["tractors"] == ["T1"]][0]["evidence"])


def test_concurrent_equipment_fault_is_unchanged_and_kept_separate():
    # T1 loses its correction link for 20 min; a multipath-like dip occurs inside it.
    segs = [(600, {}), (600, {"link": False}), (17, {"link": False, **DIP}), (583, {"link": False})]
    d = scenario({"T1": segs})
    off, on = detect(d, Config(), WINDOW), detect(d, MP, WINDOW)
    ef_off = [x for x in off if x["cause"] == "EQUIPMENT_FAULT"]
    ef_on = [x for x in on if x["cause"] == "EQUIPMENT_FAULT"]
    assert ef_off and ef_off == ef_on                       # existing detection untouched
    assert len(mp(on)) == 1                                 # multipath kept as its own cause
    s_off = to_submission(off, d, Config(), "x", "https://github.com/x/y")["detections"]
    s_on = to_submission(on, d, MP, "x", "https://github.com/x/y")["detections"]
    assert [x for x in s_off if x["class"] == "EQUIPMENT_FAULT"] == [x for x in s_on if x["class"] == "EQUIPMENT_FAULT"]
    mp_ev = " ".join([x for x in s_on if x["class"] == "MULTIPATH"][0]["evidence"])
    assert "Concurrent with EQUIPMENT_FAULT on T1" in mp_ev


# --- switches -------------------------------------------------------------------------------------------
def test_off_by_default_and_in_starter():
    d = scenario({"T1": [(600, {}), (17, DIP)]})
    assert Config().detect_multipath is False and STARTER.detect_multipath is False
    assert mp(detect(d, Config(), WINDOW)) == [] and mp(detect(d, STARTER, WINDOW)) == []

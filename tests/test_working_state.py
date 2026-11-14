"""Synthetic tests for the working-state gate. No challenge data needed.

Run: python -m pytest -q tests/test_working_state.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from straightrows.config import STARTER, Config  # noqa: E402
from straightrows.pipeline import detect  # noqa: E402

T0 = pd.Timestamp("2026-05-06T00:00:00Z")
WINDOW = (T0, T0 + pd.Timedelta(hours=2))
TRACTORS = ["T1", "T2", "T3"]
NORMAL = dict(speed=4.5, cn0=45.0, mincn0=40.0, link=True)


def tractor(segments, tid):
    """segments: list of (seconds, overrides) applied in order from T0."""
    rows, t = [], T0
    for secs, over in segments:
        s = {**NORMAL, **over}
        ts = pd.date_range(t, periods=secs, freq="1s")
        rows.append(pd.DataFrame({
            "ts": ts, "tractor_id": tid, "lat": 46.9, "lon": -97.2,
            "speed_mps": s["speed"], "cross_track_error_m": 0.0, "num_sats": 12,
            "mean_cn0_dbhz": s["cn0"], "min_cn0_dbhz": min(s["mincn0"], s["cn0"]),
            "fix_state": "RTK_FIXED", "base_link_ok": s["link"],
        }))
        t = t + pd.Timedelta(seconds=secs)
    return pd.concat(rows)


def scenario(per_tractor, s4=0.05, total_s=7200):
    """per_tractor: {tid: segments}; unspecified tractors are normal and working."""
    tele = []
    for tid in TRACTORS:
        segs = per_tractor.get(tid, [])
        used = sum(s for s, _ in segs)
        tele.append(tractor(segs + [(total_s - used, {})], tid))
    return {
        "tele": pd.concat(tele, ignore_index=True),
        "kp": pd.DataFrame({"ts": [T0], "kp": [2.0]}),
        "s4": pd.DataFrame({"ts": [T0], "s4": [s4]}),
    }


def causes(dets, cause):
    return [d for d in dets if d["cause"] == cause]


M = 60
PARKED_POOR = {"speed": 0.0, "cn0": 30.0, "mincn0": 25.0}
WORKING_POOR = {"cn0": 30.0, "mincn0": 25.0}


# --- parked-only poor reception creates nothing --------------------------------------------
def test_parked_only_regional_loss_is_not_space_weather():
    d = scenario({t: [(30 * M, PARKED_POOR)] for t in TRACTORS}, s4=0.5)
    assert causes(detect(d, Config(), WINDOW), "SPACE_WEATHER") == []


def test_parked_only_loss_is_not_jamming():
    d = scenario({"T1": [(30 * M, PARKED_POOR)]}, s4=0.05)
    assert causes(detect(d, Config(), WINDOW), "JAMMING") == []


def test_parked_only_link_fault_is_not_equipment_fault():
    d = scenario({"T1": [(30 * M, {"speed": 0.0, "link": False})]})
    assert causes(detect(d, Config(), WINDOW), "EQUIPMENT_FAULT") == []


def test_historical_starter_config_still_flags_parked_loss():
    # STARTER intentionally reproduces the old baseline, which had no working gate.
    d = scenario({t: [(30 * M, PARKED_POOR)] for t in TRACTORS}, s4=0.5)
    assert causes(detect(d, STARTER, WINDOW), "SPACE_WEATHER")


# --- the same symptoms while working remain eligible ----------------------------------------
def test_working_regional_loss_is_space_weather():
    d = scenario({t: [(30 * M, WORKING_POOR)] for t in TRACTORS}, s4=0.5)
    sw = causes(detect(d, Config(), WINDOW), "SPACE_WEATHER")
    assert len(sw) == 1 and sw[0]["tractors"] == TRACTORS
    assert (sw[0]["start"], sw[0]["end"]) == (T0, T0 + pd.Timedelta(minutes=30))


def test_working_loss_is_jamming():
    d = scenario({"T1": [(30 * M, WORKING_POOR)]}, s4=0.05)
    jam = causes(detect(d, Config(), WINDOW), "JAMMING")
    assert len(jam) == 1 and jam[0]["tractors"] == ["T1"]


def test_working_link_fault_is_equipment_fault():
    d = scenario({"T1": [(30 * M, {"link": False})]})
    ef = causes(detect(d, Config(), WINDOW), "EQUIPMENT_FAULT")
    assert len(ef) == 1 and ef[0]["tractors"] == ["T1"]


# --- transitions do not pull the start into the parked period -------------------------------
def test_poor_while_parked_then_working_starts_when_work_starts():
    segs = [(20 * M, PARKED_POOR), (30 * M, WORKING_POOR)]
    d = scenario({t: segs for t in TRACTORS}, s4=0.5)
    sw = causes(detect(d, Config(), WINDOW), "SPACE_WEATHER")
    assert len(sw) == 1 and sw[0]["start"] == T0 + pd.Timedelta(minutes=20)


def test_mid_minute_start_of_work_starts_at_that_minute():
    # Work starts 30 s into minute 20: that minute's mean speed is 2.25 m/s > 1.0 -> working.
    segs = [(20 * M + 30, PARKED_POOR), (30 * M, WORKING_POOR)]
    d = scenario({t: segs for t in TRACTORS}, s4=0.5)
    sw = causes(detect(d, Config(), WINDOW), "SPACE_WEATHER")
    assert len(sw) == 1 and sw[0]["start"] == T0 + pd.Timedelta(minutes=20)


def test_working_then_parked_ends_when_work_stops():
    segs = [(30 * M, WORKING_POOR), (30 * M, PARKED_POOR)]
    d = scenario({t: segs for t in TRACTORS}, s4=0.5)
    sw = causes(detect(d, Config(), WINDOW), "SPACE_WEATHER")
    assert len(sw) == 1 and sw[0]["end"] == T0 + pd.Timedelta(minutes=30)


# --- bridging across parked intervals ------------------------------------------------------
def test_long_parked_gap_is_not_bridged():
    # 10 min parked (> 180 s bridge) between two working episodes: two detections, neither in the stop.
    segs = [(10 * M, WORKING_POOR), (10 * M, PARKED_POOR), (10 * M, WORKING_POOR)]
    d = scenario({"T1": segs}, s4=0.05)
    jam = causes(detect(d, Config(), WINDOW), "JAMMING")
    assert [(j["start"], j["end"]) for j in jam] == [
        (T0, T0 + pd.Timedelta(minutes=10)),
        (T0 + pd.Timedelta(minutes=20), T0 + pd.Timedelta(minutes=30)),
    ]


def test_short_stop_inside_one_working_episode_is_bridged():
    # Documented behaviour: a stop <= bridge_gap_s (here 2 min) between two working parts of the
    # same cause on the same tractor is joined, so the interval contains the brief stop. The
    # parked minutes themselves never start or extend an incident beyond working minutes.
    segs = [(10 * M, WORKING_POOR), (2 * M, PARKED_POOR), (10 * M, WORKING_POOR)]
    d = scenario({"T1": segs}, s4=0.05)
    jam = causes(detect(d, Config(), WINDOW), "JAMMING")
    assert [(j["start"], j["end"]) for j in jam] == [(T0, T0 + pd.Timedelta(minutes=22))]

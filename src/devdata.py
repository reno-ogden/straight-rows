"""Shared loaders for the labeled development window (2026-05-04..2026-05-06 UTC).

All timestamps are parsed as timezone-aware UTC. Raw files are read only.
"""
import json
from pathlib import Path

import pandas as pd

DEV_START = pd.Timestamp("2026-05-04T00:00:00Z")
DEV_END = pd.Timestamp("2026-05-06T00:00:00Z")
TRACTORS = ["T1", "T2", "T3"]


def load(data="data"):
    data = Path(data)
    tele = pd.read_csv(data / "farm/tractor_telemetry.csv.gz")
    tele["ts"] = pd.to_datetime(tele["ts"], utc=True, format="ISO8601")
    sgi = json.load(open(data / "sda/sgi_indices.json"))
    kp = pd.DataFrame(sgi["kp"])
    dst = pd.DataFrame(sgi["dst"])
    s4 = pd.DataFrame(json.load(open(data / "sda/scintillation_series.json"))["series"])
    adv = pd.DataFrame(json.load(open(data / "sda/constellation_advisories.json"))["advisories"])
    rfi = pd.DataFrame(json.load(open(data / "sda/rfi_reports.json"))["reports"])
    # Feeds mix ISO-8601 variants (e.g. RFI times carry fractional seconds, others do not).
    for df in (kp, dst, s4, adv, rfi):
        df["ts"] = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
    eps = pd.DataFrame(json.load(open(data / "labels/train_episodes.json"))["episodes"])
    eps["start"] = pd.to_datetime(eps["start"], utc=True, format="ISO8601")
    eps["end"] = pd.to_datetime(eps["end"], utc=True, format="ISO8601")
    assert ((eps.start >= DEV_START) & (eps.end <= DEV_END)).all(), "labels outside dev window"
    return dict(tele=tele, kp=kp, dst=dst, s4=s4, adv=adv, rfi=rfi, eps=eps)


def overlapping(eps, ep):
    """Other labeled episodes whose time interval intersects ep (any tractors)."""
    o = eps[(eps.id != ep.id) & (eps.start < ep.end) & (eps.end > ep.start)]
    return o


def context(ep):
    """Context window around an episode, scaled to its length."""
    dur = ep.end - ep.start
    pad = pd.Timedelta(minutes=3) if dur < pd.Timedelta(minutes=5) else pd.Timedelta(minutes=45)
    return ep.start - pad, ep.end + pad

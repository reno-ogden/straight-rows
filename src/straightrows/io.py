"""Load the raw challenge files read-only, with every timestamp as timezone-aware UTC."""
import json
from pathlib import Path

import pandas as pd


def _utc(s):
    # Feeds mix ISO-8601 variants (RFI times carry fractional seconds).
    return pd.to_datetime(s, utc=True, format="ISO8601")


def load(data="data"):
    data = Path(data)
    tele = pd.read_csv(data / "farm/tractor_telemetry.csv.gz")
    tele["ts"] = _utc(tele["ts"])
    sgi = json.load(open(data / "sda/sgi_indices.json"))
    out = {
        "tele": tele,
        "kp": pd.DataFrame(sgi["kp"]),
        "dst": pd.DataFrame(sgi["dst"]),
        "s4": pd.DataFrame(json.load(open(data / "sda/scintillation_series.json"))["series"]),
        "adv": pd.DataFrame(json.load(open(data / "sda/constellation_advisories.json"))["advisories"]),
        "rfi": pd.DataFrame(json.load(open(data / "sda/rfi_reports.json"))["reports"]),
    }
    for k in ("kp", "dst", "s4", "adv", "rfi"):
        out[k]["ts"] = _utc(out[k]["ts"])
    labels = data / "labels/train_episodes.json"
    if labels.exists():
        eps = pd.DataFrame(json.load(open(labels))["episodes"])
        eps["start"], eps["end"] = _utc(eps["start"]), _utc(eps["end"])
        out["labels"] = eps
    return out

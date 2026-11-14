"""Load the raw challenge files read-only, with every timestamp as timezone-aware UTC."""
import json
from pathlib import Path

import pandas as pd

TELE_COLUMNS = ("ts", "tractor_id", "lat", "lon", "speed_mps", "cross_track_error_m",
                "num_sats", "mean_cn0_dbhz", "min_cn0_dbhz", "fix_state", "base_link_ok")


def _utc(s):
    # Feeds mix ISO-8601 variants (RFI times carry fractional seconds).
    return pd.to_datetime(s, utc=True, format="ISO8601")


def _feed(rows, name, value=None, allow_empty=False):
    df = pd.DataFrame(rows)
    if df.empty and allow_empty:
        return pd.DataFrame({"ts": pd.Series(dtype="datetime64[ns, UTC]")})
    required = {"ts"} | ({value} if value else set())
    missing = required - set(df.columns)
    if missing or df.empty:
        raise ValueError(f"{name}: missing required data ({', '.join(sorted(missing)) or 'empty feed'})")
    df["ts"] = _utc(df["ts"])
    if df[list(required)].isna().any().any() or df.ts.duplicated().any():
        raise ValueError(f"{name}: null or duplicate timestamp/value")
    return df


def load(data="data"):
    data = Path(data)
    tele = pd.read_csv(data / "farm/tractor_telemetry.csv.gz")
    missing = set(TELE_COLUMNS) - set(tele.columns)
    if missing:
        raise ValueError(f"telemetry: missing columns {', '.join(sorted(missing))}")
    tele["ts"] = _utc(tele["ts"])
    if tele[list(TELE_COLUMNS)].isna().any().any():
        raise ValueError("telemetry: null required value")
    if tele.duplicated(["tractor_id", "ts"]).any():
        raise ValueError("telemetry: duplicate tractor_id/ts records")
    if not tele.tractor_id.isin(("T1", "T2", "T3")).all():
        raise ValueError("telemetry: unexpected tractor_id")
    sgi = json.load(open(data / "sda/sgi_indices.json"))
    out = {
        "tele": tele,
        "kp": _feed(sgi["kp"], "kp", "kp"),
        "dst": _feed(sgi["dst"], "dst", "dst_nT"),
        "s4": _feed(json.load(open(data / "sda/scintillation_series.json"))["series"], "s4", "s4"),
        "adv": _feed(json.load(open(data / "sda/constellation_advisories.json"))["advisories"], "adv", allow_empty=True),
        "rfi": _feed(json.load(open(data / "sda/rfi_reports.json"))["reports"], "rfi", allow_empty=True),
    }
    labels = data / "labels/train_episodes.json"
    if labels.exists():
        eps = pd.DataFrame(json.load(open(labels))["episodes"])
        eps["start"], eps["end"] = _utc(eps["start"]), _utc(eps["end"])
        out["labels"] = eps
    return out

"""Malformed-input checks that protect the meaning of tractor-minute aggregates."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from straightrows.config import Config  # noqa: E402
from straightrows.io import load  # noqa: E402


def package(tmp_path, tele=None, kp=None):
    (tmp_path / "farm").mkdir()
    (tmp_path / "sda").mkdir()
    if tele is None:
        tele = pd.DataFrame([{
            "ts": "2026-05-06T00:00:00Z", "tractor_id": t, "lat": 46.9, "lon": -97.2,
            "speed_mps": 4.5, "cross_track_error_m": 0.0, "num_sats": 12,
            "mean_cn0_dbhz": 45.0, "min_cn0_dbhz": 40.0,
            "fix_state": "RTK_FIXED", "base_link_ok": True,
        } for t in ("T1", "T2", "T3")])
    tele.to_csv(tmp_path / "farm/tractor_telemetry.csv.gz", index=False, compression="gzip")
    files = {
        "sgi_indices.json": {"kp": [{"ts": "2026-05-06T00:00:00Z", "kp": 2.0}] if kp is None else kp,
                             "dst": [{"ts": "2026-05-06T00:00:00Z", "dst_nT": -10}]},
        "scintillation_series.json": {"series": [{"ts": "2026-05-06T00:00:00Z", "s4": 0.05}]},
        "constellation_advisories.json": {"advisories": []},
        "rfi_reports.json": {"reports": []},
    }
    for name, content in files.items():
        (tmp_path / "sda" / name).write_text(json.dumps(content), encoding="utf-8")
    return tmp_path


def test_empty_optional_feeds_load_and_keep_utc_columns(tmp_path):
    d = load(package(tmp_path))
    assert d["rfi"].empty and d["adv"].empty
    assert str(d["rfi"].ts.dtype) == "datetime64[ns, UTC]"


def test_conflicting_duplicate_tractor_second_is_rejected(tmp_path):
    tele = pd.DataFrame([{
        "ts": "2026-05-06T00:00:00Z", "tractor_id": "T1", "lat": 46.9, "lon": -97.2,
        "speed_mps": 4.5, "cross_track_error_m": 0.0, "num_sats": 12,
        "mean_cn0_dbhz": v, "min_cn0_dbhz": 30.0,
        "fix_state": "RTK_FIXED", "base_link_ok": True,
    } for v in (30.0, 50.0)])
    with pytest.raises(ValueError, match="duplicate tractor_id/ts"):
        load(package(tmp_path, tele=tele))


def test_null_required_measurement_is_rejected(tmp_path):
    p = package(tmp_path)
    tele = pd.read_csv(p / "farm/tractor_telemetry.csv.gz")
    tele.loc[0, "mean_cn0_dbhz"] = float("nan")
    tele.to_csv(p / "farm/tractor_telemetry.csv.gz", index=False, compression="gzip")
    with pytest.raises(ValueError, match="null required value"):
        load(p)


def test_empty_required_sda_feed_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="kp: missing required data"):
        load(package(tmp_path, kp=[]))


@pytest.mark.parametrize("bad", [{"cn0_low_dbhz": -1}, {"bridge_gap_s": -1}, {"s4_storm": 2},
                                       {"mp_min_s": 20, "mp_max_s": 10}])
def test_invalid_configuration_is_rejected(bad):
    with pytest.raises(ValueError):
        Config(**bad)

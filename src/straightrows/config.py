"""Pipeline parameters. Every value is either inherited from the starter baseline
or chosen on the labeled development window (2026-05-04..06). See docs/pipeline.md.
"""
from dataclasses import dataclass

import pandas as pd

DEV = (pd.Timestamp("2026-05-04T00:00:00Z"), pd.Timestamp("2026-05-06T00:00:00Z"))
EVAL = (pd.Timestamp("2026-05-06T00:00:00Z"), pd.Timestamp("2026-05-07T00:00:00Z"))

ACTION = {
    "SPACE_WEATHER": "HALT_OR_DEGRADED_MODE",
    "JAMMING": "HALT_AND_REPORT",
    "SPOOFING": "HALT_CROSSCHECK_AND_REPORT",
    "EQUIPMENT_FAULT": "SERVICE_MACHINE_OTHERS_CONTINUE",
    "MULTIPATH": "CONTINUE_FALSE_ALARM",
}
# Priority used only in single-label mode (reproduces the starter's if-chain).
PRIORITY = ["SPACE_WEATHER", "JAMMING", "SPOOFING", "EQUIPMENT_FAULT"]


@dataclass(frozen=True)
class Config:
    # --- candidate flags (starter values) ---
    cn0_low_dbhz: float = 38.0       # 1-min mean C/N0 below this = signal-loss candidate
    xte_high_m: float = 1.0          # 1-min mean cross-track error above this = guidance-error candidate
    moving_mps: float = 1.0          # 1-min mean speed above this = tractor working
    link_low_frac: float = 0.7       # 1-min fraction of base_link_ok below this = link-fault candidate
    dropout_dbhz: float = 20.0       # 1-min minimum C/N0 below this (with normal mean) = antenna dropout
    # --- attribution context ---
    s4_storm: float = 0.2            # regional S4 at/above = scintillation conditions (commit b40c92e)
    # --- interval assembly (starter values) ---
    min_duration_s: float = 180.0    # drop runs shorter than this
    merge_gap_s: float = 300.0       # merge same-cause detections starting within this of a previous end
    # --- behaviour switches ---
    multi_label: bool = True         # independent per-cause tests (preserves concurrent causes)
    # Fill same-tractor, same-cause gaps <= this BEFORE the duration filter. Dev rationale:
    # TRN-10's link fault appears as 1-2 min flagged runs separated by 2-3 missing minutes,
    # so the starter's 180 s filter discarded every piece. 180 s covers every gap observed
    # in dev (max 3 missing min); the dev score is flat for any value from 120 to 360 s.
    bridge_gap_s: float = 180.0
    # Require the tractor to be working (the existing `working` flag: 1-min mean speed >
    # moving_mps) for SPACE_WEATHER, JAMMING and EQUIPMENT_FAULT, as SPOOFING already did via
    # xte_high. Official guide: scored episodes concern working tractors; poor reception while
    # parked alone is not a scored guidance event.
    require_working: bool = True
    # --- suspected multipath (straightrows/multipath.py) ---
    # Off by default: enabling it adds one short detection per tractor per dip (about 160 per working tractor
    # per development day), which approaches the validator's 500-detection limit. All values were chosen on the
    # development window only (see docs/pipeline.md); none uses labeled timestamps or positions.
    detect_multipath: bool = False
    mp_drop_db: float = 6.0          # 1 Hz min C/N0 at least this far below its running median
    mp_window_s: float = 121.0       # centred running-median window (s)
    mp_mean_tol_db: float = 2.0      # mean C/N0 must stay within this of its running median
    mp_join_s: float = 4.0           # join qualifying seconds separated by at most this (recoveries, gaps)
    mp_min_s: float = 8.0            # shortest dip reported (shorter = normal fluctuation)
    mp_max_s: float = 60.0           # longest dip reported (longer lows belong to other causes)


# Historical baseline: reproduces src/baseline.py exactly (no working gate except on XTE).
STARTER = Config(multi_label=False, bridge_gap_s=0.0, require_working=False)

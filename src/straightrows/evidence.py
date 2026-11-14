"""Evidence strings computed from the measurements behind each detection.

Everything quoted is measured from the raw 1 Hz telemetry or the SDA feeds over
the detection interval; nothing is templated without a number behind it.
"""
import math

import pandas as pd

TRACTORS = ["T1", "T2", "T3"]
PRE = pd.Timedelta(minutes=30)


def _z(ts):
    return ts.strftime("%H:%MZ")


def _km(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111.32
    dx = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _stats(seg):
    if seg.empty:
        return None
    return {
        "cn0": seg.mean_cn0_dbhz.mean(), "mincn0": seg.min_cn0_dbhz.min(),
        "sats": seg.num_sats.median(), "xte_med": seg.cross_track_error_m.median(),
        "xte_max": seg.cross_track_error_m.max(),
        "fixed": 100 * (seg.fix_state == "RTK_FIXED").mean(),
        "nofix": 100 * (seg.fix_state == "NO_FIX").mean(),
        "link": 100 * seg.base_link_ok.mean(),
    }


def describe(det, d, cfg, others):
    tele, a, b = d["tele"], det["start"], det["end"]
    aff = det["tractors"]
    un = [t for t in TRACTORS if t not in aff]
    span = f"{_z(a)}-{_z(b)}"
    during = tele[(tele.ts >= a) & (tele.ts < b)]
    sa = _stats(during[during.tractor_id.isin(aff)])
    su = _stats(during[during.tractor_id.isin(un)])
    pre = tele[(tele.ts >= a - PRE) & (tele.ts < a) & tele.tractor_id.isin(aff) & (tele.speed_mps > 0)]
    sp = _stats(pre)
    who, cause = ",".join(aff), det["cause"]
    ev = []

    # 1. Farm-side signal health: affected vs. own recent past vs. neighbours.
    s = f"{who} {span}: mean C/N0 {sa['cn0']:.1f} dB-Hz"
    s += f" (vs {sp['cn0']:.1f} in prior 30 min working)" if sp else " (no working samples in prior 30 min)"
    if su:
        s += f"; unaffected {','.join(un)} {su['cn0']:.1f}"
    s += f"; min C/N0 {sa['mincn0']:.1f}; median satellites {sa['sats']:.0f}."
    ev.append(s)

    # 2. Guidance + fix + correction link.
    s = (f"Cross-track error median {sa['xte_med']:.2f} m, max {sa['xte_max']:.2f} m"
         + (f" (unaffected median {su['xte_med']:.2f} m)" if su else "")
         + f"; RTK_FIXED {sa['fixed']:.0f}%, NO_FIX {sa['nofix']:.0f}%; RTK link up {sa['link']:.0f}%"
         + (f" (unaffected {su['link']:.0f}%)." if su else "."))
    ev.append(s)

    # 3. Space context: S4 in force during the interval, Kp, Dst.
    s4 = d["s4"]
    s4w = s4[(s4.ts > a - pd.Timedelta(minutes=15)) & (s4.ts < b)].s4
    kp = d["kp"][(d["kp"].ts > a - pd.Timedelta(hours=3)) & (d["kp"].ts < b)].kp
    dst = d["dst"][(d["dst"].ts > a - pd.Timedelta(hours=1)) & (d["dst"].ts < b)].dst_nT
    rel = "at/above" if s4w.min() >= cfg.s4_storm else ("below" if s4w.max() < cfg.s4_storm else "crossing")
    ev.append(f"Regional S4 {s4w.min():.3f}-{s4w.max():.3f} ({rel} the {cfg.s4_storm} scintillation level); "
              f"Kp {', '.join(f'{v:g}' for v in kp)}; Dst min {dst.min():.0f} nT.")

    # 4. Why this cause (the rule that fired, with its numbers).
    s4txt = f"S4 {s4w.min():.3f}-{s4w.max():.3f}"
    if cause == "SPACE_WEATHER":
        ev.append(f"Attributed SPACE_WEATHER: per-minute rule = all three tractors below {cfg.cn0_low_dbhz:g} dB-Hz "
                  f"together with S4 >= {cfg.s4_storm} (here {s4txt}); a regional cause fits, a single-machine "
                  f"fault does not.")
    elif cause == "JAMMING":
        ev.append(f"Attributed JAMMING: per-minute rule = C/N0 below {cfg.cn0_low_dbhz:g} dB-Hz with S4 below "
                  f"{cfg.s4_storm} (here {s4txt}), so scintillation does not explain the signal loss.")
    elif cause == "SPOOFING":
        ev.append(f"Attributed SPOOFING: guidance error above {cfg.xte_high_m:g} m on {who} with mean C/N0 "
                  f"{sa['cn0']:.1f} dB-Hz (no signal-health collapse)"
                  + (f", neighbours {su['cn0']:.1f}." if su else "."))
    elif cause == "EQUIPMENT_FAULT":
        # Name only the signal(s) that crossed their rule threshold, compared with the neighbours.
        parts = []
        if sa["link"] < 100 * cfg.link_low_frac or (su and sa["link"] < su["link"]):
            parts.append(f"RTK correction link up {sa['link']:.0f}%" + (f" vs {su['link']:.0f}% on {','.join(un)}" if su else ""))
        if sa["mincn0"] < cfg.dropout_dbhz:
            parts.append(f"antenna dropouts to min C/N0 {sa['mincn0']:.1f} dB-Hz"
                         + (f" vs {su['mincn0']:.1f} on {','.join(un)}" if su else ""))
        ev.append(f"Attributed EQUIPMENT_FAULT (machine-specific): {'; '.join(parts) or 'link/dropout rule'}; "
                  f"recommend servicing {who} while other machines continue.")

    # 5. RFI reports: one timestamp per report; README: 10-30 min delays. Search onset-10 to end+30 min.
    rfi = d["rfi"][(d["rfi"].ts >= a - pd.Timedelta(minutes=10)) & (d["rfi"].ts <= b + pd.Timedelta(minutes=30))]
    if len(rfi):
        pos = during[during.tractor_id.isin(aff)][["lat", "lon"]].mean()
        ev.append("RFI: " + "; ".join(
            f"{r.id} at {r.ts:%H:%M}Z ({(r.ts - a).total_seconds() / 60:+.0f} min from onset), confidence "
            f"{r.confidence}, centre {_km(r.centerLat, r.centerLon, pos.lat, pos.lon):.1f} km from {who} "
            f"(ellipse {r.semiMajor_km}x{r.semiMinor_km} km)" for r in rfi.itertuples()) + ".")
    else:
        ev.append(f"No RFI report between {_z(a - pd.Timedelta(minutes=10))} and {_z(b + pd.Timedelta(minutes=30))}.")

    # 6. Concurrent detections: distinct causes kept separate; note shared operational event.
    if others:
        ev.append("Concurrent with " + "; ".join(
            f"{o['cause']} on {','.join(o['tractors'])} {_z(o['start'])}-{_z(o['end'])}" for o in others)
            + " - reported as a separate cause in the same operational period.")
    return ev

"""Suspected multipath: short per-tractor dips in minimum C/N0 at 1 Hz.

Rule (per tractor, raw 1 Hz telemetry; parameters in Config, chosen on development data only):
  - min C/N0 is at least `mp_drop_db` below its own centred `mp_window_s` rolling median, while
  - mean C/N0 stays within `mp_mean_tol_db` of its own rolling median (the receiver as a whole is healthy;
    jamming and storms pull the mean down as well), and
  - the tractor is working in that minute (the pipeline's working definition: 1-min mean speed > moving_mps).
Qualifying seconds closer than `mp_join_s` are joined (brief recoveries and missing samples inside one dip),
and a run is kept only if it lasts `mp_min_s` to `mp_max_s` seconds. Shorter blips are normal fluctuation;
longer lows belong to other causes.

Representation: one detection per tractor per dip, with 1 Hz boundaries. These runs deliberately bypass the
minute pipeline's minimum duration, gap bridging and cross-tractor merge (a co-timed dip on three tractors is
three detections), and they never suppress or alter other causes. Reported GNSS position is used only to
describe recurrence, never to decide.
"""
import math

import pandas as pd

ONE = pd.Timedelta(seconds=1)


def _working_minutes(tele):
    """Per tractor-minute 1-min mean speed (same aggregation as features.minute_features 'moving')."""
    return (tele.set_index("ts").groupby("tractor_id")["speed_mps"].resample("1min").mean()
            .rename("moving").reset_index())


def detect(d, cfg, window):
    """Return MULTIPATH detections inside [window) as pipeline detection dicts (+ 'mp' measurement dict)."""
    a, b = window
    half = pd.Timedelta(seconds=cfg.mp_window_s / 2 + 1)
    tele = d["tele"]
    tele = tele[(tele.ts >= a - half) & (tele.ts < b + half)]
    if tele.empty:
        return []
    moving = _working_minutes(tele)
    working = moving[moving.moving > cfg.moving_mps]
    win = f"{int(cfg.mp_window_s)}s"
    minp = max(1, int(cfg.mp_window_s // 2))
    out = []
    for tr, g in tele.sort_values("ts").groupby("tractor_id"):
        g = g.set_index("ts")
        base_min = g.min_cn0_dbhz.rolling(win, center=True, min_periods=minp).median()
        base_mean = g.mean_cn0_dbhz.rolling(win, center=True, min_periods=minp).median()
        drop = base_min - g.min_cn0_dbhz
        is_working = g.index.floor("min").isin(working.ts[working.tractor_id == tr])
        cand = ((drop >= cfg.mp_drop_db) & ((base_mean - g.mean_cn0_dbhz).abs() <= cfg.mp_mean_tol_db)
                & is_working & (g.index >= a) & (g.index < b))
        ts = g.index[cand.values]
        if len(ts) == 0:
            continue
        # Join qualifying seconds whose separation is at most mp_join_s (covers brief recoveries and gaps).
        runs, start, prev = [], ts[0], ts[0]
        for t in ts[1:]:
            if (t - prev).total_seconds() > cfg.mp_join_s + 1:
                runs.append((start, prev + ONE))
                start = t
            prev = t
        runs.append((start, prev + ONE))
        for s, e in runs:
            dur = (e - s).total_seconds()
            if not (cfg.mp_min_s <= dur <= cfg.mp_max_s):
                continue
            seg = g[(g.index >= s) & (g.index < e)]
            out.append({
                "cause": "MULTIPATH", "start": s, "end": min(e, b), "tractors": [tr],
                "mp": {
                    "dur": dur, "samples": len(seg),
                    "low": float(seg.min_cn0_dbhz.min()), "base_min": float(base_min.loc[seg.index].median()),
                    "drop": float(drop.loc[seg.index].median()),
                    "mean": float(seg.mean_cn0_dbhz.mean()), "base_mean": float(base_mean.loc[seg.index].median()),
                    "sats": (int(seg.num_sats.min()), int(seg.num_sats.max())),
                    "fixed": 100 * float((seg.fix_state == "RTK_FIXED").mean()),
                    "link": 100 * float(seg.base_link_ok.mean()),
                    "xte_med": float(seg.cross_track_error_m.median()),
                    "lat": float(seg.lat.median()), "lon": float(seg.lon.median()),
                },
            })
    return sorted(out, key=lambda x: (x["start"], x["tractors"][0]))


def _m(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111320
    dx = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _z(ts):
    return ts.strftime("%H:%M:%SZ")


def describe(det, d, cfg, mp_dets, others):
    """Evidence for one MULTIPATH detection from its measurements, co-timed dips and recurrence."""
    m, tr, a, b = det["mp"], det["tractors"][0], det["start"], det["end"]
    ev = [f"{tr} {_z(a)}-{_z(b)} ({m['dur']:.0f} s, {m['samples']} samples at 1 Hz): min C/N0 down to {m['low']:.1f} "
          f"dB-Hz, median {m['drop']:.1f} dB below its {cfg.mp_window_s:g}-s running median ({m['base_min']:.1f}); "
          f"mean C/N0 {m['mean']:.1f} dB-Hz vs running median {m['base_mean']:.1f} (receiver otherwise healthy).",
          f"Satellites {m['sats'][0]}-{m['sats'][1]}; RTK_FIXED {m['fixed']:.0f}%; RTK link up {m['link']:.0f}%; "
          f"cross-track error median {m['xte_med']:.2f} m."]
    co = [x for x in mp_dets if x["tractors"][0] != tr and abs((x["start"] - a).total_seconds()) <= 5]
    ev.append("Co-timed dips (start within 5 s) on " + ", ".join(
        f"{x['tractors'][0]} {_z(x['start'])} (min {x['mp']['low']:.1f})" for x in co) + "."
              if co else "No co-timed dip on the other tractors (start within 5 s).")
    same = [x for x in mp_dets if x["tractors"][0] == tr and x is not det]
    prev = max((x for x in same if x["start"] < a), key=lambda x: x["start"], default=None)
    nxt = min((x for x in same if x["start"] > a), key=lambda x: x["start"], default=None)
    parts = []
    for name, x in (("previous", prev), ("next", nxt)):
        if x is not None:
            gap = abs((x["start"] - a).total_seconds())
            dist = _m(m["lat"], m["lon"], x["mp"]["lat"], x["mp"]["lon"])
            parts.append(f"{name} dip on {tr} {gap:.0f} s away, reported position {dist:.0f} m apart")
    ev.append(("Recurrence: " + "; ".join(parts) + ". Reported GNSS position is not verified and can be displaced "
               "by spoofing; it is descriptive only.") if parts else f"No other dip on {tr} in this window.")
    s4 = d["s4"][d["s4"].ts <= a].sort_values("ts").tail(1).s4
    ev.append(f"Attributed MULTIPATH (suspected): short min-C/N0 dip with healthy mean C/N0 while working; rule "
              f"{cfg.mp_drop_db:g} dB below running median for {cfg.mp_min_s:g}-{cfg.mp_max_s:g} s"
              + (f"; regional S4 in force {float(s4.iloc[0]):.3f}" if len(s4) else "") + ".")
    if others:
        ev.append("Concurrent with " + "; ".join(
            f"{o['cause']} on {','.join(o['tractors'])} {o['start']:%H:%MZ}-{o['end']:%H:%MZ}" for o in others)
            + " - reported as a separate cause.")
    return ev

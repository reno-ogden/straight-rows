#!/usr/bin/env python3
"""Descriptive statistics for each labeled development episode.

python src/dev_episode_stats.py --data data --out outputs/dev_episode_stats.csv

For each episode: affected vs. unaffected tractors during the episode, and the
affected tractors in the 30 minutes before onset (moving samples only). Adds
S4/Kp/Dst during the episode, RFI reports and advisories near it, and other
labeled episodes it overlaps. Descriptive only: no thresholds, development data only.
"""
import argparse
import math
from pathlib import Path

import pandas as pd

from devdata import TRACTORS, load, overlapping

PRE = pd.Timedelta(minutes=30)


def tele_stats(seg):
    if seg.empty:
        return {}
    return {
        "cn0_mean": seg.mean_cn0_dbhz.mean(),
        "cn0_min": seg.mean_cn0_dbhz.min(),
        "mincn0_min": seg.min_cn0_dbhz.min(),
        "sats_median": seg.num_sats.median(),
        "sats_min": seg.num_sats.min(),
        "xte_median": seg.cross_track_error_m.median(),
        "xte_max": seg.cross_track_error_m.max(),
        "rtk_fixed_pct": 100 * (seg.fix_state == "RTK_FIXED").mean(),
        "no_fix_pct": 100 * (seg.fix_state == "NO_FIX").mean(),
        "link_ok_pct": 100 * seg.base_link_ok.mean(),
        "moving_pct": 100 * (seg.speed_mps > 0).mean(),
    }


def km(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 111.32
    dx = (lon2 - lon1) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="data")
    p.add_argument("--out", default="outputs/dev_episode_stats.csv")
    args = p.parse_args()
    d = load(args.data)
    t, eps = d["tele"], d["eps"]
    rows = []
    for _, ep in eps.sort_values("start").iterrows():
        aff = list(ep.tractors)
        un = [x for x in TRACTORS if x not in aff]
        during = t[(t.ts >= ep.start) & (t.ts < ep.end)]
        pre = t[(t.ts >= ep.start - PRE) & (t.ts < ep.start) & t.tractor_id.isin(aff) & (t.speed_mps > 0)]
        row = {"id": ep.id, "class": ep["class"], "tractors": ",".join(aff),
               "start": ep.start.isoformat(), "end": ep.end.isoformat(),
               "minutes": (ep.end - ep.start).total_seconds() / 60}
        for tag, seg in (("aff", during[during.tractor_id.isin(aff)]),
                         ("unaff", during[during.tractor_id.isin(un)]),
                         ("pre", pre)):
            row.update({f"{tag}_{k}": v for k, v in tele_stats(seg).items()})
        s4 = d["s4"][(d["s4"].ts >= ep.start - pd.Timedelta(minutes=15)) & (d["s4"].ts < ep.end)]
        s4pre = d["s4"][(d["s4"].ts >= ep.start - PRE - pd.Timedelta(minutes=15)) & (d["s4"].ts < ep.start)]
        kp = d["kp"][(d["kp"].ts > ep.start - pd.Timedelta(hours=3)) & (d["kp"].ts < ep.end)]
        dst = d["dst"][(d["dst"].ts > ep.start - pd.Timedelta(hours=1)) & (d["dst"].ts < ep.end)]
        row.update(s4_min=s4.s4.min(), s4_max=s4.s4.max(), s4_pre_max=s4pre.s4.max(),
                   kp_values=" ".join(f"{v:g}" for v in kp.kp), dst_min_nT=dst.dst_nT.min())
        # RFI: feed carries one timestamp per report; README says reports arrive 10-30 min late,
        # so look from onset-10 min to end+30 min and report the lag from onset.
        near = d["rfi"][(d["rfi"].ts >= ep.start - pd.Timedelta(minutes=10)) &
                        (d["rfi"].ts <= ep.end + pd.Timedelta(minutes=30))]
        pos = during[during.tractor_id.isin(aff)][["lat", "lon"]].mean()
        row["rfi"] = "; ".join(
            f"{r.id} +{(r.ts - ep.start).total_seconds() / 60:.1f}min conf {r.confidence} "
            f"{km(r.centerLat, r.centerLon, pos.lat, pos.lon):.2f}km from tractors "
            f"(ellipse {r.semiMajor_km}x{r.semiMinor_km}km)" for r in near.itertuples())
        adv = d["adv"][(d["adv"].ts >= ep.start - pd.Timedelta(hours=2)) & (d["adv"].ts < ep.end)]
        row["advisories"] = "; ".join(f"{v.id} {v.type} {v.ts:%m-%d %H:%M}Z" for v in adv.itertuples())
        row["overlaps"] = "; ".join(f"{o.id} {o['class']} {','.join(o.tractors)}"
                                    for _, o in overlapping(eps, ep).iterrows())
        rows.append(row)
    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)  # same path, created if missing
    df.to_csv(args.out, index=False, float_format="%.3f")
    print(f"wrote {args.out}")

    # Unlabeled RFI reports and advisories in the dev window (for false-alarm context).
    def covered(ts):
        return ((eps.start - pd.Timedelta(minutes=10) <= ts) & (eps.end + pd.Timedelta(minutes=30) >= ts)).any()
    dev_rfi = d["rfi"][d["rfi"].ts < "2026-05-06"]
    print("\nRFI reports in dev window:")
    for r in dev_rfi.itertuples():
        print(f"  {r.id} {r.ts:%m-%d %H:%M:%S}Z conf {r.confidence} near a labeled episode: {covered(r.ts)} | {r.text}")
    print("Advisories:")
    for v in d["adv"].itertuples():
        print(f"  {v.id} {v.ts:%m-%d %H:%M}Z {v.type} {v.svn}: {v.text}")


if __name__ == "__main__":
    main()
